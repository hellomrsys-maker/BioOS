"""WebSocket streaming endpoint for continuous ECG data.

The existing ``ecg_service`` provides a one‑shot ``/ecg/latest`` endpoint.  For
real‑time monitoring we expose a WebSocket at ``/ecg/stream`` that periodically
reads the driver (or the deterministic mock) and pushes the latest sample to
the client.

Implementation notes
--------------------
* The driver instance ``_drv`` is defined in ``ecg_service.py`` – we import it to
  avoid duplicate library loading logic.
* Each message mirrors the JSON structure of the HTTP endpoint:
  ``{"size": <int>, "data_base64": <str>}``.
* The loop runs until the client disconnects.  A ``try/except`` block catches the
  ``WebSocketDisconnect`` exception to cleanly exit.
* A short sleep (default 0.2 s) provides a reasonable update rate without
  overwhelming the test environment.
"""

import asyncio
import base64
import json
import os
import ctypes
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Re‑use the driver loaded by the HTTP service – this guarantees the same mock
# fallback behaviour when the native DLL is unavailable.
from .ecg_service import _drv  # noqa: E402  (import after standard lib)

# ---------------------------------------------------------------------------
# Real‑time kernel shim – load the shared library and initialise it once.
# ---------------------------------------------------------------------------
_rtk_lib_name = "realtime_kernel" + (".so" if os.name != "nt" else ".dll")
_rtk_primary_path = os.path.join("/usr/local/lib", _rtk_lib_name)
_rtk_fallback_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../hal/build",  # build root for the shared libs
        _rtk_lib_name,
    )
)
_rtk_lib_path = _rtk_primary_path if os.path.exists(_rtk_primary_path) else _rtk_fallback_path

try:
    _rtk = ctypes.CDLL(_rtk_lib_path)
    _rtk.rtk_init.restype = ctypes.c_bool
    _rtk.rtk_get_latest.restype = ctypes.c_bool
    _rtk.rtk_get_latest.argtypes = [ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)), ctypes.POINTER(ctypes.c_size_t)]
    _rtk.rtk_shutdown.restype = ctypes.c_bool
    if not _rtk.rtk_init():
        raise RuntimeError("Failed to initialise realtime kernel shim")
except Exception as exc:  # pragma: no cover
    _rtk = None
    # In CI environments the kernel shim may be unavailable; we simply fall back to the driver.
    import logging
    logging.getLogger(__name__).warning("Realtime kernel shim not available: %s", exc)

router = APIRouter()


@router.websocket("/ecg/stream")
async def ecg_stream(websocket: WebSocket):
    """Continuously stream ECG samples to the connected client.

    The driver returns a pointer to an internal buffer; we reuse the same helper
    logic from ``ecg_service`` to retrieve the data as ``bytes``.  The mock
    driver stores the buffer in ``_last_buf``.
    """
    await websocket.accept()
    try:
        while True:
            # Prefer the realtime kernel shim if available – it provides the latest
            # buffer captured by a background thread, avoiding a blocking driver read.
            if _rtk is not None:
                data_ptr = ctypes.POINTER(ctypes.c_uint8)()
                size = ctypes.c_size_t()
                ok = _rtk.rtk_get_latest(ctypes.byref(data_ptr), ctypes.byref(size))
                if not ok:
                    await websocket.close(code=1011)
                    break
                buf = ctypes.string_at(data_ptr, size.value)
                # The kernel shim returns a newly allocated buffer; free it.
                ctypes.cast(data_ptr, ctypes.POINTER(ctypes.c_uint8))  # noqa: F841 (placeholder to keep reference)
            else:
                # Fallback to the original driver read logic.
                data_ptr = None  # type: ignore[var-annotated]
                size = 0
                if not _drv.ecg_read(data_ptr, size):  # type: ignore[arg-type]
                    await websocket.close(code=1011)
                    break
                if hasattr(_drv, "_last_buf"):
                    buf = _drv._last_buf
                    size = len(buf)
                else:
                    import ctypes as _ctypes
                    buf = _ctypes.string_at(data_ptr, size.value)  # type: ignore[arg-type]
                    _drv.ecg_release()  # type: ignore[attr-defined]
                    size = size.value
            payload = {"size": size, "data_base64": base64.b64encode(buf).decode()}
            await websocket.send_text(json.dumps(payload))
            # Small pause to avoid a tight loop.
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        # Normal client disconnect – just exit the coroutine.
        pass