# -*- coding: utf-8 -*-
"""
BioOS NEWS2 Trend Monitor — deterioration trajectory detection

Implements the published RCP NEWS2 trajectory rules on top of point-in-time
scores (RCP NEWS2 December 2017, escalation guidance):

- RISING_NEWS2_URGENT_REVIEW: "a rise of 2 or more points from the previous
  observation should trigger urgent review even if the latest score is low"
  (published single-parameter/trajectory guidance).
- PERSISTENT_ELEVATED: NEWS2 >= 3 sustained for `sustain_count` consecutive
  observations warrants escalation review even without a further rise.
- CRITICAL_HIGH: latest score in the HIGH band (>= 7) — emergency response.

The monitor keeps a bounded per-patient history (most recent N scores).
Plane B ADVISES ONLY: it computes alerts; clinical response is human.
Pure stdlib.
"""

import time
from collections import deque
from typing import Any, Dict, List


class News2TrendMonitor:
    """Bounded per-patient NEWS2 history + published trajectory rules."""

    def __init__(self, history_size: int = 20, sustain_count: int = 3):
        if history_size < 2:
            raise ValueError("history_size must be >= 2")
        if sustain_count < 1:
            raise ValueError("sustain_count must be >= 1")
        self.history_size = history_size
        self.sustain_count = sustain_count
        self._history: Dict[str, deque] = {}
        self.alerts_emitted = 0

    def record(self, patient_id: str, total_score: int) -> List[Dict[str, Any]]:
        """Records one observation score; returns any trajectory alerts."""
        if not 0 <= total_score <= 20:
            raise ValueError(f"NEWS2 total_score {total_score} out of plausible range")
        history = self._history.setdefault(
            patient_id, deque(maxlen=self.history_size)
        )
        history.append({"total_score": total_score, "ts_ns": time.time_ns()})
        alerts = self._evaluate(patient_id, list(history))
        self.alerts_emitted += len(alerts)
        return alerts

    def history(self, patient_id: str) -> List[Dict[str, Any]]:
        return list(self._history.get(patient_id, ()))

    def _evaluate(self, patient_id: str, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        latest = history[-1]["total_score"]
        ts = history[-1]["ts_ns"]

        # CRITICAL_HIGH: latest score in the emergency band
        if latest >= 7:
            alerts.append(self._alert(
                patient_id, "CRITICAL_HIGH", latest, ts,
                "NEWS2 >= 7: emergency response required (continuous monitoring)",
            ))

        # Published trajectory rule: rise of >= 2 from previous observation
        if len(history) >= 2:
            previous = history[-2]["total_score"]
            if latest - previous >= 2:
                alerts.append(self._alert(
                    patient_id, "RISING_NEWS2_URGENT_REVIEW", latest, ts,
                    f"NEWS2 rose {latest - previous} points "
                    f"({previous} -> {latest}): urgent review required even if low",
                ))

        # Sustained elevation: >= 3 over the last `sustain_count` observations
        if latest >= 3 and len(history) >= self.sustain_count:
            recent = [h["total_score"] for h in history[-self.sustain_count:]]
            if all(s >= 3 for s in recent):
                alerts.append(self._alert(
                    patient_id, "PERSISTENT_ELEVATED", latest, ts,
                    f"NEWS2 >= 3 sustained over {self.sustain_count} observations: "
                    "escalation review warranted",
                ))
        return alerts

    @staticmethod
    def _alert(patient_id: str, kind: str, score: int, ts_ns: int, message: str) -> Dict[str, Any]:
        return {
            "patient_id": patient_id,
            "type": kind,
            "latest_score": score,
            "message": message,
            "ts_ns": ts_ns,
        }
