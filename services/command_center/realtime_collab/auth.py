"""Authentication helpers for the realtime collaboration service.

The platform already uses JWT tokens (see other services).  This module provides a
single ``get_user`` dependency compatible with FastAPI that validates a token
provided via an ``Authorization: Bearer <jwt>`` header and returns the ``sub``
claim as the user identifier.

If the environment variable ``COLLAB_JWT_SECRET`` is not set a warning is printed
and a hard‑coded fallback secret is used – **never** in production!
"""

import jwt
import os
from typing import Optional

import jwt  # pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Use a sufficiently long default secret for local development (>= 32 bytes).
# In production the env var ``COLLAB_JWT_SECRET`` must be set to a strong secret.
JWT_SECRET: str = os.getenv(
    "COLLAB_JWT_SECRET", "change-me-please-please-change-32b"
)
if JWT_SECRET == "change-me-please":
    # In a CI environment this is acceptable, but warn the operator.
    print(
        "[realtime_collab] WARNING: using default JWT secret – set COLLAB_JWT_SECRET"
    )

bearer = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> dict:
    """Decode a JWT using the shared secret.

    Raises ``jwt.PyJWTError`` if the token is malformed or the signature does not
    match.  The caller should translate this into an ``HTTPException``.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def get_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    ) -> str:
    """FastAPI dependency that returns the authenticated ``user_id``.

    * If no ``Authorization`` header is present, a ``401`` error is raised.
    * If the token cannot be decoded, a ``401`` error is raised.
    * On success the ``sub`` claim is returned as a string.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    try:
        payload = _decode_token(credentials.credentials)
        user_id = str(payload.get("sub"))
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'sub' claim",
            )
        return user_id
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# HMAC utilities (per‑operation integrity) – used by the server to verify that
# the client really generated the operation.
# ---------------------------------------------------------------------------
import base64
import hashlib
import hmac
import json

def _derive_hmac_key(user_id: str) -> bytes:
    """Derive a deterministic HMAC key from the global JWT secret and the user id.

    In production you would store a per‑user secret in a KMS.  Here we simply
    hash ``JWT_SECRET || user_id`` with SHA‑256.
    """
    return hmac.new(JWT_SECRET.encode(), user_id.encode(), hashlib.sha256).digest()


def verify_signature(message: dict, signature_b64: str, user_id: str) -> bool:
    """Verify an HMAC‑SHA256 signature over the *canonical* JSON representation.

    The client must sign the JSON payload **exactly** as the server receives it,
    using sorted keys and no whitespace (``json.dumps(..., separators=(',', ':'),
    sort_keys=True)``).  The signature is base64‑encoded.
    """
    key = _derive_hmac_key(user_id)
    canonical = json.dumps(message, separators=(",", ":"), sort_keys=True).encode()
    expected = hmac.new(key, canonical, hashlib.sha256).digest()
    try:
        provided = base64.b64decode(signature_b64)
    except Exception:
        return False
    return hmac.compare_digest(expected, provided)