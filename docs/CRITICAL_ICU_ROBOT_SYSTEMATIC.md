# Critical ICU Robot — Systematic Monitoring & Conditional Analysis

> **Beyond OR:** Critical robot does not *do* surgery. It *tunes beyond* — continuous ICU aware monitoring, buffer-fast analysis, calling doctor only when arguable.

## 1. ICU Room 10 — Maintained Staffing (What We Have)

| Role | Count | Maintains | Monitors Base |
|------|-------|-----------|---------------|
| Staff Nurse | 2 | 5 beds each | Vitals, intake/output, drains, position, infusion pumps |
| Head Nurse | 1 | All 10 | Staff load, triage, handoffs, audit, escalation |
| Junior Doctor | 1 (in-ICU) | First response | qSOFA, shock index, vent settings, orders |
| Attending | 1 (on-call) | Decisions | Only when conditional analysis triggers |
| **Critical Robot** | 1-2 mobile | *Everything above, simultaneously* | All signals + position + machinery network |

**Robot is not replacement** — it is *encrypted-network* extension: fixed LiDAR+UWB position (±2cm), machinery VLAN (pumps, vent, monitors, beds), attains position to detect everything, assists nurse to stabilise, then *calls doctor* with pre-analysed packet.

## 2. Base Monitor Required — Systematic List (What Exactly)

### A. Nurse-Maintained (2 nurses x 5 beds)
1. **Physiological Core (per bed, 1Hz)** — ECG, arterial pressure (MAP), CVP, SpO2, EtCO2, temp, urine output, blood loss, BIS
2. **Device State** — pump rate vs ordered, vent PIP/PEEP/FiO2, drain volume, bed angle, restraint
3. **Human Observations** — pain score, GCS, skin (pressure injury), agitation, family presence
4. **Conditional triggers** — MAP <65, SpO2 <90, urine <0.3 ml/kg/h, drain >100ml/h bright red

### B. Head Nurse-Maintained (10-bed view)
1. **Load Matrix** LoadFactor = Σ(patient acuity)/nurse_count — surge if >3.0
2. **Triage Queue** TriageTag Green/Yellow/Red/Black per `surge_engine` — capacity_pct
3. **Degraded Modes** task-shifting, single-use reuse, load-shedding electives
4. **Audit** PEAP: Plan shift, Exec handoffs, Audit missed checks, Prepare restock

### C. Doctor-Maintained (junior + attending)
1. **Shock Index** SI = HR/SBP — conditional >1.2 ⇒ fluid bolus + call attending
2. **qSOFA/SOFA Trending** — via `StateSpace` prediction 30min ahead
3. **Vent Liberation Readiness** — RSBI, P/F ratio, spontaneous breathing trial gate
4. **Antibiotic Timeout** — 48h review, de-escalation

## 3. Robot Injection — What It Adds (Precisionless Precision)

Robot is **trained capable** (not learning on patient) + **encrypted machinery network** (TLS 1.3, VLAN isolated from hospital WiFi) + **position-aware** (UWB anchors in ceiling, attains (x,y,θ) every 100ms).

**Collects faster than nurse+robot together via buffer:**
- Circular buffer per bed: 10s @ 500Hz (ECG, pressure waveform) — nurse sees 1Hz, robot analyses 500Hz buffer in <50ms
- Machinery bus sniff: reads pump CAN, vent RS485, bed MQTT without touching device
- Position: knows *which* bed, *which* nurse is at bed, distance to crash cart — no manual entry

**Analyses extended deeper:**
- `dft_magnitude(waveform)` → hidden arrhythmia not visible on monitor
- `convolve(vitals_history, hemorrhage_impulse)` → predicts hypotension 4min early
- `StateSpace` liver/kidney twin → `prime_viability` drift, suggests `capillary leak` before edema

**Precisionless Precision = 0.1 mm actuation + 1 ms determinism, no jitter** — robot never does surgery here, only *positions* sensors, adjusts bed angle ±0.5°, holds ultrasound probe still for nurse.

## 4. Conditional Analysis — Control Systems + Engineering Math

**Every conditional is a control law with gate:**

| Condition | Signal | Formula | Control Action |
|-----------|--------|---------|----------------|
| Hemodynamic instability | MAP, HR | `SI = HR/SBP` ; `TF step_response predicts MAP 2min` | Nurse stabilize: 250ml crystalloid, re-eval, call doctor if `StabilityAnalyzer::is_stable_den` fails |
| Hypoxia | SpO2, FiO2 | `P/F = PaO2/FiO2` ; Shannon capacity check | Increase FiO2 via `PID(kp=0.8)` gated by `gain_margin>6dB` |
| Sepsis | Temp, lactate, WBC | `qSOFA ≥2` ; `convolve(temp, infection_kernel)` | Head nurse triggers `surge_level=Elevated`, reserve bed |
| Waterborne after disaster | Wound + water | `WaterContam.risk>0.8 && wound erythema` | PostCare: clean-water irrigation, doxycycline, `SurgeProtocol` field hospital |

**Engineering equations applied to ICU (not just OR):**
- **Oxygen delivery** `DO2 = CO * CaO2 *10` — StateSpace output y
- **Fluid responsiveness** `PPV = (PPmax-PPmin)/PPmean` — TransferFunction from fluid bolus to MAP
- **Workload** `LoadFactor = Σ acuity / staff` — used for `SurgeLevel::from_load()`
- **Latency budget** `deadline - WCET` — communication fabric enforces `nyquist_ok(fs>2*fmax)`

## 5. Nurse + Robot Collecting → Doctor Call Flow

```
[Robot @ bed 3, 10:00:00.000] acquire 500Hz buffer → ArtifactDetector(Motion) → DriftCorrector → dft → detects VT 3-beat run (monitor shows normal)
[Robot] → encrypted MQTT → Head Nurse tablet: "Bed3 conditional: VT run, SI=1.3, prime_viability 0.82→0.78"
[Head Nurse] PEAP Audit: needs_replan=true → Prepare: re-allocate nurse2 to bed3
[Nurse2+Robot] stabilize: robot holds probe, nurse gives fluid (robot timed 250ml @ 999ml/h, PID clamped)
[Conditional] SI still >1.2 after 5min → Robot auto-calls Junior Doctor with packet: waveform buffer + StateSpace 5-min prediction + suggested norepi 2mcg/min (gated by Routh-Hurwitz)
[Junior→Attending] only if `Sev=Critical` and `gain_margin` stable
```

**Buffer as faster:** Robot buffers 10s high-freq, analyses while nurse hands-on. To treat, nurse does not wait for central monitor — robot already flagged 50ms after event. Thoughts + figure extended deeper via `tissue_interaction.expected_force` and `prime_viability`.

Verification: `cargo check` clean for `control_system`/`awareness`/`surge_engine`/`post_care` + new `icu_critical_robot`.
