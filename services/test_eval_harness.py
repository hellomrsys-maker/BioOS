# -*- coding: utf-8 -*-
"""
Golden-Case Eval Harness + Drift Monitor tests.
Run: python -m pytest services/test_eval_harness.py -v
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "cognitive_plane"), os.path.join(_HERE, "command_center")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from drift_monitor import ApprovalRateDriftMonitor
from eval_harness import GOLDEN_CASES, run_golden_cases


def test_all_golden_cases_pass_on_deterministic_backend():
    print("[TEST] Golden-case evaluation on deterministic constrained backend...")
    report = run_golden_cases()
    assert report["total"] == len(GOLDEN_CASES)
    assert report["skipped"] <= 1  # only the kernel-gate case may skip
    for r in report["results"]:
        if not r.get("skipped"):
            assert r["passed"], f"{r['case_id']} failed: {r['detail']}"
    assert report["all_passed"], f"failures: {[r for r in report['results'] if not r['passed']]}"
    print(f" -> Eval harness PASS ({report['passed']}/{report['total']} cases, "
          f"{report['skipped']} skipped)")


def test_harness_detects_broken_backend():
    print("[TEST] Harness must FAIL a backend that approves hallucinated tokens...")

    class GuardlessBackend:
        """Simulates a guard bypass: approves everything with fixed dosing."""

        def generate_constrained_clinical_recommendation(self, **kwargs):
            order = {
                "resourceType": "MedicationRequest",
                "status": "draft_awaiting_plane_a_kernel_validation",
                "medicationCodeableConcept": {"coding": [{"display": "Unknown Drug"}]},
                "dosageInstruction": [{
                    "route": {"text": "IV"},
                    "doseAndRate": [{"doseQuantity": {"value": 999.0, "unit": "mg"}}],
                }],
            }
            return order, True

    report = run_golden_cases(coe=GuardlessBackend())
    assert report["all_passed"] is False
    failed_ids = {r["case_id"] for r in report["results"] if not r["passed"]}
    assert "GOLD-008" in failed_ids  # hallucinated token was NOT rejected
    assert failed_ids  # verbatim dosing cases also fail (wrong drug/dose/route)
    print(f" -> Guard-bypass detection PASS ({len(failed_ids)} cases flagged)")


def test_drift_monitor_suspicious_high_alert():
    print("[TEST] Drift monitor: guard bypass (100% approval) -> HIGH alert...")
    monitor = ApprovalRateDriftMonitor()
    alert = None
    for _ in range(50):
        alert = monitor.record(True)
    assert alert is not None and alert["type"] == "APPROVAL_RATE_SUSPICIOUS_HIGH"
    assert monitor.approval_rate() == 1.0
    print(" -> HIGH control-limit alert PASS")


def test_drift_monitor_low_alert():
    print("[TEST] Drift monitor: 20% approval -> LOW alert...")
    monitor = ApprovalRateDriftMonitor()
    alert = None
    for i in range(50):
        alert = monitor.record(i % 5 == 0)  # 20% approval rate
    assert alert is not None and alert["type"] == "APPROVAL_RATE_LOW"
    print(" -> LOW control-limit alert PASS")


def test_drift_monitor_stable_stream_no_alert():
    print("[TEST] Drift monitor: healthy 75% approval stream -> no alerts...")
    monitor = ApprovalRateDriftMonitor()
    alerts = []
    for i in range(200):
        a = monitor.record(i % 4 != 3)  # 75% approval
        if a:
            alerts.append(a)
    assert alerts == []
    assert 0.70 < monitor.approval_rate() < 0.80  # ~75% expected; window edges vary
    print(" -> Stable-stream PASS (no false alerts over 200 samples)")


def test_drift_monitor_reset_and_validation():
    print("[TEST] Drift monitor: reset + invalid limits...")
    monitor = ApprovalRateDriftMonitor()
    for _ in range(30):
        monitor.record(True)
    monitor.reset()
    assert monitor.approval_rate() is None
    try:
        ApprovalRateDriftMonitor(lower_limit=0.9, upper_limit=0.5)
        raise AssertionError("inverted limits must raise")
    except ValueError:
        pass
    print(" -> Reset + validation PASS")


if __name__ == "__main__":
    test_all_golden_cases_pass_on_deterministic_backend()
    test_harness_detects_broken_backend()
    test_drift_monitor_suspicious_high_alert()
    test_drift_monitor_low_alert()
    test_drift_monitor_stable_stream_no_alert()
    test_drift_monitor_reset_and_validation()
    print("\nALL EVAL HARNESS + DRIFT MONITOR TESTS PASSED!")
