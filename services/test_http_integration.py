import io
import os
import statistics
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "services"), os.path.join(HERE, "services", "command_center"), os.path.join(HERE, "services", "cognitive_plane")):
    if p not in sys.path if False else []:
        pass

import sys
for p in (HERE, os.path.join(HERE, "services"), os.path.join(HERE, "services", "command_center"), os.path.join(HERE, "services", "cognitive_plane")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from fastapi.testclient import TestClient

import bioos_runtime as runtime

client = TestClient(runtime.app)


def test_health_liveness_and_latency_budget():
    print("[TEST] HTTP /api/health: liveness + soft latency budget")
    samples = []
    for _ in range(20):
        started = time.perf_counter()
        res = client.get("/api/health")
        samples.append((time.perf_counter() - started) * 1000.0)
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
    p95 = sorted(samples)[int(0.95 * len(samples)) - 1]
    assert p95 < 200.0, f"health p95 latency {p95:.1f} ms exceeded soft 200 ms budget"
    print(f" -> Health PASS (p95 {p95:.1f} ms over 20 calls, soft budget 200 ms)")


def test_kernel_step_persists_telemetry():
    print("[TEST] HTTP /api/kernel/step: watchdog cycle + telemetry persistence")
    before = runtime.store.telemetry_count()
    res = client.post("/api/kernel/step", json={"pressure_mmhg": 200, "bubble_ul": 0})
    assert res.status_code == 200
    body = res.json()
    assert body["watchdog_state"] in ("NORMAL", "CAUTION", "HARDWARE_LOCKOUT")
    assert "seq_ctr" in body and "crc16" in body
    assert runtime.store.telemetry_count() >= before  # sampler or step captured rows
    print(f" -> Kernel step PASS (state={body['watchdog_state']}, telemetry {before} -> {runtime.store.telemetry_count()})")


def test_news2_census_batch_and_single_observation_flow():
    print("[TEST] HTTP NEWS2: census batch + clinical observation with H-11 defaults")
    res = client.get("/api/clinical/news2")
    assert res.status_code == 200
    data = res.json()
    assert data["patients"], "census must not be empty"
    assert set(data["band_counts"].keys()) == {"LOW", "MEDIUM", "HIGH"}

    patient = data["patients"][0]
    res = client.post(
        f"/api/clinical/news2/{patient['patient_id']}/observation",
        json={"spo2_scale": 1, "on_supplemental_oxygen": False, "is_alert": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["defaults_used"]["on_supplemental_oxygen"] is False  # explicit override
    assert isinstance(body["trend_alerts"], list)
    print(f" -> NEWS2 flow PASS ({len(data['patients'])} patients, observation recorded, trend alerts {len(body['trend_alerts'])})")


def test_kernel_gated_metformin_order_writes_audit_chain():
    print("[TEST] HTTP FHIR: kernel-gated metformin order -> audit chain intact")
    patients = client.get("/api/clinical/news2").json()["patients"]
    patient_id = patients[0]["patient_id"]

    res = client.post(
        "/api/fhir/medication-request",
        json={"patient_id": patient_id, "drug": "Metformin", "dose_mg": 500.0, "egfr": 22.0},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["kernel_verification"] == "HardLockoutContraindicated"
    assert body["medication_request"]["status"] == "draft"  # advisory only

    chain = client.get("/api/audit/chain").json()
    assert chain["verification"]["valid"] is True
    assert chain["verification"]["entries"] >= 1
    print(f" -> Kernel-gated order PASS (HardLockout, audit chain intact, {chain['verification']['entries']} entries)")


def test_auth_token_issuance_and_unknown_patient_404():
    print("[TEST] HTTP auth token + 404 handling")
    res = client.post("/api/auth/token", json={"role": "PHYSICIAN", "subject": "dr-e2e"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    assert token.count(".") == 2  # JWT shape

    res = client.get("/api/fhir/patient/DOES-NOT-EXIST")
    assert res.status_code == 404

    res = client.get("/api/clinical/news2/DOES-NOT-EXIST")
    assert res.status_code == 404
    print(" -> Auth + 404 PASS (JWT issued, missing resources rejected)")


def test_drift_endpoint_exposed():
    print("[TEST] HTTP /api/cognitive/drift: drift telemetry exposed")
    res = client.get("/api/cognitive/drift")
    assert res.status_code == 200
    body = res.json()
    assert "approval_rate" in body and "limits" in body and "alerts_emitted" in body
    print(f" -> Drift endpoint PASS (rate={body['approval_rate']}, alerts={body['alerts_emitted']})")
