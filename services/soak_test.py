import io
import os
import random
import statistics
import sys
import tempfile
import time
import argparse

# Isolate the runtime store before the daemon boots
_TMP = tempfile.mkdtemp(prefix="bioos_soak_")
os.environ["BIOOS_DB_PATH"] = os.path.join(_TMP, "soak.db")
os.environ["BIOOS_TELEMETRY_HZ"] = "5"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import bioos_runtime as runtime  # noqa: E402


def _pctl(samples, p):
    if not samples:
        return 0.0
    ordered = sorted(samples)
    rank = max(1, int(round((p / 100.0) * len(ordered))))
    return ordered[min(len(ordered) - 1, rank - 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description="BioOS sustained-load soak test")
    parser.add_argument("--duration", type=float, default=12.0,
                        help="soak duration in seconds")
    parser.add_argument("--windows", type=int, default=3,
                        help="number of equal analysis windows")
    args = parser.parse_args()

    client = TestClient(runtime.app)
    patient_id = next(iter(runtime.topology.patients.keys()))

    window_seconds = args.duration / args.windows
    windows = [{"latencies": [], "failures": 0, "requests": 0}
               for _ in range(args.windows)]

    telemetry_start = runtime.store.telemetry_count()
    observations_start = len(client.get("/api/clinical/news2").json()["patients"])

    print(f"[BioOS Soak] duration={args.duration}s windows={args.windows} "
          f"telemetry_before={telemetry_start}")

    started = time.perf_counter()
    request_index = 0
    rng = random.Random(20261016)

    while True:
        elapsed = time.perf_counter() - started
        if elapsed >= args.duration:
            break
        window = min(args.windows - 1, int(elapsed / window_seconds))
        t0 = time.perf_counter_ns()

        # Mixed clinical workload against the live stack
        choice = request_index % 6
        try:
            if choice == 0:
                resp = client.post("/api/kernel/step", json={
                    "pressure_mmhg": rng.randint(120, 600),
                    "bubble_ul": rng.choice([0, 0, 0, 40]),
                    "h_index": rng.randint(2, 30),
                    "k_val": round(rng.uniform(3.0, 6.0), 2),
                })
            elif choice == 1:
                resp = client.get("/api/clinical/news2")
            elif choice == 2:
                resp = client.post(f"/api/clinical/news2/{patient_id}/observation", json={
                    "respiration_rate": rng.randint(10, 28),
                    "spo2_percent": rng.randint(90, 100),
                    "systolic_bp_mmhg": rng.randint(90, 140),
                    "pulse_bpm": rng.randint(55, 125),
                    "temperature_c": round(rng.uniform(36.0, 39.2), 1),
                    "spo2_scale": 1,
                })
            elif choice == 3:
                resp = client.get("/api/audit/chain")
            elif choice == 4:
                resp = client.post("/api/os/execute", json={"command": "news2"})
            else:
                resp = client.get("/api/amsv/triplane")

            latency_ms = (time.perf_counter_ns() - t0) / 1e6
            windows[window]["latencies"].append(latency_ms)
            windows[window]["requests"] += 1
            if resp.status_code >= 500:
                windows[window]["failures"] += 1
        except Exception:
            windows[window]["failures"] += 1

        request_index += 1

    total_requests = sum(w["requests"] for w in windows)
    total_failures = sum(w["failures"] for w in windows)

    print(f"[BioOS Soak] completed {total_requests} requests in {args.duration:.0f}s")

    # 1. Zero server failures across the whole soak
    assert total_failures == 0, f"{total_failures} server failures during soak"

    # 2. Audit chain intact after sustained mixed load
    verdict = client.get("/api/audit/chain").json()["verification"]
    assert verdict["valid"] is True, f"audit chain broken: {verdict}"

    # 3. Telemetry grew monotonically (sampler + kernel steps persisted)
    telemetry_end = runtime.store.telemetry_count()
    assert telemetry_end > telemetry_start, "telemetry did not grow"

    # 4. Latency stability across windows (degradation detection).
    #    Generous tolerance: host VMs/GC can spike; we detect systematic
    #    degradation, not individual pauses. p95 of last window must stay
    #    under 3x the first window's p95 + 10 ms absolute headroom.
    p95s = [_pctl(w["latencies"], 95) for w in windows]
    budget = p95s[0] * 3.0 + 10.0
    for i, p95 in enumerate(p95s):
        print(f"  window {i}: requests={windows[i]['requests']:>5} "
              f"p50={_pctl(windows[i]['latencies'], 50):7.2f} ms "
              f"p95={p95:7.2f} ms max={_pctl(windows[i]['latencies'], 100):8.2f} ms")
    assert p95s[-1] <= budget, (
        f"latency degradation: final p95 {p95s[-1]:.2f} ms exceeds budget {budget:.2f} ms"
    )

    # 5. Trajectory monitor saw observations (clinical path exercised)
    matrix = client.get("/api/clinical/news2").json()
    total_trend = sum(p["trend_observations"] for p in matrix["patients"])
    assert total_trend > 0, "clinical observation path was not exercised"

    print(f"[BioOS Soak] PASS - chain intact, telemetry {telemetry_start}->{telemetry_end}, "
          f"trend obs {total_trend}, failures 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())