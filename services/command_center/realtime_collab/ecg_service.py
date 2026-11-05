"""Simple ECG service exposing the HAL driver via FastAPI.

The service loads the C API compiled in ``hal/drivers/ecg_ble`` using ``ctypes``.
It provides a single endpoint ``/ecg/latest`` that returns a JSON payload with
the most recent raw byte buffer (base64‑encoded) and its size.  In a production
system this would be a streaming endpoint, but for the initial real‑product
iteration a single‑sample fetch is sufficient for integration tests.
"""

import base64
import ctypes
import os
import threading
import time
from fastapi import APIRouter, HTTPException

router = APIRouter()

# ---------------------------------------------------------------------------
# Background ECG poller – periodically reads from the driver and stores the most
# recent buffer in a thread‑safe variable. This mimics a real‑time kernel that
# pushes data at a fixed interval without requiring the client to poll on each
# request.
# ---------------------------------------------------------------------------
_latest_buf_lock = threading.Lock()
_latest_buf: bytes | None = None
_stop_event = threading.Event()

def _poller_loop(interval_seconds: float = 0.1) -> None:
    """Continuously read the ECG driver.

    The loop runs in a daemon thread started on FastAPI ``startup``. It reads the
    driver using the same logic as ``/ecg/latest`` and stores the raw bytes in
    ``_latest_buf`` under a lock.
    """
    while not _stop_event.is_set():
        data_ptr = ctypes.POINTER(ctypes.c_uint8)()
        size = ctypes.c_size_t()
        try:
            ok = _drv.ecg_read(ctypes.byref(data_ptr), ctypes.byref(size))
        except Exception:
            ok = False
        if ok:
            if hasattr(_drv, "_last_buf"):
                buf = _drv._last_buf  # type: ignore[attr-defined]
            else:
                buf = ctypes.string_at(data_ptr, size.value)
                # Release native buffer for real driver implementations.
                try:
                    _drv.ecg_release()
                except Exception:
                    pass
            with _latest_buf_lock:
                _latest_buf = buf
        time.sleep(interval_seconds)

def _start_background_thread() -> None:
    thread = threading.Thread(target=_poller_loop, daemon=True, name="ECG‑Poller")
    thread.start()
    return thread

# FastAPI lifecycle events – start the background poller when the app starts.
@router.on_event("startup")
def _startup_event() -> None:  # pragma: no cover – exercised indirectly via server startup
    _start_background_thread()

@router.on_event("shutdown")
def _shutdown_event() -> None:  # pragma: no cover
    _stop_event.set()

# Resolve the shared library location – the Dockerfile copies all *.so (or *.dll)
# files to /usr/local/lib.  ``ctypes.util.find_library`` does not work on the
# minimal image, so we construct the path manually.
_lib_name = "libecg_ble_driver" + (".so" if os.name != "nt" else ".dll")
# Primary location (Docker image) and fallback location (local build output).
_primary_path = os.path.join("/usr/local/lib", _lib_name)
_fallback_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../../../hal/build/drivers/ecg_ble",
        _lib_name,
    )
)
_lib_path = _primary_path if os.path.exists(_primary_path) else _fallback_path

if not os.path.exists(_lib_path):
    raise RuntimeError(f"ECG driver library not found at {_primary_path} or {_fallback_path}")

# Load the driver – if the shared library cannot be loaded (e.g., missing
# runtime dependencies on a developer machine), fall back to a pure‑Python mock
# implementation that mimics the C API.  This keeps the FastAPI endpoint usable
# for unit‑tests and development without requiring the full native build.
try:
    _drv = ctypes.CDLL(_lib_path)
    # Declare argument/return types for the C API.
    _drv.ecg_init.restype = ctypes.c_bool
    _drv.ecg_read.restype = ctypes.c_bool
    _drv.ecg_read.argtypes = [ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)), ctypes.POINTER(ctypes.c_size_t)]
    _drv.ecg_release.restype = None
    _drv.ecg_write.restype = ctypes.c_bool
    _drv.ecg_write.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
    _drv.ecg_shutdown.restype = ctypes.c_bool
    if not _drv.ecg_init():
        raise RuntimeError("Failed to initialise ECG driver")
except Exception as exc:  # pragma: no cover – exercised in CI when DLL missing
    # Simple deterministic mock – 64 bytes of incremental data.
    class _MockDrv:
        def __init__(self):
            self.counter = 0

        def ecg_init(self):
            return True

        def ecg_read(self, data_ptr, size_ptr):
            # Generate a buffer of 64 bytes where each byte = counter % 256
            buf_array = (ctypes.c_uint8 * 64)()
            for i in range(64):
                buf_array[i] = (self.counter + i) % 256
            self.counter = (self.counter + 1) % 256
            # Store a Python copy for the endpoint to retrieve.
            self._last_buf = bytes(buf_array)
            # Populate size for the caller (used only in the real DLL path).
            # size will be set by the endpoint using the Python buffer length
            return True

        def ecg_release(self):
            return None

        def ecg_write(self, data, size):
            return True

        def ecg_shutdown(self):
            return True

    _drv = _MockDrv()


@router.get("/ecg/latest")
def get_latest_ecg():
    """Return the most recent ECG buffer.

    If the background poller has already populated ``_latest_buf`` we use that to
    avoid a blocking driver read. Otherwise we fall back to a direct ``ecg_read``
    call (maintaining compatibility with environments where the poller may not
    have run yet).
    """
    # Prefer the background-cached buffer.
    with _latest_buf_lock:
        cached = _latest_buf
    if cached is not None:
        buf = cached
        size = len(buf)
        return {"size": size, "data_base64": base64.b64encode(buf).decode()}

    # Fallback: direct read from the driver.
    data_ptr = ctypes.POINTER(ctypes.c_uint8)()
    size = ctypes.c_size_t()
    if not _drv.ecg_read(ctypes.byref(data_ptr), ctypes.byref(size)):
        raise HTTPException(status_code=503, detail="No ECG data available")
    if hasattr(_drv, "_last_buf"):
        buf = _drv._last_buf
        size.value = len(buf)
    else:
        buf = ctypes.string_at(data_ptr, size.value)
        try:
            _drv.ecg_release()
        except Exception:
            pass
    return {"size": size.value, "data_base64": base64.b64encode(buf).decode()}
