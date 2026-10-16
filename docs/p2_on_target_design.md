# BioOS P2 — On-Target Design Document (Plane A Physical Port)

**Status:** Design, pre-hardware | **Date:** 2026-10-17 | **Inputs:** Sprint 4 embedded proof (thumbv7em-none-eabihf builds clean), Sprint 3 u64 time base, `portable_atomic.rs` spinlock constraints

> This document is the P2 entry artifact. Nothing here is implemented yet; each section maps to a P2.x phase with an exit criterion. Certification language remains *aligned-to* until P5.

## 1. Objective

Move the Plane A safety kernel from a host cdylib (simulation) to a dedicated
Cortex-M4F target with hardware watchdog authority, physical actuator
interlocks, instrumented WCET, and a HIL rig — preserving the existing 16-test
host suite as the golden reference.

## 2. Target Selection

| Criterion | STM32F407VGT6 (selected) | nRF52840 (alternative) | STM32H743 (stretch) |
|---|---|---|---|
| Core | Cortex-M4F 168 MHz | Cortex-M4F 64 MHz | Cortex-M7 480 MHz |
| Flash / RAM | 1 MB / 192 KB | 1 MB / 256 KB | 2 MB / 1 MB |
| Hardware watchdogs | IWDG + WWDG | WDT | IWDG + WWDG |
| MPU | 8 regions | 8 regions | 16 regions |
| Timer capture for WCET | DWT CYCCNT + TIM | DWT + TIMER | DWT + TIM |
| Ecosystem (probe-rs, defmt, embassy) | Excellent | Excellent | Good |
| Match to `thumbv7em-none-eabihf` CI gate | Exact | Exact (hardfloat variant differs) | Requires thumbv7em-none-eabihf compat check |

**Selected: STM32F407VGT6** (e.g., NUCLEO-F407ZG or custom board). Rationale:
the CI already cross-compiles for `thumbv7em-none-eabihf`; dual hardware
watchdogs match the WIE dual-relay model (SSR fast trip / mechanical air gap);
documented errata; lowest integration risk.

## 3. Execution Architecture (P2.1-P2.3: no RTOS)

Phase 1 runs **bare metal, no RTOS**: a fixed-priority interrupt architecture
over a 1 kHz SysTick base, with the existing kernel engines called from
interrupt/loop contexts. Rationale: the kernel is allocation-free and O(1);
an RTOS adds SOUP (certification scope) without an immediate need. Embassy is
deliberately deferred to a P2 extension if async drivers are required.

| Context | Priority | Work | Budget |
|---|---|---|---|
| SysTick ISR (1 kHz) | Highest | ESE sample latch, WIE `evaluate_cycle`, relay decision | <= 100 us (REQ-WCET-001) |
| TIM ISR (100 Hz) | High | Envelope `evaluate_envelope`, alpha-floor | <= 500 us |
| Main loop | Lowest | Telemetry marshalling to Plane B link, self-test | <= 1 ms slack |

**ISR discipline (closes the `portable_atomic.rs` P2 constraint):** all shared
state touched by ISR + main loop is protected by `cortex_m::interrupt::free`
critical sections (or NVIC BASEPRI masking on the spinlock in
`portable_atomic.rs`). No ISR may spin. This is the documented integration
requirement recorded in that module.

## 4. Time Base (closes the wrap-safety class permanently)

- 64-bit monotonic nanoseconds: 32-bit hardware timer (TIM2, 1 MHz) latched
  with an overflow counter inside its ISR — composed into u64 without race
  (double-read + consistency check).
- DWT CYCCNT (168 MHz) for sub-microsecond WCET measurement.
- Heartbeat source: Plane B link timestamps; on-target `HEARTBEAT_TIMEOUT_NS =
  50_000_000` unchanged. The `wrapping_sub` semantics in `engine4_wie.rs`
  carry over unchanged; the on-target time provider must guarantee monotonic
  u64 (no settable wall clock on the safety path).

## 5. Watchdog & Panic Wiring (closes H-04 residual)

- **IWDG** (independent, LSI-clocked — survives clock failure): refreshed ONLY
  from the SysTick ISR after `WIE.evaluate_cycle` returns non-lockout. A
  hardware lockout deliberately starves the refresh -> IWDG reset as the
  final backstop.
- **WWDG** (windowed, PCLK-clocked): detects early/late refresh (runaway loop).
- **Panic handler replacement** (the `lib.rs` latch-and-spin placeholder):
  1. Latch `WatchdogState::HardwareLockout` into the relay GPIOs (SSR off,
     mechanical air gap open) with polarity locked by hardware.
  2. Record panic reason into noinit RAM for post-mortem.
  3. THEN halt (IWDG will reset if the halt itself hangs).
- Relay GPIOs: SSR + mechanical relay driven by two independent GPIOs with
  READBACK pins (closed-loop proof of relay state, not open-loop trust).

## 6. Actuator & Sensor Interfaces

| Signal | Interface | Notes |
|---|---|---|
| SSR control | GPIO + hardware inverter | Readback required |
| Mechanical relay | GPIO + driver | Readback required; 12 ms mechanical spec |
| Pump motor enable | GPIO | Interlocked with relay state |
| Pump rate | TIM PWM + step/direction | Rate setpoint from envelope ceiling |
| Line pressure | ADC + conditioner | 525 mmHg / 10.2 psi trip (ESE) |
| Air-in-line | Ultrasonic + comparator/CAP | >= 25 uL trip (ESE) |
| Hemolysis index | Plane B link (lab domain) | CLSI C56-A gate is a data interlock |
| Plane B link | UART/USB-CDC or SPI | Heartbeat + setpoints; NEVER actuation authority |

**Freedom from interference:** the actuator GPIOs and relay readbacks are
mapped into an MPU-protected region writable only by the SysTick ISR context;
Plane B has no physical path to them (separate cortex, separate supply domain
desired). The B-advises/A-executes invariant becomes a PHYSICAL property.

## 7. Memory Budget (static audit required at P2.3)

Current host-audited footprint is small (kernel engines are O(1), 0-heap);
target: RAM < 64 KB of 192 KB (headroom for ISRs stacks), Flash < 256 KB of
1 MB. The MISRA-style static audit (linker map review, `size` output in CI)
is a P2.3 exit criterion. No dynamic allocation exists today and must not be
introduced (0-heap invariant).
## 8. Plane B Link Contract (unchanged invariant, physical enforcement)

The link carries: heartbeat timestamps, laboratory values (K+, hemolysis),
and advisory setpoints. The kernel IGNORES any setpoint exceeding its own
interlocks — the existing PVE/ESE/WIE engines remain the sole authority. New
on-target requirement: the link parser must be bounded (fixed-frame, length-
checked, CRC) — a malformed Plane B frame may never stall the SysTick ISR.
Parser fuzzing is a P2.7 HIL test item.

## 9. Build & Deploy Pipeline

- Cross-compile: `cargo build --release --target thumbv7em-none-eabihf --no-default-features --features no_std` (already a CI gate).
- Flash + debug: `probe-rs` (cargo-flash / cargo-embed), RTT for defmt logs.
- Logging: `defmt` + `defmt-rtt` behind a feature flag (compiled OUT of the
  safety path by default; logging must not affect WCET in release builds).
- Binary artifacts: `.elf` + `.bin` published per CI run with the SBOM.
- **SOUP register (P5 linkage):** `libm`, `cortex-m`, `cortex-m-rt`, `stm32f4xx-hal`, `probe-rs` (host side). Each entry needs version pinning + license + known-issues review.

## 10. HIL Test Rig (P2.7)

- Rig host: Raspberry Pi 4 (or second NUCLEO) acting as pump/vent simulator:
  drives pressure/voltage analogues into the ADC, captures relay readback
  transitions with a logic analyzer (validates the 2 ms / 12 ms trip latencies
  on REAL GPIO, not simulation).
- Test classes: trip-latency capture (REQ-SAFE-002/003), heartbeat-loss
  injection (REQ-SAFE-004 incl. future-stamp injection), watchdog reset storms,
  power brownout/blackout (brownout detector + IWDG interplay), malformed
  Plane B frame flood (parser fuzzing), thermal soak.
- Exit criterion: trip latency measured on hardware within spec across >= 1000
  injections per class, zero missed lockouts.

## 11. Verification & Traceability Additions

- **WCET instrumentation:** DWT CYCCNT sampled around each engine call in
  debug builds; on-target budgets: ESE/WIE ISR path <= 100 us (REQ-WCET-001),
  envelope <= 500 us. Host `wcet_benchmark.py` numbers remain host-FFI
  evidence only — on-target numbers supersede them for certification.
- **Formal:** `engine4_wie.rs` Mealy automaton -> Kani proofs (no panic,
  reachability of HardwareLockout on every trip condition, absence of lockout
  without a trip condition). Kani runs on host; results trace to the same
  source.
- **Traceability matrix additions (REQ-SAFE-015+):** on-target watchdog wiring,
  relay readback closed-loop, time-base monotonicity, link parser boundedness,
  MPU region correctness.
- Existing host tests remain the regression base; on-target self-test at boot
  (RAM/flash CRC, relay readback loop, timer tick verification) gates entry to
  operational state.

## 12. Phased Plan & Exit Criteria

| Phase | Deliverable | Exit criterion |
|---|---|---|
| P2.1 | Board bring-up: clocks, RTT logs, LED heartbeat | defmt output over probe-rs; CI artifact flashes |
| P2.2 | 1 kHz SysTick + u64 time base + DWT WCET harness | Tick monotonicity test; WCET harness reports cycles |
| P2.3 | IWDG/WWDG wiring + panic handler replacement + static memory audit | Deliberate hang -> watchdog reset observed; linkers map reviewed |
| P2.4 | Relay/SSR GPIO + readback + WIE decision wiring | Trip latency on GPIO within 2 ms/12 ms spec (logic analyzer) |
| P2.5 | ADC pressure + ultrasonic air sensor into ESE | Trip conditions detected from physical signals |
| P2.6 | Plane B bounded link + heartbeat | Frame-flood soak: ISR never stalls; malformed frames rejected |
| P2.7 | HIL rig + fault injection campaign | Section 10 exit criteria met |
| P2.8 | Release build freeze + SBOM + SOUP review | Artifacts + register complete; hand-off to P5 |

## 13. Risks

| Risk | Mitigation |
|---|---|
| Spinlock (PortableAtomicU64) priority inversion under ISR load | Interrupt-masking discipline (section 3); measure worst-case lock hold; long-term: per-context data ownership to eliminate shared cells |
| defmt/logging perturbs WCET | Logging behind feature flag, excluded from release measurement builds |
| HAL crate as large SOUP surface | Pin exact versions; wrap all HAL access behind the existing `hal.rs` trait boundary |
| Host/on-target behavioral divergence | Same source, same tests; HIL replays the host golden vectors |
| Relay readback disagrees with command | Treat readback as truth: immediate mechanical air gap + lockout latch |

## 14. Immediate Next Actions (no hardware required)

1. `cortex-m`/`cortex-m-rt`/`stm32f4xx-hal` added behind a `target-stm32`
   feature (host builds unaffected; CI gains an on-target build gate when the
   deps land).
2. Interrupt-masking wrapper for `PortableAtomicU64` spinlock (cortex-m
   critical section) behind the same feature.
3. Panic-handler replacement skeleton (latch -> noinit -> halt) behind the
   feature.
4. Linker script + memory.x for F407VG (flash/ram regions, noinit section).
5. This document reviewed and signed off before any hardware order.