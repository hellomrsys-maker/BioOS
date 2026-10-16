# -*- coding: utf-8 -*-
"""
BioOS Early Warning Score Engine — NEWS2 (Royal College of Physicians, 2017)
Standard: RCP National Early Warning Score (NEWS) 2, December 2017

Scoring is implemented strictly from the published aggregate scoring chart.
Published bands (Scale 1 = standard SpO2 target 96%; Scale 2 = hypercapnic
respiratory failure, target 88-92%):

Respiration rate (per min):  <=8:3  9-11:1  12-20:0  21-24:2  >=25:3
SpO2 Scale 1 (%):            <=91:3  92-93:2  94-95:1  >=96:0
SpO2 Scale 2 (%):            <=83:3  84-85:2  86-87:1  88-92:0  93-94(+O2):1
                             95-96(+O2):2  >=97(+O2):3
Supplemental O2:             room air:0  on oxygen:2
Systolic BP (mmHg):          <=90:3  91-100:2  101-110:1  111-219:0  >=220:3
Pulse (bpm):                 <=40:3  41-50:1  51-90:0  91-110:1  111-130:2  >=131:3
Consciousness:               Alert:0  new CVPU (Confusion/Voice/Pain/Unresponsive):3
Temperature (C):             <=35.0:3  35.1-36.0:1  36.1-38.0:0  38.1-39.0:1  >=39.1:2

Aggregate clinical risk bands:
  0            -> LOW      (routine monitoring, 12-hourly obs)
  1-4          -> LOW      (6-4-hourly obs, clinician review of single score-3)
  5-6          -> MEDIUM   (urgent review, 1-hourly obs)  [key threshold]
  >=7          -> HIGH     (emergency response, continuous monitoring)
Single-parameter rule: any parameter scoring 3 with total in LOW band
escalates the response to MEDIUM (urgent review).

This engine ADVISES ONLY (Plane B). Escalation actions remain human decisions.
Pure stdlib. All scoring verified against golden vectors in test_ews_engine.py.
"""

from typing import Any, Dict


def score_respiration_rate(rr: float) -> int:
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def score_spo2_scale1(spo2: float) -> int:
    if spo2 <= 91:
        return 3
    if spo2 <= 93:
        return 2
    if spo2 <= 95:
        return 1
    return 0


def score_spo2_scale2(spo2: float) -> int:
    if spo2 <= 83:
        return 3
    if spo2 <= 85:
        return 2
    if spo2 <= 87:
        return 1
    if spo2 <= 92:
        return 0
    if spo2 <= 94:
        return 1
    if spo2 <= 96:
        return 2
    return 3


def score_supplemental_o2(on_oxygen: bool) -> int:
    return 2 if on_oxygen else 0


def score_systolic_bp(sbp: float) -> int:
    if sbp <= 90:
        return 3
    if sbp <= 100:
        return 2
    if sbp <= 110:
        return 1
    if sbp <= 219:
        return 0
    return 3


def score_pulse(pulse: float) -> int:
    if pulse <= 40:
        return 3
    if pulse <= 50:
        return 1
    if pulse <= 90:
        return 0
    if pulse <= 110:
        return 1
    if pulse <= 130:
        return 2
    return 3


def score_consciousness(alert_only: bool) -> int:
    """alert_only=True -> Alert (0). Any new Confusion/Voice/Pain/Unresponsive -> 3."""
    return 0 if alert_only else 3


def score_temperature(temp_c: float) -> int:
    if temp_c <= 35.0:
        return 3
    if temp_c <= 36.0:
        return 1
    if temp_c <= 38.0:
        return 0
    if temp_c <= 39.0:
        return 1
    return 2

def _band(total: int) -> str:
    if total == 0:
        return "LOW"
    if total <= 4:
        return "LOW"
    if total <= 6:
        return "MEDIUM"
    return "HIGH"


def compute_news2(
    respiration_rate: float,
    spo2_percent: float,
    on_supplemental_oxygen: bool,
    systolic_bp_mmhg: float,
    pulse_bpm: float,
    is_alert: bool,
    temperature_c: float,
    spo2_scale: int = 1,
) -> Dict[str, Any]:
    """Computes the full NEWS2 aggregate score, band, and escalation advice.

    Returns per-parameter scores (auditability) plus the total and band.
    Raises ValueError for physiologically impossible inputs (fail-loud)."""
    if spo2_scale not in (1, 2):
        raise ValueError("spo2_scale must be 1 or 2 (RCP NEWS2 definition)")
    if not (0 < respiration_rate < 120):
        raise ValueError(f"respiration_rate {respiration_rate} out of range")
    if not (0 < spo2_percent <= 100):
        raise ValueError(f"spo2_percent {spo2_percent} out of range")
    if not (30 < systolic_bp_mmhg < 400):
        raise ValueError(f"systolic_bp_mmhg {systolic_bp_mmhg} out of range")
    if not (0 < pulse_bpm < 350):
        raise ValueError(f"pulse_bpm {pulse_bpm} out of range")
    if not (25.0 <= temperature_c <= 45.0):
        raise ValueError(f"temperature_c {temperature_c} out of range")

    spo2_score = (
        score_spo2_scale1(spo2_percent) if spo2_scale == 1
        else score_spo2_scale2(spo2_percent)
    )
    per_parameter = {
        "respiration_rate": score_respiration_rate(respiration_rate),
        "spo2": spo2_score,
        "supplemental_oxygen": score_supplemental_o2(on_supplemental_oxygen),
        "systolic_bp": score_systolic_bp(systolic_bp_mmhg),
        "pulse": score_pulse(pulse_bpm),
        "consciousness": score_consciousness(is_alert),
        "temperature": score_temperature(temperature_c),
    }
    total = sum(per_parameter.values())
    band = _band(total)

    # RCP single-parameter escalation rule: a score-3 parameter with a LOW
    # aggregate elevates the clinical response to MEDIUM (urgent review).
    has_score3 = 3 in per_parameter.values()
    escalation = "MEDIUM" if (band == "LOW" and has_score3 and total > 0) else band
    if band == "LOW" and total == 0:
        monitoring = "Routine 12-hourly observations"
    elif escalation == "MEDIUM" and band == "LOW":
        monitoring = "Urgent ward-based review; minimum 4-hourly observations"
    elif band == "MEDIUM":
        monitoring = "Urgent review by ward clinician; minimum 1-hourly observations"
    else:
        monitoring = "Emergency response; continuous monitoring of vital signs"

    return {
        "system": "NEWS2",
        "scale": "RCP December 2017",
        "spo2_scale": spo2_scale,
        "per_parameter": per_parameter,
        "total_score": total,
        "clinical_risk": band,
        "escalation": escalation,
        "has_single_score_3": has_score3,
        "monitoring_recommendation": monitoring,
        "advisory_only": True,
    }


def news2_from_patient(rec: Any) -> Dict[str, Any]:
    """Convenience mapping from a HospitalTopology PatientRecord (Scale 1).
    PatientRecord lacks oxygen-supplement and ACVPU fields; both default to
    room-air / Alert and MUST be overridden by clinicians when untrue."""
    return compute_news2(
        respiration_rate=float(rec.respiratory_rate),
        spo2_percent=float(rec.spo2_percent),
        on_supplemental_oxygen=False,
        systolic_bp_mmhg=float(rec.systolic_bp),
        pulse_bpm=float(rec.heart_rate),
        is_alert=(rec.gcs_score >= 15),
        temperature_c=float(rec.temperature_c),
        spo2_scale=1,
    )
