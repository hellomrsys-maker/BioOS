"""A tiny operational‑transformation (OT) engine for plain‑text documents.

The engine stores a ``Document`` (a ``str``) and a monotonically increasing
``version`` number.  Clients send an ``OperationMessage`` containing a client
sequence number.  The server checks that ``client_seq`` equals the current version;
if it does, the operation is applied and the version is incremented.  If the
client is out‑of‑sync the server returns an ``ErrorMessage`` asking the client to
resync.

This implementation is deliberately simple – it works for the unit‑tests and
demonstrates the overall architecture.  For production you would replace the
``apply`` method with a full CRDT library (Yjs, Automerge, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .model import OperationPayload, OperationMessage, ErrorMessage


@dataclass
class Document:
    """Container for a mutable text document.

    Attributes
    ----------
    content: str
        The current text of the document.
    version: int
        Incremented after every successful operation.  Starts at ``0``.
    """

    content: str = ""
    version: int = 0

    def insert(self, pos: int, text: str) -> None:
        self.content = self.content[:pos] + text + self.content[pos:]

    def delete(self, pos: int, length: int) -> None:
        self.content = self.content[:pos] + self.content[pos + length :]


class OTEngine:
    """Very small OT engine.

    The public API is ``apply`` which receives an ``OperationMessage`` and the
    current ``Document``.  It returns either ``(new_doc, None)`` on success or
    ``(doc, ErrorMessage)`` on failure (e.g. version mismatch).
    """

    @staticmethod
    def apply(doc: Document, op_msg: OperationMessage) -> Tuple[Document, ErrorMessage | None]:
        # Validate client sequence against server version.
        if op_msg.client_seq != doc.version:
            err = ErrorMessage(
                code=409,
                msg="Version mismatch – client out of sync",
                details={"expected": doc.version, "got": op_msg.client_seq},
            )
            return doc, err

        payload: OperationPayload = op_msg.payload
        # Basic bounds checking – keep the engine robust.
        if payload.pos < 0 or payload.pos > len(doc.content):
            err = ErrorMessage(code=400, msg="Invalid position", details={"pos": payload.pos})
            return doc, err

        if payload.op == "insert":
            assert payload.text is not None
            doc.insert(payload.pos, payload.text)
        elif payload.op == "delete":
            assert payload.length is not None
            if payload.pos + payload.length > len(doc.content):
                err = ErrorMessage(
                    code=400,
                    msg="Delete exceeds document length",
                    details={"pos": payload.pos, "length": payload.length, "doc_len": len(doc.content)},
                )
                return doc, err
            doc.delete(payload.pos, payload.length)
        else:
            # Should never happen because of Pydantic validation.
            err = ErrorMessage(code=400, msg="Unsupported operation", details={"op": payload.op})
            return doc, err

        # Successful transformation – bump version.
        doc.version += 1
        return doc, None
