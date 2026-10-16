import io
import os
import tempfile

# Isolate the runtime store BEFORE importing the runtime daemon (it boots the
# whole stack at module level: kernel bridge, engines, sampler, trend hydration).
_TMP = tempfile.mkdtemp(prefix="bioos_api_test_")
os.environ["BIOOS_DB_PATH"] = os.path.join(_TMP, "api_test.db")

from fastapi.testclient import TestClient  # noqa: E402

import bioos_runtime as runtime  # noqa: E402

client = TestClient(runtime.app)


def _any_patient_id():
    return next(iter(runtime.topology.patients.keys()))


def test_health_liveness():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["service"] == "bioos-runtime"


def test_news2_census_matrix_shape():
    resp = client.get("/api/clinical/news2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["advisory_only"] is True
    assert set(data["band_counts"].keys()) == {"LOW", "MEDIUM", "HIGH"}
    assert len(data["patients"]) == len(runtime.topology.patients)
    # Sorted worst-first
    scores = [p["total_score"] for p in data["patients"]]
    assert scores == sorted(scores, reverse=True)


def test_news2_observation_full_flow_with_overrides():
    patient_id = _any_patient_id()
    payload = {
        "respiration_rate": 25,
        "spo2_percent": 92,
        "on_supplemental_oxygen": True,
        "spo2_scale": 1,
        "systolic_bp_mmhg": 95,
        "pulse_bpm": 110,
        "is_alert": False,
        "temperature_c": 38.5,
    }
    resp = client.post(f"/api/clinical/news2/{patient_id}/observation", json=payload)
    assert resp.status_code == 200
    score = resp.json()
    # Hand-computed from the published chart: RR25:3 + SpO2 92:2 + O2:2 +
    # SBP 95:2 + pulse 110:1 + new-CVPU:3 + 38.5C:1 = 14 -> HIGH emergency
    assert score["total_score"] == 14
    assert score["clinical_risk"] == "HIGH"
    assert score["escalation"] == "HIGH"
    assert score["defaults_used"] == {
        "on_supplemental_oxygen": False, "spo2_scale": False, "is_alert": False,
    }

    # Census matrix now reflects the recorded trend observation
    matrix = client.get("/api/clinical/news2").json()
    row = next(p for p in matrix["patients"] if p["patient_id"] == patient_id)
    assert row["trend_observations"] >= 1

    # Audit chain remains intact after the escalation entries
    audit = client.get("/api/audit/chain").json()
    assert audit["verification"]["valid"] is True
    assert audit["verification"]["entries"] >= 1


def test_news2_observation_rejects_impossible_physiology():
    patient_id = _any_patient_id()
    resp = client.post(
        f"/api/clinical/news2/{patient_id}/observation",
        json={"respiration_rate": 0},
    )
    assert resp.status_code == 422
    assert "out of range" in resp.json()["error"]


def test_fhir_bundle_shapes():
    patients = client.get("/api/fhir/patients").json()
    assert patients["resourceType"] == "Bundle" and patients["type"] == "collection"
    assert len(patients["entry"]) == len(runtime.topology.patients)

    patient_id = _any_patient_id()
    observations = client.get(f"/api/fhir/observations/{patient_id}").json()
    codes = {e["resource"]["code"]["coding"][0]["code"] for e in observations["entry"]}
    assert "8867-4" in codes and "8471-5" in codes  # HR + MAP (LOINC)


def test_shell_endpoint_audit_command():
    resp = client.post("/api/os/execute", json={"command": "audit"})
    assert resp.status_code == 200
    body = resp.json()
    assert "HASH-CHAINED AUDIT LOG" in body["output"]
    assert "INTACT" in body["output"]


def test_auth_enforcement_matrix():
    import os as _os

    _os.environ["BIOOS_AUTH_REQUIRED"] = "1"
    try:
        # Exempt route stays public
        assert client.get("/api/health").status_code == 200

        # Protected route without credentials -> 401
        assert client.post("/api/kernel/step", json={}).status_code == 401

        # Issue a NURSE token: has write_telemetry + bed_manage, not clinical_order
        token = client.post(
            "/api/auth/token", json={"role": "NURSE", "subject": "RN-Test"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert client.post("/api/kernel/step", json={}, headers=headers).status_code == 200
        assert client.get("/api/audit/chain", headers=headers).status_code == 403  # AUDIT perm missing

        # AUDITOR role: read + audit only -> kernel step forbidden
        auditor_token = client.post(
            "/api/auth/token", json={"role": "AUDITOR", "subject": "AUD-1"}
        ).json()["access_token"]
        auditor_headers = {"Authorization": f"Bearer {auditor_token}"}
        assert client.get("/api/audit/chain", headers=auditor_headers).status_code == 200
        assert client.post("/api/kernel/step", json={}, headers=auditor_headers).status_code == 403
    finally:
        _os.environ["BIOOS_AUTH_REQUIRED"] = "0"


if __name__ == "__main__":
    test_health_liveness()
    test_news2_census_matrix_shape()
    test_news2_observation_full_flow_with_overrides()
    test_news2_observation_rejects_impossible_physiology()
    test_fhir_bundle_shapes()
    test_shell_endpoint_audit_command()
    test_auth_enforcement_matrix()
    print("\nALL API ROUTE TESTS PASSED!")