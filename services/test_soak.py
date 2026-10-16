# -*- coding: utf-8 -*-
"""Compact sustained-load soak gate for CI (roadmap 4.11).

Runs a 4-second / 2-window mixed clinical workload through the live stack and
asserts: zero server failures, audit-chain intactness, telemetry growth,
clinical path exercised, and no systematic latency degradation.
Long-form evidence run: services/soak_test.py --duration 12.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from soak_test import main as _soak_main  # noqa: E402


def test_sustained_load_soak_gate():
    sys.argv = ["soak", "--duration", "4", "--windows", "2"]
    assert _soak_main() == 0, "soak gate failed - see captured output"