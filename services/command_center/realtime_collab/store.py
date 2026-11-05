"""In‑memory storage for documents and client sessions.

For a production service you would back this with Redis or a durable KV store
so that multiple pod replicas can share state.  The current implementation keeps
everything in a global ``_rooms`` dictionary – enough for a single‑node demo and
the unit‑tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

from fastapi import WebSocket

from .crdt_engine import Document

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class Room:
    """Container for all clients attached to a single document.

    Attributes
    ----------
    doc: Document
        The authoritative text and version.
    clients: List[WebSocket]
        Active connections for this document.
    """

    def __init__(self) -> None:
        self.doc: Document = Document()
        self.clients: List[WebSocket] = []

    # -------------------------------------------------------------------
    # Connection management helpers
    # -------------------------------------------------------------------
    async def broadcast(self, message: dict) -> None:
        dead: List[WebSocket] = []
        for ws in self.clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        if ws in self.clients:
            self.clients.remove(ws)


# Global registry – in‑memory only.
_rooms: Dict[str, Room] = {}

# Track active Redis subscriber tasks per document – needed to avoid spawning
# multiple listeners for the same doc.
_listener_tasks: Dict[str, asyncio.Task] = {}


def get_room(doc_id: str) -> Room:
    """Retrieve (or lazily create) a ``Room`` for *doc_id*."""
    if doc_id not in _rooms:
        _rooms[doc_id] = Room()
    return _rooms[doc_id]


def ensure_redis_listener(doc_id: str, room: Room) -> None:
    """Start a background ``asyncio`` task that forwards Redis pub/sub updates to the room.

    The task runs ``redis_store.subscribe_updates`` which loops forever.  It is
    stored in ``_listener_tasks`` so we only create one per document.
    """
    if doc_id in _listener_tasks:
        return
    import asyncio
    from .redis_store import subscribe_updates

    async def forward(msg: dict) -> None:
        # Broadcast the incoming message to all local clients.  The message already
        # contains the ``crdt_update`` field that clients will apply.
        await room.broadcast(msg)

    task = asyncio.create_task(subscribe_updates(doc_id, forward))
    _listener_tasks[doc_id] = task


# ---------------------------------------------------------------------------
# Optional snapshot persistence (useful for local debugging)
# ---------------------------------------------------------------------------
SNAPSHOT_DIR = Path(os.getenv("COLLAB_SNAPSHOT_DIR", "./data/snapshots"))
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _snapshot_path(doc_id: str) -> Path:
    safe_name = doc_id.replace("/", "_")  # simple sanitisation
    return SNAPSHOT_DIR / f"{safe_name}.json"


def save_snapshot(doc_id: str) -> None:
    """Persist the document state to Redis.

    In production the authoritative store is a Redis hash (see ``redis_store``).
    The function is kept synchronous because the server code still calls it in a
    blocking context.  Internally we run the async Redis call via ``asyncio``.
    """
    import asyncio
    from .redis_store import save_document

    room = get_room(doc_id)
    # ``save_document`` is async – we run it to completion here.
    asyncio.get_event_loop().run_until_complete(save_document(doc_id, room.doc))


def load_snapshot(doc_id: str) -> None:
    """Load a persisted snapshot from Redis (if any) and hydrate the in‑memory document."""
    import asyncio
    from .redis_store import load_document

    room = get_room(doc_id)
    # ``load_document`` is async – execute it synchronously for compatibility.
    room.doc = asyncio.get_event_loop().run_until_complete(load_document(doc_id))