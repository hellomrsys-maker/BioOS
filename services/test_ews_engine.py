# -*- coding: utf-8 -*-
"""
NEWS2 golden-vector tests — every boundary value hand-computed from the
published RCP (December 2017) aggregate scoring chart.
Run: python -m pytest services/test_ews_engine.py -v
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "command_center")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from ews_engine import (
    compute_news2,
    news2_from_patient,
    score_consciousness,
    score_pulse,
    score_respiration_rate,
    score_spo2_scale1,
    score_spo2_scale2,
    score_systolic_bp,
    score_temperature,
)


def test_per_parameter_boundaries_respiration():
    # Chart: <=8:3  9-11:1  12-20:0  21-24:2  >=25:3
    for value, expected in [(8, 3), (9, 1), (11, 1), (12, 0), (20, 0), (21, 2), (24, 2), (25, 3)]:
        assert score_respiration_rate(value) == expected, f"RR {value}"


def test_per_parameter_boundaries_spo2_scale1():
    # Chart: <=91:3  92-93:2  94-95:1  >=96:0
    for value, expected in [(91, 3), (92, 2), (93, 2), (94, 1), (95, 1), (96, 0), (100, 0)]:
        assert score_spo2_scale1(value) == expected, f"SpO2 {value}"


def test_per_parameter_boundaries_spo2_scale2():
    # Chart: <=83:3  84-85:2  86-87:1  88-92:0  93-94:1  95-96:2  >=97:3
    for value, expected in [(83, 3), (84, 2), (86, 1), (88, 0), (92, 0),
                            (93, 1), (94, 1), (95, 2), (96, 2), (97, 3)]:
        assert score_spo2_scale2(value) == expected, f"SpO2(S2) {value}"


def test_per_parameter_boundaries_sbp_pulse_temp():
    # SBP: <=90:3  91-100:2  101-110:1  111-219:0  >=220:3
    for value, expected in [(90, 3), (91, 2), (100, 2), (101, 1), (110, 1),
                            (111, 0), (219, 0), (220, 3)]:
        assert score_systolic_bp(value) == expected, f"SBP {value}"
    # Pulse: <=40:3  41-50:1  51-90:0  91-110:1  111-130:2  >=131:3
    for value, expected in [(40, 3), (41, 1), (50, 1), (51, 0), (90, 0),
                            (91, 1), (110, 1), (111, 2), (130, 2), (131, 3)]:
        assert score_pulse(value) == expected, f"pulse {value}"
    # Temp: <=35.0:3  35.1-36.0:1  36.1-38.0:0  38.1-39.0:1  >=39.1:2
    for value, expected in [(35.0, 3), (35.1, 1), (36.0, 1), (36.1, 0), (38.0, 0),
                            (38.1, 1), (39.0, 1), (39.1, 2)]:
        assert score_temperature(value) == expected, f"temp {value}"
    assert score_consciousness(True) == 0
    assert score_consciousness(False) == 3  # new CVPU


def _news2(rr, spo2, o2, sbp, pulse, alert, temp, scale=1):
    return compute_news2(rr, spo2, o2, sbp, pulse, alert, temp, spo2_scale=scale)

def test_golden_aggregate_healthy_total_zero():
    print("[TEST] NEWS2 golden: fully healthy patient -> 0, LOW, routine")
    r = _news2(14, 98, False, 120, 72, True, 36.8)
    assert r["total_score"] == 0 and r["clinical_risk"] == "LOW"
    assert r["escalation"] == "LOW"
    assert r["monitoring_recommendation"] == "Routine 12-hourly observations"


def test_golden_aggregate_sepsis_high():
    print("[TEST] NEWS2 golden: sepsis physiology -> 10, HIGH, emergency response")
    # RR 24:2  SpO2 93:2  O2:2  SBP 95:2  pulse 105:1  alert:0  38.9:1  = 10
    r = _news2(24, 93, True, 95, 105, True, 38.9)
    assert r["total_score"] == 10 and r["clinical_risk"] == "HIGH"
    assert r["escalation"] == "HIGH"
    assert "Emergency response" in r["monitoring_recommendation"]


def test_golden_single_parameter_escalation_rule():
    print("[TEST] NEWS2 golden: RR 26 alone -> total 3 LOW band but MEDIUM escalation")
    # RR 26:3, everything else 0 -> total 3 -> LOW band, single score-3 rule
    r = _news2(26, 97, False, 125, 80, True, 36.5)
    assert r["total_score"] == 3
    assert r["clinical_risk"] == "LOW"
    assert r["has_single_score_3"] is True
    assert r["escalation"] == "MEDIUM"
    assert "Urgent ward-based review" in r["monitoring_recommendation"]


def test_golden_aggregate_medium_threshold():
    print("[TEST] NEWS2 golden: aggregate 5 -> MEDIUM (key RCP threshold)")
    # RR 22:2  SpO2 95:1  SBP 105:1  pulse 100:1  = 5
    r = _news2(22, 95, False, 105, 100, True, 37.0)
    assert r["total_score"] == 5 and r["clinical_risk"] == "MEDIUM"
    assert r["escalation"] == "MEDIUM"


def test_golden_scale2_and_oxygen_scoring():
    print("[TEST] NEWS2 golden: Scale 2 SpO2 + supplemental O2 scoring")
    # Scale 2, SpO2 96 -> 2 (target 88-92 exceeded); total 2 LOW
    r = _news2(20, 96, False, 130, 85, True, 36.5, scale=2)
    assert r["per_parameter"]["spo2"] == 2
    assert r["total_score"] == 2 and r["clinical_risk"] == "LOW"
    # Room-air equivalent on Scale 1 would be 0 — scale changes the score
    r1 = _news2(20, 96, False, 130, 85, True, 36.5, scale=1)
    assert r1["per_parameter"]["spo2"] == 0
    # On oxygen alone adds 2
    r2 = _news2(14, 97, True, 118, 70, True, 36.5)
    assert r2["per_parameter"]["supplemental_oxygen"] == 2
    assert r2["total_score"] == 2 and r2["escalation"] == "LOW"  # no score-3


def test_golden_unresponsive_alert_rule():
    print("[TEST] NEWS2 golden: new unresponsiveness -> score 3 -> MEDIUM escalation")
    r = _news2(12, 98, False, 118, 70, False, 36.5)
    assert r["per_parameter"]["consciousness"] == 3
    assert r["total_score"] == 3 and r["escalation"] == "MEDIUM"


def test_golden_boundary_aggregate_five_across_parameters():
    print("[TEST] NEWS2 golden: five 1-point boundaries -> total 5 MEDIUM")
    # RR 9:1  SpO2 94:1  SBP 101:1  pulse 41:1  temp 35.5:1  = 5
    r = _news2(9, 94, False, 101, 41, True, 35.5)
    assert r["total_score"] == 5 and r["clinical_risk"] == "MEDIUM"


def test_input_validation_fail_loud():
    print("[TEST] NEWS2 validation: impossible physiology must raise, not score")
    with pytest.raises(ValueError):
        _news2(0, 98, False, 120, 72, True, 36.8)       # RR 0 impossible
    with pytest.raises(ValueError):
        _news2(14, 101, False, 120, 72, True, 36.8)     # SpO2 > 100
    with pytest.raises(ValueError):
        _news2(14, 98, False, 500, 72, True, 36.8)      # SBP out of range
    with pytest.raises(ValueError):
        _news2(14, 98, False, 120, 72, True, 50.0)      # temp out of range
    with pytest.raises(ValueError):
        _news2(14, 98, False, 120, 72, True, 36.8, scale=3)  # invalid scale


def test_patient_record_mapping_defaults_score_zero():
    print("[TEST] NEWS2: PatientRecord defaults (stable inpatient) -> total 0")
    from hospital_topology import HospitalTopologyManager, PatientRecord
    mgr = HospitalTopologyManager()
    rec = PatientRecord(
        patient_id="EWS-PT-1", mrn="MRN-EWS", name="EWS Test", age=60, sex="F",
        diagnosis="Observation", esi_triage_score=4, ward_id="ED_MAIN", bed_id="",
        attending_md="Dr. EWS", primary_rn="RN", admission_timestamp=1000.0,
    )
    ok, _ = mgr.admit_patient(rec, "ED_MAIN")
    assert ok
    r = news2_from_patient(rec)
    assert r["total_score"] == 0 and r["clinical_risk"] == "LOW"
    assert r["advisory_only"] is True
    print(" -> PatientRecord mapping PASS (NEWS2 0, advisory flag set)")


if __name__ == "__main__":
    test_per_parameter_boundaries_respiration()
    test_per_parameter_boundaries_spo2_scale1()
    test_per_parameter_boundaries_spo2_scale2()
    test_per_parameter_boundaries_sbp_pulse_temp()
    test_golden_aggregate_healthy_total_zero()
    test_golden_aggregate_sepsis_high()
    test_golden_single_parameter_escalation_rule()
    test_golden_aggregate_medium_threshold()
    test_golden_scale2_and_oxygen_scoring()
    test_golden_unresponsive_alert_rule()
    test_golden_boundary_aggregate_five_across_parameters()
    test_input_validation_fail_loud()
    test_patient_record_mapping_defaults_score_zero()
    print("\nALL NEWS2 GOLDEN VECTOR TESTS PASSED!")