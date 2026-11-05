"""Convenient façade for realtime collaboration security helpers.

This module groups together the three primary security concerns used by the
collaboration service:

* **Policy evaluation** – ``eval_policy`` forwards to the lightweight OPA shim
  defined in ``opa_client``.  It expects a dict with ``user``, ``doc_id`` and
  ``action`` keys and returns ``True`` when the operation is permitted.
* **Rate‑limiting** – ``allow_op`` forwards to the token‑bucket implementation in
  ``rate_limiter``.  It returns ``True`` if the user may perform another CRDT
  operation now, otherwise ``False``.
* **HMAC signature verification** – ``verify_signature`` forwards to the
  implementation in ``auth`` which derives a per‑user HMAC key from the JWT
  secret and validates a base64‑encoded signature.

Having a single import point makes the server code a little cleaner and provides
an obvious place for future expansion (e.g. adding audit logging).
"""

from __future__ import annotations

from typing import Dict

# Re‑export the concrete implementations from their respective modules.
from .opa_client import eval_policy as _eval_policy
from .rate_limiter import allow_op as _allow_op
from .auth import verify_signature as _verify_signature

__all__ = ["eval_policy", "allow_op", "verify_signature"]


def eval_policy(input_data: Dict) -> bool:
    """Delegate to :func:`services.command_center.realtime_collab.opa_client.eval_policy`.

    The function exists for backward‑compatibility with earlier code that imported
    ``eval_policy`` directly from a ``security`` module.
    """
    return _eval_policy(input_data)


def allow_op(user_id: str) -> bool:
    """Delegate to :func:`services.command_center.realtime_collab.rate_limiter.allow_op`."""
    return _allow_op(user_id)


def verify_signature(message: dict, signature_b64: str, user_id: str) -> bool:
    """Delegate to :func:`services.command_center.realtime_collab.auth.verify_signature`."""
    return _verify_signature(message, signature_b64, user_id)
