# BioOS (BioSentinel OS)
### Tri-Plane Aerospace Safety-Critical Medical AI Operating System
**Standard Pedigree:** IEC 62304 Class C &bull; ASTM F2761 ICE &bull; Aerospace DO-178C Level A &bull; ISO/IEEE 11073 SDC &bull; CLSI C56-A  
**Target Hardware:** Tri-Plane Heterogeneous (Rust `#![no_std]` 1000 Hz Actuator Kernel + 100 Hz Kalman Envelope Limiter + AMD Instinct MI300X ROCm 6.2 Cognitive FMS)  
**Competition Target:** AMD Developer Hackathon: ACT III (Track 2: Health & Wellbeing + Evolus Partner Track)

---

## 1. Tri-Plane Aerospace Architecture

BioOS applies commercial avionics-grade redundancy (analogous to multi-engine fly-by-wire aircraft such as the Airbus A350 and Boeing 787):
> *"Software and artificial intelligence are probabilistic and subject to latency, drift, and hallucination; physical medical hardware requires zero-failure, hard real-time determinism."*

```
+---------------------------------------------------------------------------------------------------+
|                                 BIOOS TRIPLANE AEROSPACE ARCHITECTURE                             |
+---------------------------------------------------------------------------------------------------+
|  PLANE A: ENGINE 1 - FLY-BY-WIRE ACTUATOR SAFETY KERNEL (Rust #![no_std], 1000 Hz, O(1), 0-Heap)  |
|  - Exclusive Physical Relay Authority (2ms SSR / 12ms Mechanical Air-Gap)                         |
|  - CLSI C56-A Hemolysis Gate (H > 20 mg/dL => VOID K+ to prevent pseudohyperkalemic arrest)       |
|  - Hydrostatic Pressure Trip (525 mmHg / 10.2 psi) & Ultrasonic Air-in-Line Trip (>= 25 uL)       |
|  - Dettli Linear Ceiling Law & Metformin Hard Lockout (eGFR < 30 mL/min/1.73m2)                   |
|  - 3-State Mealy Hardware Watchdog Automaton & 50ms Missing Heartbeat Cutoff                      |
+---------------------------------------------------------------------------------------------------+
                                                  ▲
               [CACHE LINE 0: 0x00..0x3F (64 Bytes) - ACTUATOR STATE & CRC-16]
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|  PLANE C: ENGINE 2 - DYNAMIC PHYSIOLOGICAL ENVELOPE & KALMAN OBSERVER (100 Hz, O(1))               |
|  - Airbus-Style "Alpha-Floor" Hemodynamic Stall Protection (MAP < 55 mmHg => Rate Clamp to 0.0)   |
|  - Continuous Extended Kalman Filter (EKF) State & Velocity Tracking (MAP, HR, Shock Index)      |
|  - Dynamic Vasoactive Slew-Rate Acceleration Limiter (d(Rate)/dt <= 2.5 mL/h/sec)                 |
|  - Real-Time Dynamic Safety Margin Indexing & Receptor Desensitization Guard                      |
+---------------------------------------------------------------------------------------------------+
                                                  ▲
               [CACHE LINE 1: 0x40..0x7F (64 Bytes) - ENVELOPE STATE & KALMAN VAR]
                                                  ▼
+---------------------------------------------------------------------------------------------------+
|  PLANE B: ENGINE 3 - COGNITIVE FLIGHT MANAGEMENT SYSTEM (AMD Instinct MI300X, ROCm 6.2, vLLM)    |
|  - XGrammar Constrained JSON Decoding (FHIR R4 MedicationRequest Enums)                           |
|  - Dual-Model Adversarial Safety Ensemble (Llama-3.1-8B-Instruct + Llama-Guard-3-8B)             |
|  - RFC 9162 Merkle Tree Audit Trail (SHA-256 Hash Tree & Cryptographic Non-Repudiation)          |
|  - Hospital Escalation Index (E_I), RTLS 5-Stage Bed Turnover & HICS 2014 Reverse Triage         |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Directory Layout & Organization

```
bio-os/
├── .github/workflows/ci.yml          # CI: fmt + clippy(-D warnings) + tests + Linux cdylib build
├── docs/
│   ├── MASTER_ARCHITECTURE_BLUEPRINT.md    # Comprehensive system specification
│   ├── DATA_DICTIONARY_AND_FORMULAS.md     # Formulas, clinical constants, NTI tables
│   └── ROADMAP_AND_CRITICAL_PRIORITIES.md  # Gap analysis & prioritized development plan
├── crates/
│   └── bioos-kernel/                       # Rust #![no_std] IEC 62304 Class C Safety Kernel
│       ├── Cargo.toml / Cargo.lock         # Pinned, reproducible dependency resolution
│       └── src/ (see Section 2 modules)
├── services/
│   ├── bioos_runtime.py                    # FastAPI + SSE Master OS Runtime Daemon
│   ├── bioos_ctl.py                        # Administrative CLI shell
│   ├── kernel_bridge.py                    # ctypes zero-bridge to kernel cdylib (dll/so/dylib)
│   ├── rbac_auth.py                        # Stdlib HS256 JWT + RBAC (OIDC-ready skeleton)
│   ├── wcet_benchmark.py                   # Kernel C-ABI WCET harness (host FFI budgets)
│   ├── test_services.py / test_kernel_bridge.py / test_enterprise_fabric.py
│   ├── test_hl7_mllp.py / test_eval_harness.py / test_ews_engine.py / test_ews_trend.py / test_oidc_auth.py
│   ├── cognitive_plane/
│   │   ├── engine5_coe.py                  # AMD Instinct MI300X vLLM + RFC 9162 Merkle Log
│   │   ├── eval_harness.py                 # 9 golden clinical cases + scoring runner (CI-runnable)
│   │   └── drift_monitor.py                # Approval-rate control limits (guard-bypass alerts)
│   └── command_center/
│       ├── engine6_oce.py                  # Hospital Command, Escalation Index, MHP, RTLS
│       ├── wellbeing_engine.py             # Clinician & Patient Wellbeing Engine
│       ├── hospital_topology.py            # 78-bed multi-ward topology & RTLS turnover
│       ├── audit_store.py                  # SQLite WAL telemetry + hash-chained audit log
│       ├── fhir_facade.py                  # FHIR R4 Patient/Observation/MedicationRequest (kernel-gated)
│       ├── hl7_mllp.py                     # HL7 v2 MLLP stub listener (env BIOOS_MLLP_PORT)
│       ├── ews_engine.py                   # NEWS2 early-warning score (RCP Dec 2017, golden-vector tested)
│       └── ews_trend.py                    # NEWS2 trajectory rules (rise>=2 / sustained>=3 / >=7 emergency)
├── docs/compliance/                        # ISO 14971 hazard register, IEC 62304 traceability (aligned-to)
├── web/                                    # Medical Flight Deck UI (index/app.js/style.css)
├── requirements.txt                        # Pinned Python dependencies (supply-chain policy)
└── Dockerfile / .dockerignore              # Multi-stage: Rust kernel build + Python runtime
```

---

## 3. Verification & Test Execution

### 3.1 Plane A Rust Kernel Tests (100% Pass)
```powershell
cd D:\BIO.OS\crates\bioos-kernel
cargo test
```
**Test Results (14/14):**
- `test_amsv_struct_layout_and_size`: Verified 64-byte size, 64-byte alignment, Seqlock read/write, CRC-16.
- `test_triplane_dual_cacheline_layout`: Verified 128-byte dual-cache-line TriPlane layout.
- `test_hal_medical_bus_and_fault_injection`: Verified medical bus HAL online/fault injection states.
- `test_medical_device_drivers_ders_and_alarms`: Verified DERS limits and IEC 60601-1-8 alarm classes on device drivers.
- `test_kalman_envelope_and_alpha_floor`: Verified 100 Hz EKF envelope tracking and alpha-floor hemodynamic stall protection.
- `test_realtime_scheduler_edf_dispatch`: Verified deterministic rate-monotonic/EDF task dispatch.
- `test_spsc_ring_buffer_wait_free_ipc`: Verified wait-free single-producer/single-consumer IPC.
- `test_static_slab_pool_o1_alloc_free`: Verified O(1) static slab allocation/free with 0-heap guarantee.
- `test_clsi_c56a_potassium_hemolysis_gate`: Verified $H > 20 \implies$ VOID (NaN) pseudohyperkalemia interlock.
- `test_pump_occlusion_and_air_bubble_trips`: Verified $525\text{ mmHg}$ ($10.2\text{ psi}$) and $\ge 25\ \mu\text{L}$ bubble trips.
- `test_ckd_epi_and_cockcroft_gault`: Verified race-free eGFR and 3-tier Devine weight selection.
- `test_metformin_hard_lockout_at_low_egfr`: Verified absolute contraindication at $\text{eGFR} < 30$.
- `test_tisdale_qtc_risk_lockout`: Verified score $\ge 11 \implies$ hard lockout.
- `test_wie_watchdog_relay_trip_and_heartbeat_timeout`: Verified $2\text{ ms}$ SSR trip, $12\text{ ms}$ mechanical trip, and $50\text{ ms}$ heartbeat loss.

### 3.2 Plane B & Enterprise Python Tests (100% Pass)
```powershell
cd D:\BIO.OS
python -m pytest services -v
```

### 3.3 Cognitive Plane Golden-Case Evaluation
```powershell
cd D:\BIO.OS
python services\cognitive_plane\eval_harness.py
```
9 golden cases: verbatim NTI dosing (Vancomycin/Digoxin/Enoxaparin/Metformin), hallucinated-token rejection, and a live Plane A kernel metformin lockout (eGFR 22 → HardLockoutContraindicated). Exits 1 on any failure; guard-bypass detection proven.

### 3.4 Embedded no_std Build (Cortex-M4F)
```powershell
rustup target add thumbv7em-none-eabihf
cargo build --lib --no-default-features --features no_std --target thumbv7em-none-eabihf --manifest-path crates\bioos-kernel\Cargo.toml
```
Proves the safety kernel is genuinely `#![no_std]` (gated in CI; 64-bit atomics portable via `portable_atomic.rs`).

### 3.5 Kernel WCET Benchmark (first measured numbers)
```powershell
cd D:\BIO.OS
python services\wcet_benchmark.py --iters 50000
```
Measured host FFI round-trip (Windows, 50k samples): `bioos_kernel_step` p50 ≈ 2.7 µs, p99 ≈ 8.1 µs against the 100 µs budget of the 1000 Hz loop. Max spikes are Windows scheduler preemption artifacts; on-target RTOS budgets are a separate roadmap item.
**Test Results:**
- Engine 5 (COE): AMD ROCm inference adapter, XGrammar JSON constrained generation, RFC 9162 Merkle tree root hashing.
- Engine 6 (OCE): Hospital Escalation Index ($E_I$), RTLS 5-stage bed turnover, Massive Hemorrhage Protocol (MHP "7 Ts"), Nurse Standing Orders (Sepsis 1-hr, ACS, Hypoglycemia), ASHRAE 170 HVAC cascades, and HICS 2014 reverse triage.

### 3.6 Interactive Medical Flight Deck
- Open `http://localhost:8090/` in any modern web browser to interact with live telemetry, trigger occlusion and air-in-line spikes, test the CLSI C56-A potassium gate, simulate mass casualty surge, and inspect the 64-byte AMSV cache-line memory grid.


---



### 3.7 Sustained-Load Soak Test

```powershell
cd D:\BIO.OS
python services\soak_test.py --duration 12 --windows 3
```

Drives a mixed clinical workload (kernel steps, NEWS2 observations, census matrix, audit reads, shell commands, TriPlane reads) through the live stack and asserts: zero server failures, hash-chain intactness, telemetry growth, clinical-path exercise, and no inter-window latency degradation. The compact 4-second gate runs in CI (`services/test_soak.py`).

## 4. Runtime Configuration

All runtime behavior is environment-configurable (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `BIOOS_DB_PATH` | `data/bioos_runtime.db` | SQLite WAL store (telemetry + hash-chained audit) |
| `BIOOS_TELEMETRY_HZ` | `2` | Background AMSV sampler rate (0 disables) |
| `BIOOS_MLLP_PORT` | unset | HL7 v2 MLLP listener port (unset = disabled) |
| `BIOOS_AUTH_REQUIRED` | `0` | `1` enforces RBAC on `/api/*` (UI uses `/api/auth/token`) |
| `BIOOS_JWT_SECRET` | dev value | Dev HS256 signing secret (never in production) |
| `BIOOS_SERVICE_API_KEY` | unset | `X-Api-Key` mapped to the SERVICE role |
| `BIOOS_OIDC_ISSUER` | unset | Hospital OIDC issuer — enables RS256/JWKS verification |
| `BIOOS_OIDC_AUDIENCE` | unset | Expected `aud` claim when OIDC is configured |
| `BIOOS_KERNEL_LIB` | auto | Plane A cdylib override (dll/so/dylib auto-resolved) |

Auth resolution order for bearer tokens: **OIDC RS256 (when issuer set) -> dev HS256 -> X-Api-Key**. Route permissions per role are defined in `services/rbac_auth.py`.


---


