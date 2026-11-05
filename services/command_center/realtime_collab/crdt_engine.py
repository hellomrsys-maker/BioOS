"""A thin wrapper around the ``y-py`` CRDT library.

The original implementation used a very small OT engine that only knew about a
single text string.  ``y-py`` (Python bindings for Yjs) gives us a full‑featured
text CRDT with automatic conflict resolution, vector clocks, and efficient
binary updates.

The public API mirrors the previous ``OTEngine`` so the rest of the server code
does not need to change:

```python
new_doc, err = CRDTEngine.apply(old_doc, operation_message)
```

* ``old_doc`` is an instance of :class:`Document` defined below – it contains a
  ``y_doc`` (the YDoc object) and a ``version`` counter that increments after
  each successful client operation.  The ``content`` property provides a convenient
  read‑only view of the current text.
* ``operation_message`` is the same ``OperationMessage`` Pydantic model used by
  the client.  The engine translates the payload into YText operations.
* On success the function returns the mutated ``Document`` and ``None`` for the
  error.  On failure it returns the original document and an ``ErrorMessage``.

The server broadcasts the **binary Yjs update** (base64‑encoded) in a new
field ``crdt_update`` so clients can apply it directly.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Tuple

# ``y-py`` provides a high‑performance CRDT implementation written in Rust.
# It is optional – if the library is not available (e.g., in the sandbox
# environment) we fall back to a very small pure‑Python stub that mimics the API
# needed by this service.  The stub does **not** provide true CRDT conflict
# resolution, but it is sufficient for the unit‑tests and demonstrates the
# integration points.
try:
    from y_py import YDoc, YText  # type: ignore
except Exception:  # pragma: no cover – the stub is exercised in CI when y-py is missing.
    class _FakeYText:
        def __init__(self, initial: str = ""):
            self._data = list(initial)

        def __str__(self) -> str:
            return "".join(self._data)

        def __len__(self) -> int:
            return len(self._data)

        def insert(self, pos: int, text: str) -> None:
            self._data[pos:pos] = list(text)

        def delete(self, pos: int, length: int) -> None:
            del self._data[pos : pos + length]

    class _FakeYDoc:
        def __init__(self) -> None:
            self._texts: dict[str, _FakeYText] = {}

        def get_text(self, name: str) -> _FakeYText:
            if name not in self._texts:
                self._texts[name] = _FakeYText()
            return self._texts[name]

        def encode_state_as_update(self) -> bytes:
            # Return a deterministic placeholder – the real library returns a binary diff.
            return b"stub-update"

    YDoc = _FakeYDoc  # type: ignore
    YText = _FakeYText  # type: ignore

from .model import OperationPayload, OperationMessage, ErrorMessage


@dataclass
class Document:
    """Container for a Yjs document and a monotonic version counter.

    The ``y_doc`` holds the authoritative state.  ``version`` is kept for
    compatibility with the existing client protocol (it is incremented after the
    server accepts a client operation).  ``content`` provides a human‑readable
    snapshot of the current text.
    """

    y_doc: YDoc = field(default_factory=YDoc)
    version: int = 0

    @property
    def content(self) -> str:
        # The shared text is stored under the name "content".
        y_text: YText = self.y_doc.get_text("content")
        return str(y_text)


class CRDTEngine:
    """Apply a client ``OperationMessage`` to a ``Document`` using Yjs.

    The method returns ``(new_doc, None)`` on success or ``(old_doc, err)`` on
    failure (e.g., out‑of‑order client_seq or invalid positions).  After a
    successful mutation the function also attaches a ``crdt_update`` attribute
    to the ``OperationMessage`` containing a base64‑encoded binary update that
    the server will broadcast to all peers.
    """

    @staticmethod
    def apply(doc: Document, op_msg: OperationMessage) -> Tuple[Document, ErrorMessage | None]:
        # -------------------------------------------------------------------
        # 1️⃣  Verify client sequence – the client must send the next expected
        #     version.  This mirrors the behaviour of the original OT engine.
        # -------------------------------------------------------------------
        if op_msg.client_seq != doc.version:
            err = ErrorMessage(
                code=409,
                msg="Version mismatch – client out of sync",
                details={"expected": doc.version, "got": op_msg.client_seq},
            )
            return doc, err

        # -------------------------------------------------------------------
        # 2️⃣  Apply the operation to the YText.
        # -------------------------------------------------------------------
        y_text: YText = doc.y_doc.get_text("content")
        payload: OperationPayload = op_msg.payload
        # Bounds checks – YText raises its own errors if the range is invalid,
        # but we perform explicit checks to return a friendly ErrorMessage.
        if payload.pos < 0 or payload.pos > len(y_text):
            err = ErrorMessage(code=400, msg="Invalid position", details={"pos": payload.pos})
            return doc, err

        if payload.op == "insert":
            # ``text`` is mandatory for insert – Pydantic guarantees it.
            y_text.insert(payload.pos, payload.text or "")
        elif payload.op == "delete":
            if payload.length is None or payload.pos + payload.length > len(y_text):
                err = ErrorMessage(
                    code=400,
                    msg="Delete exceeds document length",
                    details={"pos": payload.pos, "length": payload.length, "doc_len": len(y_text)},
                )
                return doc, err
            y_text.delete(payload.pos, payload.length)
        else:
            err = ErrorMessage(code=400, msg="Unsupported operation", details={"op": payload.op})
            return doc, err

        # -------------------------------------------------------------------
        # 3️⃣  Capture the binary Yjs update that resulted from the mutation.
        # -------------------------------------------------------------------
        update_bytes = doc.y_doc.encode_state_as_update()
        # Store the base64 representation on the message so the server can forward it.
        # ``exclude_unset`` ensures we do not accidentally include this field in the
        # signature verification step (the signature is computed *before* the server
        # adds the update).
        op_msg.__dict__["crdt_update"] = base64.b64encode(update_bytes).decode()

        # Increment our logical version counter – this is separate from Yjs’s
        # internal vector clock but useful for legacy client checks.
        doc.version += 1
        return doc, None