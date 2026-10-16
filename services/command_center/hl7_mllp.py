# -*- coding: utf-8 -*-
"""
BioOS HL7 v2 MLLP Listener (stub)
Standard: HL7 v2.x over MLLP (Minimal Lower Layer Protocol, ITU-T X.2xx framing)

Frame format:  <VT=0x0B>  HL7-message  <FS=0x1C>  <CR=0x0D>

STUB SCOPE (P1 close-out item):
- Receives ADT/ORU-style messages, parses minimal MSH/PID fields
- Writes every receipt to the hash-chained audit store (via runtime callback)
- Answers MSA|AA acknowledgements
- NO clinical action is derived from HL7 input in this stub (advisory only)

Enable with BIOOS_MLLP_PORT=<port> (disabled by default).
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

VT = 0x0B  # Start-of-frame (Vertical Tab)
FS = 0x1C  # End-of-message (File Separator)
CR = 0x0D  # Frame terminator (Carriage Return)

MessageHandler = Callable[[Dict[str, Any], str], None]


def frame_message(payload: Any) -> bytes:
    """Wraps an HL7 message string/bytes in MLLP framing."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return bytes([VT]) + payload + bytes([FS, CR])


def extract_frames(buffer: bytes) -> Tuple[List[bytes], bytes]:
    """Pops every complete MLLP frame from a stream buffer.

    Returns (complete_message_payloads, remaining_buffer). Incomplete frames
    stay buffered until more bytes arrive."""
    messages: List[bytes] = []
    while True:
        start = buffer.find(bytes([VT]))
        if start == -1:
            break
        end = buffer.find(bytes([FS]), start + 1)
        if end == -1:
            break
        messages.append(buffer[start + 1:end])
        # Consume FS plus the CR terminator when present
        if end + 1 < len(buffer) and buffer[end + 1] == CR:
            buffer = buffer[end + 2:]
        else:
            buffer = buffer[end + 1:]
    return messages, buffer


def parse_hl7(message: str) -> Dict[str, Any]:
    """Minimal HL7 v2 parse: MSH-3/9/10 and PID-3 only (stub scope)."""
    segments = [s for s in message.replace("\n", "\r").split("\r") if s.strip()]
    parsed: Dict[str, Any] = {
        "message_type": None,
        "trigger_event": None,
        "control_id": None,
        "sending_app": None,
        "patient_id": None,
        "segment_count": len(segments),
    }
    for seg in segments:
        fields = seg.split("|")
        if fields[0] == "MSH" and len(fields) > 9:
            # MSH-1 is the field separator itself; MSH-2 = encoding characters.
            parsed["sending_app"] = fields[2] or None
            raw_type = fields[8] or ""
            parsed["control_id"] = fields[9] or None
            if "^" in raw_type:
                parts = raw_type.split("^")
                parsed["message_type"] = parts[0] or None
                parsed["trigger_event"] = parts[1] if len(parts) > 1 else None
            else:
                parsed["message_type"] = raw_type or None
        elif fields[0] == "PID" and len(fields) > 3:
            first_id = fields[3].split("^")[0]
            parsed["patient_id"] = first_id or None
    return parsed

def build_ack(
    parsed: Dict[str, Any],
    sending_app: str = "BIOOS",
    sending_facility: str = "BIOOS_HOSPITAL",
) -> str:
    """Builds an HL7 v2 ACK (MSA|AA) for the received message."""
    ts = time.strftime("%Y%m%d%H%M%S")
    trigger = parsed.get("trigger_event")
    msh9 = f"ACK^{trigger}" if trigger else "ACK"
    msh = (
        f"MSH|^~\\&|{sending_app}|{sending_facility}|"
        f"{parsed.get('sending_app') or ''}|{parsed.get('sending_app') or ''}|"
        f"{ts}||{msh9}|ACK-{uuid.uuid4().hex[:12]}|P|2.4"
    )
    msa = f"MSA|AA|{parsed.get('control_id') or 'UNKNOWN'}"
    return msh + "\r" + msa + "\r"


class MllpAuditServer:
    """Asyncio MLLP TCP server: frames -> parse -> handler callback -> ACK."""

    def __init__(
        self,
        port: int,
        host: str = "127.0.0.1",
        on_message: Optional[MessageHandler] = None,
    ):
        self.host = host
        self.requested_port = port
        self.port = port  # resolved after bind (port 0 = ephemeral, for tests)
        self.on_message = on_message
        self.messages_received = 0
        self._server: Optional[asyncio.AbstractServer] = None

    async def serve(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.requested_port
        )
        self.port = self._server.sockets[0].getsockname()[1]
        async with self._server:
            try:
                await self._server.serve_forever()
            except asyncio.CancelledError:
                pass  # clean shutdown requested via stop(); not an error

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        buffer = b""
        try:
            while not reader.at_eof():
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                frames, buffer = extract_frames(buffer)
                for raw in frames:
                    self.messages_received += 1
                    text = raw.decode("utf-8", errors="replace")
                    parsed = parse_hl7(text)
                    if self.on_message is not None:
                        try:
                            self.on_message(parsed, text)
                        except Exception as exc:  # handler errors must not kill the link
                            print(f"[BioOS MLLP] handler error: {exc}")
                    writer.write(frame_message(build_ack(parsed)))
                    await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass  # abrupt client disconnect is normal for hospital interfaces
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def run_blocking(self) -> None:
        """Blocking entry point for a dedicated daemon thread."""
        asyncio.run(self.serve())
