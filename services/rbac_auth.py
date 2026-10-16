# -*- coding: utf-8 -*-
"""
BioOS Authentication & Role-Based Access Control (OIDC-ready skeleton)

Design:
- HS256 JWT sign/verify implemented purely with the Python standard library
  (hmac/hashlib/base64) so no new pinned dependency enters the supply chain.
- Production swap: replace verify_token() with JWKS-based RS256 validation
  against the hospital OIDC provider (claims schema stays identical).
- ENFORCEMENT IS OFF BY DEFAULT (BIOOS_AUTH_REQUIRED=0) so the flight-deck UI
  and demo flows keep working. Set BIOOS_AUTH_REQUIRED=1 to enforce.
  The web UI should then fetch a token from POST /api/auth/token.

Permission model:
- read             : any GET on /api/*
- write_telemetry  : kernel/envelope stepping, OS command execution, alarm filter
- bed_manage       : admit / transfer / discharge / select_bed
- clinical_order   : FHIR MedicationRequest, subscriptions (write)
- pharmacy         : pharmacy surveillance read
- audit            : /api/audit/* reads
- admin            : anything not otherwise mapped
"""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional


class AuthError(Exception):
    """Raised when authentication fails. Message is safe to return to clients."""


# ---- permissions -----------------------------------------------------------

READ = "read"
WRITE_TELEMETRY = "write_telemetry"
CLINICAL_ORDER = "clinical_order"
BED_MANAGE = "bed_manage"
PHARMACY = "pharmacy"
AUDIT = "audit"
ADMIN = "admin"

ROLE_PERMISSIONS: Dict[str, set] = {
    "ADMIN": {READ, WRITE_TELEMETRY, CLINICAL_ORDER, BED_MANAGE, PHARMACY, AUDIT, ADMIN},
    "PHYSICIAN": {READ, WRITE_TELEMETRY, CLINICAL_ORDER, BED_MANAGE, PHARMACY},
    "NURSE": {READ, WRITE_TELEMETRY, BED_MANAGE},
    "PHARMACIST": {READ, PHARMACY, CLINICAL_ORDER},
    "AUDITOR": {READ, AUDIT},
    "SERVICE": {READ, WRITE_TELEMETRY},
}

# ---- route permission mapping ----------------------------------------------

def route_permission(path: str, method: str) -> Optional[str]:
    """Maps an API route to the permission it requires. None = public."""
    if not path.startswith("/api/"):
        return None  # static flight-deck UI
    if path == "/api/health" or path == "/api/auth/token":
        return None
    if path.startswith("/api/audit/"):
        return AUDIT if method == "GET" else ADMIN
    if path == "/api/fhir/medication-request" and method == "POST":
        return CLINICAL_ORDER
    if path.startswith("/api/fhir/subscriptions"):
        return READ if method == "GET" else CLINICAL_ORDER
    if path.startswith("/api/fhir/"):
        return READ if method == "GET" else CLINICAL_ORDER
    if path.startswith("/api/hospital/") and method == "POST":
        return BED_MANAGE
    if method == "POST" and path in (
        "/api/kernel/step",
        "/api/envelope/step",
        "/api/os/execute",
        "/api/wellbeing/filter_alarm",
    ):
        return WRITE_TELEMETRY
    return READ if method == "GET" else ADMIN


def role_has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


# ---- HS256 JWT (stdlib) ------------------------------------------------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def default_dev_secret() -> str:
    return os.environ.get(
        "BIOOS_JWT_SECRET", "bioos-dev-secret-DO-NOT-USE-IN-PRODUCTION"
    )


def issue_token(role: str, subject: str, secret: Optional[str] = None, ttl_seconds: int = 3600) -> str:
    if role not in ROLE_PERMISSIONS:
        raise AuthError(f"unknown role: {role}")
    secret = secret or default_dev_secret()
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + int(ttl_seconds),
        "iss": "bioos-runtime",
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    )
    signature = hmac.new(
        secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    return signing_input + "." + _b64url(signature)


def verify_token(token: str, secret: Optional[str] = None) -> Dict[str, Any]:
    """Validates signature, issuer, expiry and role claim. Returns claims.
    Production OIDC swap: validate RS256 via JWKS from the IdP instead."""
    secret = secret or default_dev_secret()
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed token")
    signing_input = parts[0] + "." + parts[1]
    expected = hmac.new(
        secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(expected, _b64url_decode(parts[2])):
        raise AuthError("invalid signature")
    try:
        claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except Exception as exc:
        raise AuthError("malformed claims") from exc
    if claims.get("iss") != "bioos-runtime":
        raise AuthError("untrusted issuer")
    if float(claims.get("exp", 0)) < time.time():
        raise AuthError("token expired")
    if claims.get("role") not in ROLE_PERMISSIONS:
        raise AuthError("unknown role claim")
    return claims


# ---- request authentication ---------------------------------------------------

def _api_key_role(api_key: Optional[str]) -> Optional[str]:
    mapping: Dict[str, str] = {}
    env_key = os.environ.get("BIOOS_SERVICE_API_KEY")
    if env_key:
        mapping[env_key] = "SERVICE"
    if api_key and api_key in mapping:
        return mapping[api_key]
    return None


def authenticate_request(
    authorization: Optional[str],
    x_api_key: Optional[str],
    secret: Optional[str] = None,
) -> str:
    """Returns the authenticated role.

    Resolution order for `Authorization: Bearer <jwt>`:
    1. OIDC RS256 via the hospital IdP's JWKS (when BIOOS_OIDC_ISSUER is set)
    2. Dev HS256 tokens (issue_token/verify_token) otherwise
    `X-Api-Key` maps to the SERVICE role (env BIOOS_SERVICE_API_KEY)."""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        from oidc_auth import issuer_configured

        if issuer_configured():
            from oidc_auth import map_claims_to_role, verify_rs256_token

            try:
                claims = verify_rs256_token(
                    token,
                    os.environ["BIOOS_OIDC_ISSUER"],
                    audience=os.environ.get("BIOOS_OIDC_AUDIENCE"),
                )
            except Exception as exc:
                raise AuthError(f"OIDC verification failed: {exc}") from exc
            return map_claims_to_role(claims)
        claims = verify_token(token, secret)
        return str(claims["role"])
    role = _api_key_role(x_api_key)
    if role:
        return role
    raise AuthError("missing or invalid credentials")
