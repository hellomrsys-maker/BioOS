# Changelog

All notable changes to BioOS are documented here. Format follows Keep a Changelog; versioning is CalVer-adjacent during the pre-release phase.

## [0.2.0-alpha.1] — 2026-10-17

First hardware-ready milestone: the safety kernel compiles for real silicon, and the platform has end-to-end clinical, security, audit, and stability test coverage.

### Plane A — Safety Kernel (Rust)
- FFI exports converted to proper `unsafe fn` with `# Safety` documentation (4 functions); `static_mut_refs` eliminated via `addr_of_mut!` (hazard H-04 hygiene)
- **u64 monotonic time base** across the watchdog, FFI, bridge, and runtime — the u32 base wrapped every 4.29 s and `saturating_sub` made future heartbeat stamps look fresh (fail-unsafe); wrap-safety regression test added (hazard H-09 CLOSED)
- **STM32F407VG board-support skeleton** behind the `target-stm32` feature: 168 MHz clocks, DWT CYCCNT u64 time base, 1 kHz SysTick, SSR/mechanical relay GPIOs with readback closed-loop, raw-register IWDG (~50 ms) refreshed only after non-lockout WIE cycles, latching panic handler (relays open → post-mortem → halt), `memory.x` + target-scoped link flags
- **`PortableAtomicU64` three-variant selection**: true 64-bit atomics / 32-bit plain spinlock fallback / NEW 32-bit interrupt-masked cell (`cortex_m::interrupt::free` covers the whole access — the priority-inversion constraint is closed by design)
- Clippy clean at `-D warnings`; rustfmt-gated; 16/16 unit tests

### Clinical — NEWS2 Early Warning
- RCP NEWS2 (December 2017) scoring implemented strictly from the published chart: both SpO2 scales, supplemental-O2, ACVPU, single-parameter-3 escalation; 13 hand-computed golden boundary vectors
- **Trajectory monitor**: rise ≥ 2 → urgent review even when LOW, sustained ≥ 3 → escalation review, ≥ 7 → emergency response; 8 trajectory tests
- Observation persistence (`clinical_observations` table) with boot-time trend hydration — trajectories survive restarts
- Flight-deck console: census deterioration matrix, observation form with explicit H-11 overrides (`defaults_used` auditability), trajectory alert feed; census + shell commands

### Enterprise Fabric
- **FHIR R4 facade**: Patient/Observation (LOINC), MedicationRequest (RxNorm) gated by real kernel authority (`bioos_verify_metformin`), Subscription webhooks — all orders stay `status=draft` (Plane B advises, Plane A executes)
- **Hash-chained append-only audit log** (SQLite WAL) with tamper detection (verified: direct SQLite mutation is detected at the exact entry) complementing the RFC 9162 Merkle tree
- **OIDC RS256/JWKS verification** in pure stdlib: discovery, JWKS cache with rotation refresh, iss/aud/exp/nbf enforcement, least-privilege role mapping; tested against a local mock IdP (generated 1024-bit keypair); dev HS256 provably isolated when OIDC is enforced
- **HL7 v2 MLLP stub listener**: MLLP framing, minimal MSH/PID parse, MSA|AA acks, receipts audited (never acted on)
- Background AMSV telemetry sampler (configurable Hz) into the time-series store
- BioOS shell extended: `news2`, `drift`, `audit`, `auth` commands

### Cognitive Plane
- **Golden-case evaluation harness**: 9 frozen clinical cases (verbatim NTI dosing ×7, hallucinated-token rejection, live kernel metformin lockout at eGFR 22) with a scoring runner; **guard-bypass detection proven** (a backend that approves everything fails the hallucination case)
- **Drift monitor**: approval-rate control limits (HIGH = guard bypass, LOW = schema drift), wired to the runtime and audit chain

### Quality Engineering
- **WCET harness** measuring all six kernel C-ABI paths: kernel_step p50 2.7 µs / p99 8.1 µs (Windows) and 4.6/11.3 µs (container) vs the 100 µs budget of the 1000 Hz loop
- **Sustained-load soak harness**: 1,846 mixed clinical requests / 12 s, zero failures, chain intact, latency stable across windows (roadmap 4.11 closed)
- **Web consistency gate**: 7 structural tests — every referenced DOM id exists, every inline handler is defined, every toggled class has CSS, NEWS2 panel wired, H-11 negation semantics locked
- **Route-level integration tests**: auth enforcement matrix (401/403/200 per role), NEWS2 flow with hand-computed NEWS2=14 sepsis physiology, FHIR bundle shapes, 422 fail-loud validation
- CI: rustfmt gate, clippy `-D warnings`, host tests, Linux cdylib build, **Cortex-M4F no_std build**, **STM32 board-support build**

### Fixed
- Inverted `is_alert` semantics in the observation form (would have silently mis-scored obtunded patients)
- Duplicate runtime-configuration section in README; stale paths and port numbers corrected
- NTI dual-panel wiring: verdicts now mirror to both the biometrics-form and CR-slider panels

### Deferred (documented, resource-gated)
- P2.1+ hardware bring-up (awaits NUCLEO-F407ZG board — design complete in `docs/p2_on_target_design.md`)
- P3 real vLLM on MI300X (eval harness and adapter contract ready; `services/soak_test.py` unaffected)
- P5 QMS-backed compliance execution (registers and traceability matrix in place)
- Container rebuild + in-container re-verification (Docker Desktop requires interactive restart; CI covers the Linux path)

## [0.1.0] — 2026-10-16

Initial production repository: Tri-Plane architecture (Rust `#![no_std]` safety kernel + Python enterprise plane), 78-bed hospital topology, dual-engine flight deck, kernel bridge, test suites.
