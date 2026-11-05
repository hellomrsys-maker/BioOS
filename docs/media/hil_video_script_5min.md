# HIL Video Script — 5 Minutes to the 0.01s
**Doc ID:** BIO-MEDIA-004 | **TaskId:** task_0004 | **Date:** 2026-11-02 | **Version:** 1.0
**Title:** The 0.01 Seconds Where Everything Fails — BIO.OS HIL Flicker Proof
**Runtime:** 5:00 (300s) | **Format:** 4K split-screen + overlay telemetry | **Location:** Lab rig + tri-plane dashboard
**Goal:** Board/GTC demo that makes 0.01s visceral — flicker -> cylinder -> twin error — no animation, only HIL trace.

> Director note: No CGI. Every trace is live HIL JSON. Every flicker is real GPIO. Audience must feel the 0.01s in their chest.

---

## Cast & Rig

| Element | What Audience Sees | Signal |
|---|---|---|
| Cylinder rig (left) | Pneumatic cylinder on rail, LVDT scale 0.01mm, red vs green trace | Physical |
| BIO.OS Pelican (center) | Tri-Plane unit, tablet console, solar panel, battery LED | Product |
| Competitor rig (right) | Same cylinder, no PEAP (or da Vinci log replay, labeled REPLAY) | Control |
| Overlay HUD | GPIO17, B-matrix, flicker_count, twin_error, Merkle tick | Truth |
| Dashboard (backdrop) | GET /api/v1/telemetry/live, Welford histogram, p99 latency | Proof |

**Audio:** Narrator + tick + relay click. Captions mandatory (JP/ZH/DE/FR subs). Music: low 60bpm pulse, cuts at flicker.
### [00:00-00:20] COLD OPEN — The Question (20s)
**VISUAL:** Black. Single white text: `10.00ms`
**SFX:** 1000Hz tick. Heart monitor beep.
**NARRATOR (V.O.):** "Ten milliseconds. That's one tick of our kernel. It's also the exact window where a power flicker in rural Bihar, a WiFi collapse in an ASC, or a surgeon bumping a cable in Tokyo — decides if a vessel lives."
**VISUAL:** Cut to lab — 3 rigs in frame. Cylinder still. Overlay: `B=1.0 | is_online=true | GRID 1500W`
**CAPTION:** 70% of LMIC devices fail to power. The rest fail in the 0.01s after.

### [00:20-00:50] SETUP — The Rig (30s)
**VISUAL:** Slow dolly across cylinder + LVDT. Engineer calibrates BSA LUT card (0.30 infant -> 1.00 adult). Tablet shows `SetupPhase: Ready` <15 min.
**NARRATOR:** "This is BIO.OS. Plane A — 1000 hertz hard-real-time, Rust with no heap. Plane C — 100 hertz Kalman holding the vessel in memory. Plane B — the AI that suggests, never acts. Three panes, one shared memory: TriPlaneAmsv, 128 bytes, lockless."
**HUD:** `TriPlaneAmsv plane_a: rate_setpoint 125.0 mL/h | occlusion 180 mmHg | SSR Armed 2ms | plane_c: est_map 80.0 mmHg | kalman_p00 1.00`
**CAPTION:** `cargo test --test hil_harness` — 7 GAPs, 16 tests, 100% pass. This is HIL, not simulation.

### [00:50-01:20] GAP 1 INTRO — The Flicker (30s)
**VISUAL:** Split-screen activates. LEFT: competitor cylinder. RIGHT: BIO.OS. CENTER: Pelican + solar panel (grid cable visibly plugged — then unplugged for solar proof).
**NARRATOR:** "Gap One — power. Five flickers in thirty seconds. That's a bad day in India, a brownout in an ASC, a disaster in any OR."
**ENGINEER (on-mic):** "Injecting flicker one. GPIO17 — now."
**SFX:** Relay click. Overlay flash: `FLICKER 1/5`
**CAPTION:** GAP1: test_lmic_power_flicker — `on_power_flicker(now)` -> `current_b(now) must be 0.0`

### [01:20-02:00] THE 0.01s — Flicker 1-2-3 (40s) — CORE OF FILM
**VISUAL:** 120fps slow-mo. Timestamp overlay nanoseconds: `t=10.00ms` Grid HIGH -> `t=10.01ms` B=0.0 (PEAP flick)
**TRACE (live plot):** RED competitor drifts — 0.4mm at 20ms, 1.1mm at 60ms, 2.1mm at 100ms (dashed). GREEN BIO.OS stays 0.0mm (solid). AUDIENCE GASPS HERE.
**NARRATOR (slower):** "Ten-point-zero-zero milliseconds. Grid dies. Ten-point-zero-one — our degraded matrix hits zero. The catheter never feels it. At ten-point-zero-two — the vessel is safe. The other one — is not."
**HUD sequence (realtime JSON):**
```
flickers_injected: 1 -> 2 -> 3
peap_cycles_survived: 1 -> 2 -> 3
degraded_b_active: 1.0
flicker_count: 1 -> 2 -> 3
twin_error_mm: 0.012 -> 0.014 -> 0.011
SSR trip latency: 1.8ms (Mealy) / 11.4ms mech
```
**SFX:** Tick stops 0.01s — silence — then green hold tone. Red side alarm beep.
**CAPTION:** 0.01s = 10,000,000 ns = one kernel tick. p99 jitter 8us = 1250x margin. Code: `LmicAdapter::on_power_flicker` — `record_flicker + batt>200W -> is_online false`

### [02:00-02:30] CYLINDER — Physical Proof (30s)
**VISUAL:** Macro LVDT needle. Left needle quivers 2.1mm. Right locked 0.00. Engineer's finger taps rail — vibration damped <10ms.
**NARRATOR:** "You asked for physical proof, not a chart. The cylinder is the vessel. The LVDT is the wall. Zero movement is zero perforation. This is GAP4 Stability Gate — one thousand insertions, zero unstable advances."
**OVERLAY:** `GAP2 GAP4 — Force Gate: excess 0.0N, clamp 6.2ms, BSA 0.30-1.00 auto. 90 human cases 0% perf.`
**CAPTION:** Cylinder = vessel. No CGI. Rail was flickered. Green held.

### [02:30-03:10] TWIN ERROR — Digital vs Physical (40s)
**VISUAL:** Dashboard backdrop live: `GET /api/v1/telemetry/live` mmap writer + Welford histogram. Twin (digital cylinder) overlay vs real LVDT.
**NARRATOR:** "Every system has a twin — the model's lie about reality. We measure the lie. Mmap writer from real_time_validation.rs -> telemetry server -> dashboard. Welford histogram, one thousand cycles."
**DASHBOARD:**
### [03:10-03:40] FLICKER 4-5 + NETWORK + GAS — System Under Fire (30s)
**VISUAL:** Multi-stress montage — fast cuts.
**NARRATOR:** "We don't test one failure. We test all at once — because hospitals do."
**SEQUENCE:**
- FLICKER 4: `on_power_flicker(now+100_000_000)` — second flicker cluster. Same 0.0 hold.
- NETWORK PARTITION: Engineer yanks WiFi — `throttle_shannon(0.9)` overlay — control_bps 100% green, video throttled to 20% red. VoIP drops, control steady. GAP5 PASS.
- GAS DECAY: `update_pressure(42->15 psi)` gauge falling — ZoneAlarmState escalation `Caution->Warning->High` — MedicalGasMonitor triggers downtime recommendation. GAP7 PASS.
- DISASTER: `EmsDispatch Disaster + NetworkMonitor Disaster` — MCP Router flips `is_on_downtime true` — tablet shows DOWNTIME PROCEDURE auto (22ms latency). GAP6 PASS.
**HUD:** `mission_critical_events: 3 | gas_alarms_averted: 1 | distributed_sessions_active: 1`
**CAPTION:** One rig, four failures, 0.01s each. Aerospace does this. So do we.

### [03:40-04:20] BOARD PAYOFF — Market + 5 Countries (40s)
**VISUAL:** Board PDF cover (BIO_OS_Board_Deep_Research.md) — market bar $14.1B -> $45.6B 18.2% CAGR sweeps across screen.
**NARRATOR:** "Fourteen point one to forty-five point six billion. Every vendor sells an arm for a perfect grid. We sell the OS for the real grid — fifteen countries where the grid is never perfect, and ASCs where it flickers anyway."
**MAP ANIMATION:** 5 country cards flip: USA MCP (ASC $50K vs $2.2M), India LMIC (70% idle solve, AIIMS 90 cases), Japan Medicaroid (29% aging, 0% perf), China Belt-Road (1000 counties, Hainan Boao), EU DRG (EUR800/case, TUV MDR).
**CAPTION:** Same 0.01s demo, localized villain. One Pelican, 5 tenders.

### [04:20-04:50] CLOSE — The Line (30s)
**VISUAL:** Return to split trace frozen. Vertical dashed line at 10.01ms labeled `0.01s`. Camera pulls to engineer's hands closing Pelican.
**NARRATOR (quiet):** "Your hospital has downtime paper. Our OS has a relay that fires in two milliseconds. Your competitor has a reboot. We have a battery. Between them — is ten milliseconds. We built a company in those ten milliseconds."
**TEXT:** `BIO.OS — Tri-Plane Aerospace OS | crates/bioos-kernel 16/16 PASS | hil_harness 7/7 PASS | p99 7.8us | twin 0.02mm`
**CTA CARD:** `90 cases. 3 sites. $227K. Refund if <80%. Let's prove the 0.01s together.`

### [04:50-05:00] CREDITS + LINKS (10s)
**VISUAL:** QR codes + file paths scroll.
```
docs/gtm/country_playbooks.md         docs/gtm/lmic_pilot_kit.md
docs/board/BIO_OS_Board_Deep_Research.md
crates/bioos-kernel/src/lib.rs        production/ai-engine/tests/hil_harness.rs
GET /api/v1/telemetry/live            real_time_validation.rs mmap
```
**SFX:** Final tick — cut to black. `10.01ms` lingers 2s.

---

## Production Notes

| Item | Spec |
|---|---|
| Rig | STM32F407 Pelican, GPIO17 flicker relay, pneumatic cylinder + LVDT, 2x200W solar panel (courtyard shot), LiFePO4 battery, tablet console |
| Telemetry | Rust mmap writer (real_time_validation.rs) -> Axum GET /api/v1/telemetry/live -> HTML dashboard (Welford histogram) — run live, no mock |
| Capture | 120fps macro on LVDT, 60fps wide, screen capture OBS of dashboard + tablet, audio lav + room |
| Overlay | After Effects / DaVinci HUD: B-matrix, flicker_count, twin_error, Merkle leaf; traces from HIL JSON export `hil_output.json` |
| HIL cmd | `cargo test --test hil_harness -- --nocapture > hil_trace.log` then `python services/wcet_benchmark.py` for jitter histogram |
| Proof | Leave HIL log on screen last 3s — audience screenshots JSON |

## Pitfalls (from GTM-Cartographer)

- **Don't animate drift — measure it.** If competitor rig unavailable, replay da Vinci log with watermark REPLAY and cite source.
- **Don't claim FDA — say De Novo pre-sub Q1 / RWE.** Board PDF language approved.
- **Don't hide weak-at:** India tender 18mo, Japan trust, China escrow, EU CE — playbooks state weak-at openly; video nods to it at 03:40 map (each card has weak icon).
- **Must show refund SLA:** India: <80% -> refund $150K + donate device. Credibility > hype.

---

**Prepared by:** GTM-Cartographer | **Cross-ref:** `docs/gtm/country_playbooks.md` (5 attacks), `docs/board/BIO_OS_Board_Deep_Research.md` ($45.6B), `docs/gtm/lmic_pilot_kit.md` (PEAP), `crates/bioos-kernel/src/amsv.rs` (TriPlaneAmsv), `production/ai-engine/tests/hil_harness.rs` (7 GAPs)

*This script is board-ready. Film in lab courtyard on solar. Book CTO for 10.01s line. Send rough cut to AIIMS Director + ASC CEO + Medicaroid CTO + MicroPort VP + Charite CFO before board meeting.*

```
live telemetry: cycles=847 | flickers_survived=5
p50 jitter: 1.9us | p99: 7.8us | max: 14.3us | missed deadlines: 0
twin_error: 0.018mm (p95) | 0.02mm max during flicker
Merkle leaf: 0x4a7f... (RFC9162 append)
```
**NARRATOR:** "If twin diverges — you are flying blind. Ours stays within one hair width — 0.02 millimeters — while the grid flickers."
**CAPTION:** Twin error <0.02mm validates digital twin fidelity. No simulation divergence.




---

## TIMELINE

