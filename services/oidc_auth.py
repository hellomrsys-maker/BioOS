# -*- coding: utf-8 -*-
"""
BioOS OIDC / RS256 JWT Verification (production auth path)

Verifies access tokens against a hospital OIDC provider's published JWKS:
- OpenID Connect Discovery: fetches {issuer}/.well-known/openid-configuration
  and follows jwks_uri; falls back to {issuer}/.well-known/jwks.json
- RSASSA-PKCS1-v1_5 (RS256) signature verification in PURE STDLIB
  (modular exponentiation + RFC 8017 padding check; no crypto dependency)
- Claims validation: iss, aud (optional), exp, nbf
- JWKS cache with TTL + refresh-on-unknown-kid (key rotation)

Configuration (env):
- BIOOS_OIDC_ISSUER   : e.g. https://sso.hospital.org/realms/bioos
- BIOOS_OIDC_AUDIENCE : expected aud claim (optional but recommended)

Role mapping: claims["role"] if present, else claims["bioos_role"], else
SERVICE (least privilege). Deployment-specific group->role mapping is a P5 item.
"""

import base64
import hashlib
import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple


class OidcError(Exception):
    """Raised on any OIDC verification failure. Message is client-safe."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


# ASN.1 DigestInfo prefix for SHA-256 (RFC 8017 §9.2 note 1)
_SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")

_JWKS_TTL_SECONDS = 300.0

_JWKS_CACHE: Dict[str, Tuple[float, Dict[str, Tuple[int, int]]]] = {}


def _http_get_json(url: str, timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_jwks_document(issuer: str, timeout: float = 3.0) -> Dict[str, Any]:
    """OIDC discovery first (follows jwks_uri), then well-known fallback."""
    try:
        discovery = _http_get_json(
            issuer.rstrip("/") + "/.well-known/openid-configuration", timeout
        )
        jwks_uri = discovery.get("jwks_uri")
        if jwks_uri:
            return _http_get_json(jwks_uri, timeout)
    except Exception:
        pass  # fall through to direct well-known JWKS path
    return _http_get_json(issuer.rstrip("/") + "/.well-known/jwks.json", timeout)


def _parse_rs256_jwks(document: Dict[str, Any]) -> Dict[str, Tuple[int, int]]:
    """Extracts {kid: (modulus, exponent)} for RSA/RS256 keys only."""
    keys: Dict[str, Tuple[int, int]] = {}
    for jwk in document.get("keys", []):
        if jwk.get("kty") != "RSA" or jwk.get("alg", "RS256") != "RS256":
            continue
        kid = jwk.get("kid", "")
        if not kid or "n" not in jwk or "e" not in jwk:
            continue
        n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
        keys[kid] = (n, e)
    return keys


def issuer_configured() -> bool:
    return bool(os.environ.get("BIOOS_OIDC_ISSUER"))


def map_claims_to_role(claims: Dict[str, Any]) -> str:
    for claim in ("role", "bioos_role"):
        value = claims.get(claim)
        if isinstance(value, str) and value:
            return value
    return "SERVICE"  # least privilege when the IdP carries no BioOS role


# -*- coding: utf-8 -*-
"""
BioOS OIDC / RS256 JWT Verification — stdlib-only (P1 close-out spike)

Verifies hospital IdP tokens against a cached JWKS:
- Discovery: {issuer}/.well-known/openid-configuration -> jwks_uri,
  with direct {issuer}/.well-known/jwks.json fallback
- RS256 signature verification via pure-Python RSA public-key modexp
  (verification needs NO private key material, so the stdlib suffices and
  the dependency surface stays zero)
- Claims validation: iss, aud (optional), exp, nbf
- kid-based key selection with rotation-safe refresh on unknown kid

INTEGRATION (rbac_auth.authenticate_request): enabled when BIOOS_OIDC_ISSUER
is set and the bearer token is RS256; role comes from the `bioos_role` or
`role` claim (default SERVICE). Dev HS256 tokens remain the local path.

PRODUCTION NOTE: certified deployments should swap this for a hardened JWT
library behind TLS-pinned JWKS fetching; this module proves the contract.
"""

import base64
import hashlib
import json
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

# DER prefix for PKCS#1 v1.5 DigestInfo with SHA-256
_SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")
_JWKS_TTL_SECONDS = 300.0


class OidcError(Exception):
    """Raised for any OIDC verification failure (safe to surface to clients)."""


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _http_get_json(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_jwks_document(issuer: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Fetches the raw JWKS document, via discovery first, direct fallback."""
    try:
        discovery = _http_get_json(
            issuer.rstrip("/") + "/.well-known/openid-configuration", timeout
        )
        jwks_uri = discovery.get("jwks_uri")
        if jwks_uri:
            return _http_get_json(jwks_uri, timeout)
    except Exception:
        pass  # fall back to the conventional path
    return _http_get_json(issuer.rstrip("/") + "/.well-known/jwks.json", timeout)


def _parse_rs256_jwks(jwks: Dict[str, Any]) -> Dict[str, Tuple[int, int]]:
    keys: Dict[str, Tuple[int, int]] = {}
    for jwk in jwks.get("keys", []):
        if jwk.get("kty") != "RSA":
            continue
        if jwk.get("alg", "RS256") != "RS256":
            continue
        if jwk.get("use", "sig") != "sig":
            continue
        kid = jwk.get("kid", "")
        n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
        e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
        keys[kid] = (n, e)
    return keys


_JWKS_CACHE: Dict[str, Tuple[float, Dict[str, Tuple[int, int]]]] = {}


def get_rs256_public_keys(
    issuer: str, force_refresh: bool = False, timeout: float = 3.0
) -> Dict[str, Tuple[int, int]]:
    cached = _JWKS_CACHE.get(issuer)
    if cached and not force_refresh and (time.time() - cached[0]) < _JWKS_TTL_SECONDS:
        return cached[1]
    keys = _parse_rs256_jwks(fetch_jwks_document(issuer, timeout))
    if not keys:
        raise OidcError("JWKS contains no usable RS256 keys")
    _JWKS_CACHE[issuer] = (time.time(), keys)
    return keys


def _rsa_verify_pkcs1v15_sha256(signature: bytes, n: int, e: int, digest: bytes) -> bool:
    """RFC 8017 RSASSA-PKCS1-v1_5 verification (SHA-256), pure stdlib."""
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    em = pow(s, e, n).to_bytes(k, "big")
    digest_info = _SHA256_DIGESTINFO + digest
    if len(digest_info) + 11 > k:
        return False
    if em[0] != 0x00 or em[1] != 0x01:
        return False
    idx = 2
    while idx < k and em[idx] == 0xFF:
        idx += 1
    # PS must be exactly k - 3 - len(T) bytes and at least 8 bytes of 0xFF
    if idx != k - len(digest_info) - 1 or idx - 2 < 8:
        return False
    if em[idx] != 0x00:
        return False
    return em[idx + 1:] == digest_info


def verify_rs256_token(
    token: str,
    issuer: str,
    audience: Optional[str] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Verifies an RS256 JWT against the issuer's JWKS. Returns claims."""
    parts = token.split(".")
    if len(parts) != 3:
        raise OidcError("malformed token")
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except Exception as exc:
        raise OidcError("malformed token segments") from exc
    if header.get("alg") != "RS256":
        raise OidcError(f"unsupported alg {header.get('alg')!r}")

    kid = header.get("kid", "")
    try:
        keys = get_rs256_public_keys(issuer)
        if kid not in keys:
            # Key rotation: refresh once before failing
            keys = get_rs256_public_keys(issuer, force_refresh=True)
    except OidcError:
        raise
    except Exception as exc:
        raise OidcError(f"JWKS fetch failed: {exc}") from exc
    if kid not in keys:
        raise OidcError(f"unknown kid {kid!r}")

    n, e = keys[kid]
    signing_input = (parts[0] + "." + parts[1]).encode("ascii")
    digest = hashlib.sha256(signing_input).digest()
    if not _rsa_verify_pkcs1v15_sha256(_b64url_decode(parts[2]), n, e, digest):
        raise OidcError("invalid RS256 signature")

    now = now if now is not None else time.time()
    if claims.get("iss") != issuer:
        raise OidcError("issuer mismatch")
    if audience is not None and claims.get("aud") != audience:
        raise OidcError("audience mismatch")
    if float(claims.get("exp", 0)) < now:
        raise OidcError("token expired")
    if float(claims.get("nbf", 0)) > now + 30:
        raise OidcError("token not yet valid")
    return claims


def clear_jwks_cache() -> None:
    _JWKS_CACHE.clear()


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def issuer_configured() -> bool:
    """True when BIOOS_OIDC_ISSUER is set (RS256 IdP path active)."""
    return bool(os.environ.get("BIOOS_OIDC_ISSUER"))


def map_claims_to_role(claims: Dict[str, Any]) -> str:
    """Maps verified IdP claims to a BioOS role.

    Precedence: `bioos_role` -> `role` -> SERVICE. Unknown role strings pass
    through unchanged; rbac_auth's permission table then denies everything
    (secure-by-default: an unrecognized role gets zero permissions)."""
    return str(claims.get("bioos_role") or claims.get("role") or "SERVICE")
