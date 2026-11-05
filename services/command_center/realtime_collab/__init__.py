"""Real‑time collaboration package.

This package implements a lightweight WebSocket‑based collaborative editing
service that can be dropped into the BioOS platform.  It provides:

* JWT‑based authentication (via ``auth.get_user``)
* Simple operational‑transformation (OT) for plain‑text documents (insert &
  delete)
* Per‑document rooms that broadcast operations to all connected peers
* In‑memory document store with optional JSON‑snapshot persistence on shutdown
* Prometheus metrics for connections, ops, and latency
* Extensible message schema via ``model.py`` (pydantic) – new message types can
  be added without breaking existing clients.

The implementation is intentionally minimal so you can replace the OT engine
with a full CRDT (Yjs/Automerge) later without changing the surrounding
infrastructure.
"""

__all__ = [
    "auth",
    "engine",
    "model",
    "server",
    "store",
]