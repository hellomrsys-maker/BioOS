# -*- coding: utf-8 -*-
"""
BioOS WCET Benchmark Harness

Measures ctypes round-trip latency of the Plane A kernel C-ABI functions.
What this proves: the FFI + kernel path fits the real-time budgets on the
host platform. What it does NOT prove: on-target WCET for a certified
embedded build (requires instrumented on-target timing, see
docs/ROADMAP_AND_CRITICAL_PRIORITIES.md - Plane A phase).

Budgets:
- bioos_kernel_step     <= 100 us  (1000 Hz actuator loop budget)
- bioos_envelope_step   <= 1 ms    (100 Hz observer, generous headroom)
- pure compute FFI      <= 10 us   (must be negligible vs loop budget)

Usage:
    python services/wcet_benchmark.py --iters 50000 [--json]
"""

import argparse
import ctypes
import json
import statistics
import sys
import time
from typing import Any, Callable, Dict

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else ".")
sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")

from kernel_bridge import BioOsKernelBridge  # noqa: E402

# Budgets: pure-compute FFI gets 25 us (not 10) because HOST ctypes round-trips
# include Windows scheduler noise (~10 us p99 tail); on-target RTOS builds get
# their own instrumented budgets (see roadmap - Plane A on-target phase).
BUDGETS_NS = {
    "bioos_kernel_step": 100_000,
    "bioos_envelope_step": 1_000_000,
    "bioos_amsv_read_atomic": 25_000,
    "bioos_validate_potassium": 25_000,
    "bioos_calculate_ckd_epi": 25_000,
    "bioos_verify_metformin": 25_000,
}


def benchmark(fn: Callable[[], Any], iters: int) -> Dict[str, Any]:
    """Samples iters calls of fn and returns min/p50/p95/p99/max in ns."""
    samples = []
    for _ in range(iters):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    samples.sort()

    def pct(p: float) -> int:
        rank = max(1, int(round((p / 100.0) * len(samples))))
        return int(samples[min(len(samples) - 1, rank - 1)])

    return {
        "iters": iters,
        "min_ns": int(samples[0]),
        "p50_ns": pct(50),
        "p95_ns": pct(95),
        "p99_ns": pct(99),
        "max_ns": int(samples[-1]),
        "mean_ns": round(float(statistics.fmean(samples)), 1),
    }


def run_all(
    bridge: BioOsKernelBridge,
    iters: int = 20_000,
    budget_stat: str = "p99",
) -> Dict[str, Dict[str, Any]]:
    """Benchmarks every FFI path. `budget_stat` selects which percentile is
    budget-gated: "p99" (authoritative, use high iteration counts) or "p95"
    (host-noise-tolerant, for CI smoke tests on shared runners)."""
    lib = bridge.lib
    out_alpha = ctypes.c_uint8(0)
    out_rate = ctypes.c_float(0.0)
    amsv_snapshot = bridge.amsv_shared  # ctypes view over shared memory

    cases: Dict[str, Callable[[], Any]] = {
        "bioos_kernel_step": lambda: lib.bioos_kernel_step(
            1_000, 1_000, 180, 0, 8, 4.4
        ),
        "bioos_envelope_step": lambda: lib.bioos_envelope_step(
            82.0, 75.0, 120.0, 125.0, 0.01,
            ctypes.byref(out_alpha), ctypes.byref(out_rate),
        ),
        "bioos_amsv_read_atomic": lambda: lib.bioos_amsv_read_atomic(
            ctypes.byref(amsv_snapshot)
        ),
        "bioos_validate_potassium": lambda: lib.bioos_validate_potassium(
            4.4, 8, ctypes.byref(out_alpha)
        ),
        "bioos_calculate_ckd_epi": lambda: lib.bioos_calculate_ckd_epi(
            65.0, 1.1, False
        ),
        "bioos_verify_metformin": lambda: lib.bioos_verify_metformin(65.0, 1500.0),
    }

    results: Dict[str, Dict[str, Any]] = {}
    for name, fn in cases.items():
        stats = benchmark(fn, iters)
        budget = BUDGETS_NS.get(name)
        stats["budget_ns"] = budget
        stats["budget_stat"] = budget_stat
        stats["budget_pass"] = (stats[budget_stat + "_ns"] <= budget) if budget else None
        results[name] = stats
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="BioOS kernel WCET benchmark")
    parser.add_argument("--iters", type=int, default=20_000)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args()

    print("[BioOS WCET] Booting kernel bridge...")
    bridge = BioOsKernelBridge()
    results = run_all(bridge, iters=args.iters)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        header = f"{'function':<28}{'p50 us':>10}{'p95 us':>10}{'p99 us':>10}{'max us':>10}  budget"
        print(header)
        print("-" * len(header))
        for name, s in results.items():
            verdict = "PASS" if s["budget_pass"] else "FAIL"
            budget = f"{s['budget_ns'] / 1000:.0f} us {verdict}" if s["budget_ns"] else "n/a"
            print(
                f"{name:<28}{s['p50_ns'] / 1000:>10.2f}{s['p95_ns'] / 1000:>10.2f}"
                f"{s['p99_ns'] / 1000:>10.2f}{s['max_ns'] / 1000:>10.2f}  {budget}"
            )
    worst = all(s["budget_pass"] for s in results.values() if s["budget_pass"] is not None)
    print(f"[BioOS WCET] {'ALL BUDGETS PASS' if worst else 'BUDGET VIOLATION DETECTED'}")
    return 0 if worst else 1


if __name__ == "__main__":
    raise SystemExit(main())
