# -*- coding: utf-8 -*-
"""
OIDC / RS256 verification tests against a LOCAL MOCK IDENTITY PROVIDER.

Pure-stdlib RSA (1024-bit test keypair generated via Miller-Rabin), a real
HTTP JWKS/discovery server on loopback, and full JWT claim validation.
Run: python -m pytest services/test_oidc_auth.py -v
"""

import hashlib
import http.server
import json
import math
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pytest

import oidc_auth as oidc
from rbac_auth import AuthError, authenticate_request


def _is_probable_prime(n: int, rounds: int = 16) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


_SMALL_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47,
                 53, 59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109]


def _gen_prime(bits: int) -> int:
    while True:
        candidate = random.getrandbits(bits) | (1 << (bits - 1)) | 1
        if any(candidate % p == 0 for p in _SMALL_PRIMES):
            continue
        if _is_probable_prime(candidate):
            return candidate


def _gen_keypair(bits: int = 1024):
    e = 65537
    while True:
        p = _gen_prime(bits // 2)
        q = _gen_prime(bits // 2)
        if p == q:
            continue
        n = p * q
        phi = (p - 1) * (q - 1)
        if math.gcd(e, phi) == 1:
            return n, e, pow(e, -1, phi)


def _sign_rs256(signing_input: bytes, d: int, n: int) -> bytes:
    """TEST-ONLY RS256 signing (private-key op; production signs at the IdP)."""
    k = (n.bit_length() + 7) // 8
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(signing_input).digest()
    em = b"\x00\x01" + b"\xff" * (k - len(digest_info) - 3) + b"\x00" + digest_info
    return pow(int.from_bytes(em, "big"), d, n).to_bytes(k, "big")


def _make_token(claims: dict, n: int, d: int, kid: str = "bioos-test-key") -> str:
    header = {"alg": "RS256", "kid": kid, "typ": "JWT"}
    signing_input = (
        oidc._b64url_encode(json.dumps(header).encode())
        + "."
        + oidc._b64url_encode(json.dumps(claims).encode())
    )
    signature = _sign_rs256(signing_input.encode("ascii"), d, n)
    return signing_input + "." + oidc._b64url_encode(signature)


class _MockIdp:
    """Loopback OIDC provider: discovery doc + JWKS endpoint (RS256 key)."""

    def __init__(self, n: int, e: int):
        self.n, self.e = n, e
        self.kid = "bioos-test-key"
        self.discovery: dict = {}
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/.well-known/openid-configuration":
                    body = json.dumps(outer.discovery).encode()
                elif self.path == "/jwks.json":
                    n_bytes = (outer.n.bit_length() + 7) // 8
                    jwks = {"keys": [{
                        "kty": "RSA", "kid": outer.kid, "alg": "RS256", "use": "sig",
                        "n": oidc._b64url_encode(outer.n.to_bytes(n_bytes, "big")),
                        "e": oidc._b64url_encode(outer.e.to_bytes(3, "big")),
                    }]}
                    body = json.dumps(jwks).encode()
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.discovery["issuer"] = self.base_url
        self.discovery["jwks_uri"] = self.base_url + "/jwks.json"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture(scope="module")
def idp():
    print("[FIXTURE] generating 1024-bit RSA test keypair (Miller-Rabin)...")
    n, e, d = _gen_keypair(1024)
    provider = _MockIdp(n, e)
    provider.d = d
    provider.start()
    oidc.clear_jwks_cache()
    yield provider
    provider.stop()
    oidc.clear_jwks_cache()


def _good_claims(issuer: str, **overrides):
    claims = {
        "iss": issuer,
        "aud": "bioos-api",
        "sub": "dr-smith",
        "role": "PHYSICIAN",
        "iat": time.time() - 5,
        "exp": time.time() + 300,
    }
    claims.update(overrides)
    return claims

def test_oidc_end_to_end_valid_token(idp):
    print("[TEST] OIDC E2E: discovery -> JWKS -> RS256 verify -> claims")
    token = _make_token(_good_claims(idp.base_url), idp.n, idp.d)
    claims = oidc.verify_rs256_token(token, idp.base_url, audience="bioos-api")
    assert claims["sub"] == "dr-smith" and claims["role"] == "PHYSICIAN"
    print(f" -> Valid RS256 token verified against {idp.base_url} (discovery + JWKS)")


def test_oidc_tampered_payload_rejected(idp):
    print("[TEST] OIDC: tampered payload must fail signature verification")
    token = _make_token(_good_claims(idp.base_url), idp.n, idp.d)
    header_b64, payload_b64, sig_b64 = token.split(".")
    forged_payload = oidc._b64url_encode(json.dumps(
        _good_claims(idp.base_url, role="ADMIN")).encode())
    with pytest.raises(oidc.OidcError, match="signature"):
        oidc.verify_rs256_token(f"{header_b64}.{forged_payload}.{sig_b64}", idp.base_url)
    print(" -> Privilege-escalation payload tampering REJECTED")


def test_oidc_expired_token_rejected(idp):
    print("[TEST] OIDC: expired token rejected")
    token = _make_token(_good_claims(idp.base_url, exp=time.time() - 10), idp.n, idp.d)
    with pytest.raises(oidc.OidcError, match="expired"):
        oidc.verify_rs256_token(token, idp.base_url)
    print(" -> Expired token REJECTED")


def test_oidc_wrong_issuer_rejected(idp):
    print("[TEST] OIDC: token from a foreign issuer rejected")
    token = _make_token(_good_claims("https://evil.example"), idp.n, idp.d)
    with pytest.raises(oidc.OidcError, match="issuer"):
        oidc.verify_rs256_token(token, idp.base_url)
    print(" -> Foreign-issuer token REJECTED")


def test_oidc_unknown_kid_rejected(idp):
    print("[TEST] OIDC: unknown key id rejected (after rotation refresh)")
    token = _make_token(_good_claims(idp.base_url), idp.n, idp.d, kid="retired-key")
    with pytest.raises(oidc.OidcError, match="kid"):
        oidc.verify_rs256_token(token, idp.base_url)
    print(" -> Unknown-kid token REJECTED (rotation refresh path exercised)")


def test_oidc_audience_enforcement(idp):
    print("[TEST] OIDC: audience claim enforced when configured")
    token = _make_token(_good_claims(idp.base_url), idp.n, idp.d)
    claims = oidc.verify_rs256_token(token, idp.base_url, audience="bioos-api")
    assert claims["aud"] == "bioos-api"
    with pytest.raises(oidc.OidcError, match="audience"):
        oidc.verify_rs256_token(token, idp.base_url, audience="other-service")
    print(" -> Audience enforcement PASS (match ok, mismatch rejected)")


def test_role_mapping_least_privilege():
    print("[TEST] OIDC role mapping: role claim > bioos_role > SERVICE fallback")
    assert oidc.map_claims_to_role({"role": "NURSE"}) == "NURSE"
    assert oidc.map_claims_to_role({"bioos_role": "PHARMACIST"}) == "PHARMACIST"
    assert oidc.map_claims_to_role({"sub": "nobody"}) == "SERVICE"
    print(" -> Role mapping PASS (least-privilege fallback)")


def test_rbac_integration_oidc_and_dev_paths(idp, monkeypatch):
    print("[TEST] RBAC integration: OIDC bearer honored; dev HS256 rejected under OIDC")
    oidc.clear_jwks_cache()
    monkeypatch.setenv("BIOOS_OIDC_ISSUER", idp.base_url)
    monkeypatch.setenv("BIOOS_OIDC_AUDIENCE", "bioos-api")

    from rbac_auth import issue_token

    oidc_token = _make_token(_good_claims(idp.base_url), idp.n, idp.d)
    assert authenticate_request(f"Bearer {oidc_token}", None) == "PHYSICIAN"

    # A dev-forged HS256 token must NOT pass while OIDC is enforced
    dev_token = issue_token(role="ADMIN", subject="attacker")
    with pytest.raises(AuthError, match="OIDC"):
        authenticate_request(f"Bearer {dev_token}", None)

    # With the issuer unset, the dev HS256 path is restored
    monkeypatch.delenv("BIOOS_OIDC_ISSUER")
    assert authenticate_request(f"Bearer {dev_token}", None) == "ADMIN"
    oidc.clear_jwks_cache()
    print(" -> RBAC integration PASS (OIDC enforced, dev fallback isolated)")
