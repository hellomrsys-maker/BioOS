# -*- coding: utf-8 -*-
"""
NEWS2 Trend Monitor tests — published RCP trajectory rules.
Run: python -m pytest services/test_ews_trend.py -v
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(_HERE, "command_center")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from ews_trend import News2TrendMonitor


def test_rising_two_points_triggers_urgent_review():
    print("[TEST] RCP trajectory rule: rise >= 2 -> urgent review even if low")
    monitor = News2TrendMonitor()
    assert monitor.record("PT-1", 1) == []          # baseline
    alerts = monitor.record("PT-1", 3)              # +2 rise, still LOW band
    kinds = [a["type"] for a in alerts]
    assert "RISING_NEWS2_URGENT_REVIEW" in kinds
    rising = next(a for a in alerts if a["type"] == "RISING_NEWS2_URGENT_REVIEW")
    assert rising["latest_score"] == 3
    print(" -> Rise +2 (1 -> 3): RISING_NEWS2_URGENT_REVIEW fired")


def test_small_rise_does_not_alert():
    print("[TEST] Rise of 1 point must NOT trigger the trajectory alert")
    monitor = News2TrendMonitor()
    monitor.record("PT-2", 2)
    alerts = monitor.record("PT-2", 3)              # +1 only
    assert all(a["type"] != "RISING_NEWS2_URGENT_REVIEW" for a in alerts)
    print(" -> Rise +1 (2 -> 3): no trajectory alert")


def test_persistent_elevation_after_sustained_period():
    print("[TEST] NEWS2 >= 3 sustained -> PERSISTENT_ELEVATED")
    monitor = News2TrendMonitor(sustain_count=3)
    assert monitor.record("PT-3", 3) == []
    assert monitor.record("PT-3", 3) == []
    alerts = monitor.record("PT-3", 3)              # 3rd consecutive >= 3
    kinds = [a["type"] for a in alerts]
    assert "PERSISTENT_ELEVATED" in kinds
    print(" -> Sustained >= 3 over 3 observations: PERSISTENT_ELEVATED fired")

def test_critical_high_band_alert():
    print("[TEST] NEWS2 >= 7 -> CRITICAL_HIGH emergency alert")
    monitor = News2TrendMonitor()
    alerts = monitor.record("PT-4", 9)
    kinds = [a["type"] for a in alerts]
    assert "CRITICAL_HIGH" in kinds
    print(" -> Score 9: CRITICAL_HIGH fired")


def test_stable_low_patient_never_alerts():
    print("[TEST] Stable LOW scores produce no alerts (false-alarm check)")
    monitor = News2TrendMonitor()
    alerts = []
    for score in (0, 0, 1, 0, 1, 1, 0, 1, 0, 1):
        alerts.extend(monitor.record("PT-5", score))
    assert alerts == []
    print(" -> 10 stable observations: zero alerts")


def test_history_bounded_and_per_patient_isolated():
    print("[TEST] History bounded (maxlen) and patients isolated")
    monitor = News2TrendMonitor(history_size=3)
    for s in (0, 0, 0, 2):                          # history: 0,0,2
        monitor.record("PT-6", s)
    assert len(monitor.history("PT-6")) == 3
    assert [h["total_score"] for h in monitor.history("PT-6")] == [0, 0, 2]
    assert monitor.record("PT-7", 0) == []          # independent patient history
    assert monitor.history("PT-6")[-1]["total_score"] == 2
    print(" -> Bounded history + patient isolation PASS")


def test_out_of_range_score_rejected():
    print("[TEST] Impossible scores must raise, not record")
    monitor = News2TrendMonitor()
    with pytest.raises(ValueError):
        monitor.record("PT-8", 25)
    with pytest.raises(ValueError):
        monitor.record("PT-8", -1)
    print(" -> Range validation PASS")


def test_full_deterioration_trajectory_scenario():
    print("[TEST] Clinical scenario: deteriorating patient over 5 observations")
    monitor = News2TrendMonitor()
    scenario_scores = [0, 1, 3, 6, 8]               # worsening trajectory
    all_alerts = []
    for s in scenario_scores:
        all_alerts.extend(a["type"] for a in monitor.record("PT-9", s))
    # i=2: rise 1->3 (+2) -> RISING; i=3: rise 3->6 (+3) -> RISING;
    # i=4: 8 >= 7 -> CRITICAL_HIGH; rise 6->8 (+2) -> RISING;
    # last 3 observations (3,6,8) all >= 3 -> PERSISTENT_ELEVATED
    assert "RISING_NEWS2_URGENT_REVIEW" in all_alerts
    assert "CRITICAL_HIGH" in all_alerts
    assert "PERSISTENT_ELEVATED" in all_alerts
    print(f" -> Deterioration scenario PASS ({len(all_alerts)} alerts across trajectory)")


def test_clinical_observation_persistence_and_restart_hydration(tmp_path):
    print("[TEST] NEWS2 observations persist; trend monitor hydrates after 'restart'")
    from audit_store import BioOsPersistenceStore

    db_path = str(tmp_path / "ews_persist.db")

    # Session 1: record observations through the store (as the endpoint does)
    store1 = BioOsPersistenceStore(db_path=db_path)
    trajectory = [0, 1, 3, 6]  # deteriorating patient
    for i, score in enumerate(trajectory):
        store1.append_clinical_observation(
            ts_ns=1000 + i,
            patient_id="PT-RESTART",
            total_score=score,
            band="LOW" if score <= 4 else ("MEDIUM" if score <= 6 else "HIGH"),
            on_supplemental_oxygen=(i == 3),
            spo2_scale=1,
            is_alert=(i == 3),
            defaults_used={"on_supplemental_oxygen": i != 3, "is_alert": i != 3},
        )
    rows = store1.query_clinical_observations(patient_id="PT-RESTART")
    assert [r["total_score"] for r in rows] == trajectory
    assert rows[3]["on_supplemental_oxygen"] == 1
    assert rows[3]["defaults_used"] == {"on_supplemental_oxygen": False, "is_alert": False}
    store1.close()

    # Session 2 ("runtime restart"): fresh monitor hydrates from the store,
    # and the published trajectory rule fires on the restored history
    store2 = BioOsPersistenceStore(db_path=db_path)
    monitor = News2TrendMonitor()
    for obs in store2.query_clinical_observations(limit=500):
        monitor.record(obs["patient_id"], obs["total_score"])
    history = monitor.history("PT-RESTART")
    assert [h["total_score"] for h in history] == trajectory
    # Hydrated history ends at 6 (MEDIUM); a further jump to 8 (+2 rise) must
    # fire the published trajectory rule from RESTORED state:
    alerts = monitor.record("PT-RESTART", 8)
    kinds = [a["type"] for a in alerts]
    assert "RISING_NEWS2_URGENT_REVIEW" in kinds
    assert "CRITICAL_HIGH" in kinds  # 8 >= 7
    print(" -> Persistence + hydration PASS (trajectory survives restart)")

    test_small_rise_does_not_alert()
    test_persistent_elevation_after_sustained_period()
    test_critical_high_band_alert()
    test_stable_low_patient_never_alerts()
    test_history_bounded_and_per_patient_isolated()
    test_out_of_range_score_rejected()
    test_full_deterioration_trajectory_scenario()
    print("\nALL NEWS2 TREND TESTS PASSED!")
