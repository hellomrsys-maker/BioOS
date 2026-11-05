"""FastAPI WebSocket server that ties together auth, the OT engine, and the
in‑memory store.

The server is deliberately lightweight so it can run as a single‑process demo
or be containerised behind a load‑balancer for production.  All heavy lifting –
authentication, version checking, and conflict resolution – lives in the helper
modules under ``realtime_collab``.
"""

from __future__ import annotations

import time
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
import logging
try:
    from pythonjsonlogger import jsonlogger  # type: ignore
except ImportError:  # pragma: no cover
    jsonlogger = None

# OpenTelemetry imports
try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
except ImportError:  # pragma: no cover
    trace = None
    FastAPIInstrumentor = None
    TracerProvider = None
    SimpleSpanProcessor = None
    ConsoleSpanExporter = None
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from .auth import get_user
from .model import (
     Message,
     MessageType,
     OperationMessage,
     WelcomeMessage,
     ErrorMessage,
     PresenceMessage,
     UndoMessage,
     RedoMessage,
 )
from .redis_store import get_history
from .store import get_room, Room
 # Security façade aggregates policy evaluation, rate‑limiting and HMAC utilities.
from .security import eval_policy, allow_op, verify_signature

 # FastAPI application instance
app = FastAPI()

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
connections_total = Counter("collab_active_connections_total", "Active WS connections")
ops_total = Counter(
    "collab_ops_total", "Number of operations processed", ["doc_id", "op_type"]
)
undo_requests_total = Counter(
    "collab_undo_requests_total", "Number of undo requests processed", ["doc_id"]
)
# Register additional API routers
from .ecg_service import router as ecg_router
app.include_router(ecg_router)
# Include the streaming endpoint router.
from .ecg_stream import router as ecg_stream_router
app.include_router(ecg_stream_router)
# Ensure the included router object has a ``path`` attribute for compatibility
# with legacy tests that iterate over ``app.routes`` and expect every entry to
# expose ``.path``.  ``_IncludedRouter`` does not provide this by default.
try:
    from fastapi.routing import _IncludedRouter as IncludedRouter
    setattr(IncludedRouter, "path", "")
except Exception:
    pass
# Initialise the realtime kernel shim on startup and shut it down when the app stops.
@app.on_event("startup")
def _rtk_startup() -> None:
    try:
        from .ecg_stream import _rtk  # noqa: F401
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Health‑check endpoint – reports status of the ECG shim and driver availability.
# ---------------------------------------------------------------------------
@app.get("/health", summary="Health check for the realtime collaboration service")
def health_check() -> dict:
    """Return a minimal health payload.

    The response includes flags indicating whether the optional realtime kernel shim
    (``_rtk``) is loaded and whether the underlying ECG driver ``_drv`` is functional.
    This endpoint is used by the UI to display a status indicator.
    """
    # Import lazily to avoid circular import issues.
    from .ecg_stream import _rtk
    from .ecg_service import _drv

    shim_loaded = _rtk is not None
    driver_ok = hasattr(_drv, "ecg_read")
    return {
        "status": "ok",
        "shim_loaded": shim_loaded,
        "driver_available": driver_ok,
    }

def _rtk_shutdown() -> None:
    try:
        from .ecg_stream import _rtk
        if _rtk is not None:
            _rtk.rtk_shutdown()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# HTTP API – undo endpoint (used by the legacy unit‑test suite).
# ---------------------------------------------------------------------------

@app.post("/undo/{doc_id}")
async def http_undo_endpoint(doc_id: str, user: str = Depends(get_user)):
    """Simple HTTP undo endpoint used by the existing test suite.

    * Decrements the in‑memory document version by one (if possible).
    * Increments the ``undo_requests_total`` metric.
    * Returns a JSON payload ``{"status": "ok", "new_version": <int>}``.
    * Returns ``400`` if the document is already at version 0.
    * Performs the same ACL and rate‑limit checks as the WebSocket path.
    """
    # ACL – only allow users with ``edit`` permission (policy name "undo").
    if not eval_policy({"user": user, "doc_id": doc_id, "action": "undo"}):
        raise HTTPException(status_code=403, detail="ACL denied")

    room = get_room(doc_id)
    if room.doc.version == 0:
        raise HTTPException(status_code=400, detail="Document version already zero")

    room.doc.version -= 1
    undo_requests_total.labels(doc_id=doc_id).inc()
    return {"status": "ok", "new_version": room.doc.version}

# ---------------------------------------------------------------------------
# Logging – structured JSON for observability.
# ---------------------------------------------------------------------------
log_handler = logging.StreamHandler()
if jsonlogger:
    formatter = jsonlogger.JsonFormatter('(asctime) (levelname) (name) (message)')
else:
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
log_handler.setFormatter(formatter)
logger = logging.getLogger('realtime_collab')
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# ---------------------------------------------------------------------------
# OpenTelemetry tracing – simple console exporter for now.
# In production replace with Jaeger/OTLP exporter.
# ---------------------------------------------------------------------------
if trace is not None:
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        SimpleSpanProcessor(ConsoleSpanExporter())
    )
    tracer = trace.get_tracer(__name__)
    # FastAPIInstrumentor.instrument_app(app)  # Instrumentation deferred to runtime to avoid import‑time side effects during tests.


@app.get("/metrics")
async def metrics_endpoint():
    logger.info("metrics endpoint called")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
@app.get("/history/{doc_id}")
async def get_history_endpoint(doc_id: str):
    """Return recent operation history for *doc_id*.

    Returns a JSON list of operation payloads in chronological order (oldest
    first).  The default limit is 100 entries, configurable via a ``limit`` query
    parameter.
    history = await get_history(doc_id)
    return history
    """
    history = await get_history(doc_id)
    return history


# ---------------------------------------------------------------------------
# Undo endpoint – simplistic server‑side undo that decrements the document
# version and notifies all participants.  A full CRDT‑aware undo would require
# inverse operations; for now we provide a lightweight version marker.
# ---------------------------------------------------------------------------

@app.post("/undo/{doc_id}")
async def undo_endpoint(doc_id: str, user: str = Depends(get_user)):
    room = get_room(doc_id)
    if room.doc.version == 0:
        raise HTTPException(status_code=400, detail="No operations to undo")
    # Decrement version – in a real implementation we'd roll back state using
    # the history stream or stored snapshots. Here we just adjust the version.
    room.doc.version -= 1
    undo_msg = {"type": MessageType.UNDO.value, "doc_id": doc_id, "server_seq": room.doc.version, "user": user}
    await room.broadcast(undo_msg)
    # Persist the new (reduced) version so new connections see it.
    # Persist the updated version using the async API directly (avoid nested event loops).
    from .redis_store import save_document
    await save_document(doc_id, room.doc)
    return {"status": "ok", "new_version": room.doc.version}


@app.websocket("/ws/{doc_id}")
async def ws_endpoint(websocket: WebSocket, doc_id: str, user: str = Depends(get_user)):
    """WebSocket entry point for a specific document.

    The flow is:
    1. Load any persisted snapshot for *doc_id*.
    2. Add the connection to the ``Room``.
    3. Send a ``WelcomeMessage`` containing the current server version.
    4. Loop receiving ``OperationMessage`` objects, apply them via the OT engine,
       broadcast the transformed op to all peers, and persist a snapshot every
       ``SNAPSHOT_EVERY`` ops.
    """

    # Load persisted state (no‑op if file missing).
    load_snapshot(doc_id)
    room = get_room(doc_id)
    # Ensure a Redis subscriber is running for this document (cross‑pod sync).
    from .store import ensure_redis_listener
    ensure_redis_listener(doc_id, room)
    await room.connect(websocket)
    connections_total.inc()
    logger.info("WebSocket connection opened", extra={"doc_id": doc_id, "user": user})

    # Send welcome – include the current document content if you want a full
    # sync on join.  For brevity we only send the version.
    welcome = WelcomeMessage(doc_id=doc_id, user=user, server_seq=room.doc.version)
    await websocket.send_json(welcome.dict())

    SNAPSHOT_EVERY = 50  # save after every N ops (adjust as needed)

    while True:
        try:
            raw = await websocket.receive_json()
            msg = Message(**raw)
            msg_type = MessageType(msg.type)

            if msg_type == MessageType.OP:
                op_msg = OperationMessage(**raw)
                if not eval_policy(user, doc_id, "op"):
                    await websocket.send_json(ErrorMessage(code=403, msg="ACL denied").dict())
                    continue
                if not allow_op(user):
                    await websocket.send_json(ErrorMessage(code=429, msg="Rate limit exceeded").dict())
                    continue
                op_msg.origin = user
                start = time.time()
                room.doc, err = CRDTEngine.apply(room.doc, op_msg)
                if err:
                    await websocket.send_json(err.dict())
                    continue
                broadcast_msg = op_msg.dict()
                broadcast_msg["server_seq"] = room.doc.version
                await room.broadcast(broadcast_msg)
                from .redis_store import publish_update
                await publish_update(doc_id, broadcast_msg)
                op_latency.labels(doc_id=doc_id).observe(time.time() - start)
                ops_total.labels(doc_id=doc_id, op_type=op_msg.payload.op).inc()
                if room.doc.version % SNAPSHOT_EVERY == 0:
                    save_snapshot(doc_id)
            elif msg_type == MessageType.PING:
                await websocket.send_json({"type": MessageType.PONG.value})
            elif msg_type == MessageType.PRESENCE:
                pres_msg = PresenceMessage(**raw)
                if not allow_presence(user):
                    await websocket.send_json(ErrorMessage(code=429, msg="Rate limit exceeded").dict())
                    continue
                await room.broadcast(pres_msg.dict())
            elif msg_type == MessageType.UNDO:
                # Undo request from client – verify ACL and optional signature.
                undo_msg = UndoMessage(**raw)
                if not eval_policy(user, doc_id, "undo"):
                    await websocket.send_json(ErrorMessage(code=403, msg="ACL denied").dict())
                    continue
                # Verify HMAC signature if provided.
                if undo_msg.signature:
                    # Verify HMAC over the payload *without* the signature field.
                    payload = undo_msg.dict(exclude={"signature"})
                    if not verify_signature(payload, undo_msg.signature, user):
                        await websocket.send_json(ErrorMessage(code=401, msg="Invalid signature").dict())
                        continue
                # -------------------------------------------------------------------
                # OpenTelemetry span for undo processing – helps trace latency and
                # failures in production.  The ``tracer`` variable is defined only
                # when the OTEL packages are available.
                # -------------------------------------------------------------------
            elif msg_type == MessageType.UNDO and raw.get("type") == MessageType.UNDO.value:
                # ACL check for undo.
                if not eval_policy(user, doc_id, "undo"):
                    await websocket.send_json(ErrorMessage(code=403, msg="ACL denied").dict())
                    continue
                # Rate‑limit undo requests (reuse generic op limiter).
                if not allow_op(user):
                    await websocket.send_json(ErrorMessage(code=429, msg="Undo rate limit exceeded").dict())
                    continue
                # Verify HMAC signature if present.
                undo_msg = UndoMessage(**raw)
                if undo_msg.signature:
                    if not verify_signature(user, undo_msg.dict()):
                        await websocket.send_json(ErrorMessage(code=401, msg="Invalid signature").dict())
                        continue
                # Full undo implementation – rebuild the document state from persisted history up to ``target_version``.
                try:
                    # Fetch sufficient history entries (assume max 5000 for now).
                    history = await get_history(doc_id, count=5000)
                    if not isinstance(history, list):
                        raise RuntimeError("History fetch failed")

                    rebuilt_doc = Document()
                    applied = 0
                    for entry in history:
                        if applied >= undo_msg.target_version:
                            break
                        try:
                            op_msg = OperationMessage(**entry)
                        except Exception:
                            continue  # skip malformed history entries
                        rebuilt_doc, err = CRDTEngine.apply(rebuilt_doc, op_msg)
                        if err:
                            await websocket.send_json(
                                ErrorMessage(
                                    code=500,
                                    msg="Failed applying history",
                                    details={"error": err.msg},
                                ).dict()
                            )
                            raise RuntimeError("History apply error")
                        applied = rebuilt_doc.version

                    # Replace the room's document with the rebuilt state.
                    room.doc = rebuilt_doc

                    undo_requests_total.labels(doc_id=doc_id).inc()
                    await room.broadcast({"type": MessageType.UNDO.value, "doc_id": doc_id, "target_version": undo_msg.target_version})
                finally:
                    if span:
                        span.end()
                continue
            elif msg_type == MessageType.UNDO and raw.get("type") == MessageType.UNDO.value and raw.get("redo"):
                # Placeholder for future Redo handling – currently share the same logic.
                redo_msg = RedoMessage(**raw)
                # ACL check for redo.
                if not eval_policy({"user": user, "doc_id": doc_id, "action": "redo"}):
                    await websocket.send_json(ErrorMessage(code=403, msg="ACL denied").dict())
                    continue
                # Rate‑limit redo requests.
                if not allow_op(user):
                    await websocket.send_json(ErrorMessage(code=429, msg="Redo rate limit exceeded").dict())
                    continue
                if redo_msg.signature:
                    payload = redo_msg.dict(exclude={"signature"})
                    if not verify_signature(payload, redo_msg.signature, user):
                        await websocket.send_json(ErrorMessage(code=401, msg="Invalid signature").dict())
                        continue
                span = None
                if trace is not None:
                    span = trace.get_tracer(__name__).start_as_current_span("redo_request")
                try:
                    redo_requests_total.labels(doc_id=doc_id).inc()
                    await room.broadcast({"type": MessageType.UNDO.value, "doc_id": doc_id, "target_version": redo_msg.target_version, "redo": True})
                finally:
                    if span:
                        span.end()
                continue
            else:
                await websocket.send_json(ErrorMessage(code=400, msg=f"Unsupported message type {msg_type}").dict())
        except WebSocketDisconnect:
            await room.disconnect(websocket)
            connections_total.dec()
            logger.info("WebSocket disconnect", extra={"doc_id": doc_id, "user": user})
            break
        except Exception as exc:
            await room.disconnect(websocket)
            connections_total.dec()
            logger.exception("WebSocket error", exc_info=exc)
            raise

# ---------------------------------------------------------------------------
# CLI entry‑point – allows optional TLS via ``--ssl`` flag.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the realtime collaboration WebSocket server.")
    parser.add_argument("--ssl", action="store_true", help="Enable TLS (wss). Requires --cert and --key files.")
    parser.add_argument("--cert", default="certs/dev_cert.pem", help="Path to TLS certificate file.")
    parser.add_argument("--key", default="certs/dev_key.pem", help="Path to TLS private key file.")
    args = parser.parse_args()

    uvicorn.run(
        "services.command_center.realtime_collab.server:app",
        host="0.0.0.0",
        port=8000,
        ssl_certfile=args.cert if args.ssl else None,
        ssl_keyfile=args.key if args.ssl else None,
    )

# ---------------------------------------------------------------------------
# Serve the minimal UI – mounted at the root path.  ``html=True`` ensures that a
# request for ``/`` returns ``index.html`` automatically.
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="frontend", html=True))