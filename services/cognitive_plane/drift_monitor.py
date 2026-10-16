# -*- coding: utf-8 -*-
"""
BioOS Cognitive Plane Drift Monitor

Tracks the rolling approval rate of clinical recommendations and raises
control-limit alerts:

- APPROVAL_RATE_SUSPICIOUS_HIGH : guard may be bypassed (safety regression!)
- APPROVAL_RATE_LOW             : upstream schema drift or over-strict guard

This is a starter statistical monitor (p-chart style). Certified deployments
must extend it with per-token baselines and PSI/KL drift metrics (P3).
"""

import time
from collections import deque
from typing import Any, Dict, Optional


class ApprovalRateDriftMonitor:
    def __init__(
        self,
        window_size: int = 50,
        min_samples: int = 10,
        lower_limit: float = 0.60,
        upper_limit: float = 0.99,
    ):
        if not (0.0 < lower_limit < upper_limit <= 1.0):
            raise ValueError("require 0 < lower_limit < upper_limit <= 1")
        self.window_size = window_size
        self.min_samples = min_samples
        self.lower_limit = lower_limit
        self.upper_limit = upper_limit
        self._window: deque = deque(maxlen=window_size)
        self.alerts_emitted = 0

    def record(self, approved: bool) -> Optional[Dict[str, Any]]:
        """Records one recommendation outcome; returns an alert dict when the
        rolling approval rate breaches a control limit, else None."""
        self._window.append(1 if approved else 0)
        if len(self._window) < self.min_samples:
            return None
        rate = sum(self._window) / len(self._window)
        if rate > self.upper_limit:
            self.alerts_emitted += 1
            return self._alert("APPROVAL_RATE_SUSPICIOUS_HIGH", rate,
                               "Guard may be bypassed - safety regression investigation required")
        if rate < self.lower_limit:
            self.alerts_emitted += 1
            return self._alert("APPROVAL_RATE_LOW", rate,
                               "Upstream schema drift or over-strict guard - investigate")
        return None

    def approval_rate(self) -> Optional[float]:
        if not self._window:
            return None
        return sum(self._window) / len(self._window)

    def reset(self) -> None:
        self._window.clear()

    def _alert(self, kind: str, rate: float, message: str) -> Dict[str, Any]:
        return {
            "type": kind,
            "approval_rate": round(rate, 4),
            "window_size": len(self._window),
            "limits": [self.lower_limit, self.upper_limit],
            "message": message,
            "ts_ns": time.time_ns(),
        }
