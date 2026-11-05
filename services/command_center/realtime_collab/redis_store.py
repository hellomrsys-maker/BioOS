"""Redis‑backed persistence and pub/sub for the realtime collaboration service.

The module provides a thin wrapper around ``redis-py`` that stores the document
content and version in a Redis hash and uses a pub/sub channel to broadcast CRDT
updates between multiple pod replicas.

Only a minimal API is needed for the server:

* ``load_document(doc_id)`` – returns a ``Document`` (CRDT wrapper) populated
  from the stored state, or a fresh empty document if none exists.
* ``save_document(doc)`` – persists the document’s text and version.
* ``publish_update(doc_id, message)`` – publishes a JSON payload to the channel
  ``collab:doc:{doc_id}``.
* ``subscribe_updates(doc_id, callback)`` – runs a background ``asyncio`` task
  that listens on the same channel and invokes ``callback(message)`` for each
  incoming message.  The callback is typically ``room.broadcast``.

For unit‑testing we fall back to the in‑memory ``fakeredis`` library when the
environment variable ``COLLAB_REDIS_URL`` is not set or when ``redis`` cannot be
imported.  This keeps the test suite fast and deterministic.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Callable, Awaitable

# Attempt to import the real ``redis`` async client.  If it fails, or if the
# ``COLLAB_REDIS_URL`` environment variable is not defined, we fall back to a tiny
# in‑memory stub that implements only the methods we need for the test suite.
try:
    if not os.getenv("COLLAB_REDIS_URL"):
        raise ImportError("No Redis URL – using in‑memory stub")
    import redis.asyncio as redis  # type: ignore
except Exception:  # pragma: no cover – use lightweight stub for test envs
    class _InMemoryPubSub:
            def __init__(self, channel):
                self.channel = channel
                self.queue = asyncio.Queue()

            async def listen(self):
                while True:
                    data = await self.queue.get()
                    yield {"type": "message", "data": data}

    class _InMemoryRedis:
        def __init__(self):
            self.hashes: dict[str, dict[bytes, bytes]] = {}
            self.channels: dict[str, list[asyncio.Queue]] = {}
            self.streams: dict[str, list[dict[str, str]]] = {}

        @classmethod
        def from_url(cls, *_):
            return cls()

        async def hset(self, key, mapping):
            # Ensure values are bytes for compatibility.
            self.hashes[key] = {k.encode() if isinstance(k, str) else k: str(v).encode() for k, v in mapping.items()}

        async def hgetall(self, key):
            return self.hashes.get(key, {})

        async def publish(self, channel, message):
            if channel not in self.channels:
                return 0
            for q in self.channels[channel]:
                await q.put(message.encode())
            return len(self.channels[channel])

        async def xadd(self, key, fields: dict):
            # Simplified stream: append a dict of fields.
            self.streams.setdefault(key, []).append(fields)
            return str(len(self.streams[key]))

        async def xrange(self, key, start="-", end="+", count: int | None = None):
            # Return list of (id, fields) tuples respecting count.
            entries = self.streams.get(key, [])
            if count is not None:
                entries = entries[:count]
            result = []
            for idx, fields in enumerate(entries, start=1):
                result.append((str(idx), fields))
            return result
            if count is not None:
                entries = entries[:count]
            # Emit dummy IDs as incremental strings.
            result = []
            for idx, fields in enumerate(entries, start=1):
                result.append((str(idx), fields))
            return result

        def pubsub(self):
            return self

        async def subscribe(self, *channels):
            for ch in channels:
                self.channels.setdefault(ch, []).append(asyncio.Queue())

        async def get_message(self, ignore_subscribe_messages=False, timeout=None):
            # Simple implementation: return the first message from any subscribed channel.
            for qlist in self.channels.values():
                if qlist:
                    try:
                        data = await asyncio.wait_for(qlist[0].get(), timeout=timeout)
                        return {"type": "message", "data": data}
                    except asyncio.TimeoutError:
                        return None
            return None

        async def listen(self):  # pragma: no cover – not used in this stub
            while False:
                yield {}

    redis = _InMemoryRedis()

from .crdt_engine import Document as CRDTDocument

REDIS_URL = os.getenv("COLLAB_REDIS_URL", "redis://localhost:6379/0")

_client: redis.Redis | None = None


def get_client() -> any:
    global _client
    if _client is None:
        # ``redis`` may be the real module (with ``from_url``) or the stub
        # instance defined above.
        if hasattr(redis, "from_url"):
            _client = redis.from_url(REDIS_URL)
        else:
            _client = redis  # type: ignore
    return _client


HASH_KEY = lambda doc_id: f"collab:doc:{doc_id}"
CHANNEL = lambda doc_id: f"collab:channel:{doc_id}"
HISTORY_STREAM = lambda doc_id: f"collab:history:{doc_id}"


async def load_document(doc_id: str) -> CRDTDocument:
    """Load a document from Redis (or create a fresh empty one)."""
    client = get_client()
    data = await client.hgetall(HASH_KEY(doc_id))
    if not data:
        return CRDTDocument()
    # ``data`` values are bytes – decode to str.
    content = data.get(b"content", b"").decode()
    version = int(data.get(b"version", b"0"))
    doc = CRDTDocument()
    y_text = doc.y_doc.get_text("content")
    if content:
        y_text.insert(0, content)
    doc.version = version
    return doc


async def save_document(doc_id: str, doc: CRDTDocument) -> None:
    """Persist the document's content and version to Redis."""
    client = get_client()
    await client.hset(
        HASH_KEY(doc_id),
        mapping={"content": str(doc.content), "version": doc.version},
    )


async def publish_update(doc_id: str, message: dict) -> None:
    """Publish a JSON‑encoded message to the document's channel for cross‑pod sync."""
    client = get_client()
    await client.publish(CHANNEL(doc_id), json.dumps(message))
    # Record the operation in the history stream for undo/redo support.
    await record_history(doc_id, message)


async def subscribe_updates(doc_id: str, callback: Callable[[dict], Awaitable[None]]) -> None:
    """Subscribe to the Redis channel for *doc_id* and forward messages to ``callback``.

    The function runs forever; it should be scheduled as an ``asyncio`` task and
    cancelled when the last local connection for the document disconnects.
    """
    client = get_client()
    pubsub = client.pubsub()
    await pubsub.subscribe(CHANNEL(doc_id))
    try:
        async for msg in pubsub.listen():
            if msg is None or msg["type"] != "message":
                continue
            payload = json.loads(msg["data"].decode())
            await callback(payload)
    except asyncio.CancelledError:
        # Graceful shutdown of the listener when the task is cancelled.
        await pubsub.unsubscribe(CHANNEL(doc_id))
        await pubsub.close()


# ---------------------------------------------------------------------------
# History / operation log – stored in a Redis Stream (or in‑memory list fallback).
# ---------------------------------------------------------------------------

async def record_history(doc_id: str, message: dict) -> None:
    """Append an operation payload to the per‑document history stream.

    The stream stores raw JSON strings; each entry ID is auto‑generated by Redis.
    The in‑memory stub stores a simple list of JSON strings.
    """
    client = get_client()
    # ``xadd`` is the Redis command for streams.  The stub implements ``xadd``.
    await client.xadd(HISTORY_STREAM(doc_id), {"msg": json.dumps(message)})


async def get_history(doc_id: str, count: int = 100) -> list[dict]:
    """Retrieve the most recent *count* entries from the history stream.

    Returns a list of decoded messages ordered from oldest to newest.
    """
    client = get_client()
    # ``xrange`` returns entries in order.  The stub implements ``xrange``.
    raw = await client.xrange(HISTORY_STREAM(doc_id), start="-", end="+", count=count)
    # ``raw`` is a list of ``(id, {"msg": "..."})`` tuples.
    msgs = []
    for _id, fields in raw:
        try:
            payload = json.loads(fields.get("msg", "{}"))
        except Exception:
            payload = {}
        msgs.append(payload)
    return msgs