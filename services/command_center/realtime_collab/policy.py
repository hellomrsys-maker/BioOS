"""Simple ACL policy module – a lightweight stand‑in for an OPA policy.

In production you would replace this file with a call to an actual OPA server
or the OPA binary (`opa eval`).  For the purposes of this repository we keep
the policy pure‑Python so the test suite does not depend on external binaries.

The policy data can be populated from a JSON file or defined inline.  Here we
hard‑code a minimal role‑based map:

* ``admin`` – can read **and** write any document.
* ``editor`` – can read and write.
* ``viewer`` – read‑only.
"""

from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# Example user‑to‑role mapping.  In a real deployment this would be loaded from
# an identity service or a JSON file.
# ---------------------------------------------------------------------------
USER_ROLES: Dict[str, str] = {
    "alice": "admin",
    "bob": "editor",
    "carol": "viewer",
    # The test suite uses a synthetic JWT with ``sub": "test_user".
    # Grant ``editor`` rights so undo/redo actions are permitted.
    "test_user": "editor",
}


def allow(user: str, doc_id: str, action: str) -> bool:
    """Return ``True`` if *user* is authorized to perform *action* on *doc_id*.

    Parameters
    ----------
    user: str
        The ``sub`` claim from the JWT (username).
    doc_id: str
        Identifier of the document being accessed.
    action: str
        Either ``"read"`` or ``"write"``.
    """
    role = USER_ROLES.get(user)
    if role is None:
        return False
    if action == "read":
        # All roles can read.
        return True
    # Write actions are restricted to admin or editor.
    return role in {"admin", "editor"}