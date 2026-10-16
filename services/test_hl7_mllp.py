# -*- coding: utf-8 -*-
"""
HL7 v2 MLLP Stub Test Suite: framing, parsing, ACK, TCP roundtrip, audit trail.
Run: python -m pytest services/test_hl7_mllp.py -v
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "command_center")))

import pytest

from audit_store import BioOsPersistenceStore
from hl7_mllp import (
    build_ack,
    extract_frames,
    frame_message,
    parse_hl7,
    MllpAuditServer,
)

ADT_A01 = (
    "MSH|^~\\&|HIS|HOSPITAL|BIOOS|BIOOS_HOSPITAL|20261016120000||ADT^A01|MSG00001|P|2.4\r"
    "EVN|A01|20261016120000\r"
    "PID|1||PT-88219^^^MRN^MR||CHEN^SARAH||19800215|F\r"
)


def test_mllp_framing_and_stream_extraction():
    print("[TEST] MLLP framing + stream extraction...")
    framed = frame_message(ADT_A01)
    assert framed[0] == 0x0B and framed[-2] == 0x1C and framed[-1] == 0x0D

    # Two complete frames preceded by junk bytes, plus one trailing partial
    stream = b"junk" + framed + framed + framed[:7]
    frames, remainder = extract_frames(stream)
    assert len(frames) == 2
    assert frames[0].decode("utf-8") == ADT_A01
    # Junk before the first VT is consumed (resync); partial frame stays buffered
    assert remainder == framed[:7]
    print(" -> MLLP framing PASS (2 complete frames, partial buffered)")


def test_hl7_parse_and_ack():
    print("[TEST] HL7 v2 parse + MSA|AA acknowledgement...")
    parsed = parse_hl7(ADT_A01)
    assert parsed["message_type"] == "ADT"
    assert parsed["trigger_event"] == "A01"
    assert parsed["control_id"] == "MSG00001"
    assert parsed["patient_id"] == "PT-88219"
    assert parsed["sending_app"] == "HIS"

    ack = build_ack(parsed)
    assert ack.startswith("MSH|^~\\&|BIOOS|BIOOS_HOSPITAL|")
    assert "MSA|AA|MSG00001" in ack
    # The ACK itself must be a valid MLLP-frameable message
    frames, _ = extract_frames(frame_message(ack))
    assert frames[0].decode("utf-8") == ack
    print(" -> HL7 parse/ACK PASS (ADT^A01 -> MSA|AA|MSG00001)")


@pytest.mark.asyncio
async def test_mllp_tcp_roundtrip():
    print("[TEST] MLLP TCP roundtrip over loopback (ephemeral port)...")
    received = []
    server = MllpAuditServer(port=0, on_message=lambda p, r: received.append(p))
    task = asyncio.create_task(server.serve())
    # Deterministic bind-wait: under load the event loop may not have run the
    # serve() coroutine when the fixed sleep elapsed (observed as port == 0).
    for _ in range(200):
        if server.port != 0:
            break
        await asyncio.sleep(0.01)
    assert server.port != 0, "MLLP server failed to bind within 2 s"

    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    writer.write(frame_message(ADT_A01))
    await writer.drain()

    ack_raw = await asyncio.wait_for(reader.read(4096), timeout=3)
    frames, _ = extract_frames(ack_raw)
    assert b"MSA|AA|MSG00001" in frames[0]

    writer.close()
    await server.stop()  # unblocks serve_forever; serve() task then completes
    await asyncio.wait_for(task, timeout=3)
    assert len(received) == 1
    assert received[0]["control_id"] == "MSG00001"
    assert received[0]["patient_id"] == "PT-88219"
    print(" -> MLLP TCP roundtrip PASS (frame -> parse -> ACK MSA|AA)")


def test_mllp_receipt_lands_in_audit_chain(tmp_path):
    print("[TEST] HL7 receipt -> hash-chained audit store...")
    store = BioOsPersistenceStore(db_path=str(tmp_path / "mllp_audit.db"))
    parsed = parse_hl7(ADT_A01)
    store.append_audit_entry(
        actor="HL7_MLLP",
        action="HL7_MESSAGE_RECEIVED",
        resource_type=parsed["message_type"],
        resource_id=parsed["control_id"],
        payload={"patient_id": parsed["patient_id"], "trigger_event": parsed["trigger_event"]},
    )
    verdict = store.verify_audit_chain()
    assert verdict["valid"] is True and verdict["entries"] == 1
    print(" -> Audit integration PASS (HL7 receipt chained, verdict valid)")


if __name__ == "__main__":
    test_mllp_framing_and_stream_extraction()
    test_hl7_parse_and_ack()
    asyncio.run(test_mllp_tcp_roundtrip())
    test_mllp_receipt_lands_in_audit_chain(None)
    print("\nALL HL7 MLLP STUB TESTS PASSED!")
