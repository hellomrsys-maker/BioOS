# BioOS (BioSentinel OS) Master Architecture & Specification

**Dual-Plane Asymmetric Medical AI Operating System**  
*Compliant with IEC 62304 Class C, ASTM F2761 / AAMI 2700-1 ICE, and ISO/IEEE 11073 SDC*  
*Version 1.0 — Production Reference Specification*

---

## 1. System Overview & Core Philosophy

### 1.1 The Governing Invariant
> **"Software is probabilistic and can fail; physical medical hardware requires zero-failure determinism. The OS must apply hardware-grade reliability to software."**

BioOS is organized into two decoupled computational planes linked by a shared state vector:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                  BIOOS TOPOLOGY                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   PLANE A: Hard Deterministic Real-Time Kernel (Rust #![no_std] / C++20)         │
│   • Sub-millisecond (1000 Hz) execution loop (τ_tick = 1000 µs)                  │
│   • Zero dynamic heap allocation on safety path; bounded O(1) execution time     │
│   • Sole authority over physical actuators (smart infusion pumps, ventilators)   │
│   • Enforces immutable physiological limits and hardware interlocks              │
│                                                                                  │
│                                        ▲                                         │
│                                        │ Atomic Memory State Vector (AMSV)       │
│                                        │ (64-byte lockless Seqlock shared memory)│
│                                        ▼                                         │
│                                                                                  │
│   PLANE B: Accelerated Cognitive & Enterprise Plane (AMD Instinct / ROCm / vLLM) │
│   • Clinical reasoning, natural language CDS generation (Llama-3.1-8B)           │
│   • Grammar-constrained JSON output (XGrammar / LOINC / RxNorm / SNOMED CT)      │
│   • Hospital operations, RTLS bed turnover, predictive flow & reverse triage     │
│   • INVARIANT: PLANE B ADVISES; PLANE A EXECUTES.                                │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 The Governing Theorem (IEC 62304 Class C Freedom from Interference)
$$\forall F \in \{\text{crash, hang, GPU fault, memory corruption, hallucination}\}, \quad \text{Actuators}(F) \equiv \text{Actuators}(\text{Plane B Disconnected})$$
No software bug, model hallucination, or hardware fault in Plane B can ever expand the safe physical envelope of Plane A.

---

## 2. The Plane Boundary: 64-Byte Atomic Memory State Vector (AMSV)

The single contract between Plane A and Plane B is a 64-byte, cache-line-aligned, lockless shared memory segment protected by a Seqlock:

```
Offset  Size  Field                          Type / Encoding
0       8     seq_ctr (monotonic epoch)      u64 (even = stable; odd = write in progress)
8       4     t_write_ns (kernel monotonic)  u32 (monotonic nanoseconds)
12      2     device_class                   u16 (IEEE 11073-10101 MDS type)
14      2     metric_code                    u16 (IEEE 11073-10101 numeric id)
16      4     value_x1000                    i32 fixed-point (e.g. mL/hr, mmHg, mmol/L)
20      4     quality_flags                  u32 bitfield (VALID, DNP, CAL_EXP, DRIFT, HIL_VOID)
24      2     hil_h                          u16 (Hemolysis index: mg/dL free Hb)
26      2     hil_i                          u16 (Icterus index: mg/dL bilirubin)
28      2     hil_l                          u16 (Lipemia turbidity index)
30      2     limit_state                    u16 (DERS limit state: 0=OK, 1=SOFT, 2=HARD)
32      4     rate_setpoint_x10              u32 (Flow rate setpoint in 0.1 mL/hr units)
36      4     rate_actual_x10                u32 (Actual measured flow rate in 0.1 mL/hr)
40      4     occlusion_mmhg                 u32 (Piezoresistive in-line pressure in mmHg)
44      2     alarm_class                    u16 (IEC 60601-1-8 priority: 0=None, 1=Low, 2=Med, 3=High)
46      2     crc16                          u16 (Payload error verification)
48      1     global_mode                    u8 (0 = ROUTINE, 1 = SURGE, 2 = DISASTER)
49      1     active_escalation_tier         u8 (Tier 0 to Tier 3)
50      2     facility_census_bitmap         u16 (ED, ICU, Ward saturation vectors)
52      4     hics_incident_id               u32 (Disaster incident command identifier)
56      8     system_checksum                u64 (Cryptographic epoch validation)
Total: 64 Bytes (Exact single L1 cache line on x86-64 / AMD EPYC / ARM64).
```

### Seqlock Read Protocol (Plane A, $O(1)$, Allocation-Free):
1. Read `seq_ctr`. If `seq_ctr % 2 != 0` (write in progress), spin or back off.
2. Copy the 64-byte payload.
3. Read `seq_ctr` again. If changed or odd, retry (bounded retries).
4. **Freshness Invariant**: If `now - t_write_ns > 2 * T_tick`, degrade to `CAUTION`.

---

## 3. The Six Dedicated Engines

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ENGINE ARCHITECTURE OVERVIEW                    │
├──────────────────────────────────┬─────────────────────────────────────┤
│ ENGINE 1: ESE (Physical Sensors) │ Hardware Telemetry, Pumps, HIL Gate │
│ ENGINE 2: BPE (Biomarkers & Path)│ CKD-EPI 2021, MELD-Na, κ_immuno     │
│ ENGINE 3: PVE (Pharmacovigilance)│ Dettli Ceiling Law, NTI Drug Tables │
│ ENGINE 4: WIE (Safety Watchdog)  │ IEC 62304 Class C O(1) Interlocks   │
│ ENGINE 5: COE (Cognitive AI)     │ AMD ROCm / vLLM, RFC 9162 Merkle Log│
│ ENGINE 6: OCE (Command Center)   │ Flow Routing, RTLS, HICS Disaster   │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

### Engine 1: Physical Equipment & Sensor Telemetry Engine (ESE)
* **Standards**: ISO/IEEE 11073-10207 SDC (BICEPS), ASTM F2761 ICE Supervisor, CLSI LIS01/LIS02.
* **The Potassium Gate (CLSI C56-A)**:
  $$\text{If } H\text{-index} > 20 \text{ (Roche cobas standard): } \text{INVALIDATE } K^+ \text{ READING}$$
  * Hemolysis releases intracellular potassium, causing false pseudohyperkalemia. The ESE automatically sets `quality_flags |= HIL_VOID` and locks all potassium dosing.
* **Smart Pump Hardware Bounds**:
  * Volume accuracy: $\pm 1\%$ to $\pm 2\%$ (Syringe), $\pm 5\%$ (Peristaltic).
  * Downstream Occlusion: Hard trip at $10.2\text{ psi}$ ($525\text{ mmHg}$) for rates $\ge 30\text{ mL/hr}$.
  * Ultrasonic Air-in-Line: Instant trip on single bubble $\ge 25\ \mu\text{L}$ or cumulative air $\ge 100\ \mu\text{L/hr}$.
* **LLoQ Left-Censoring**:
  * Real-time PCR viral loads below detection floor (e.g., HBV/HCV DNA $< 20\text{ IU/mL}$) are clamped to `DETECTED_NOT_QUANTIFIED` and cannot be multiplied numerically.

---

### Engine 2: Quantitative Biomarker & Pathogen Dynamics Engine (BPE)
Deterministic, fixed-point $O(1)$ clinical calculations:

1. **2021 CKD-EPI Race-Free eGFR**:
   $$\text{eGFR} = 142 \times \min\left(\frac{S_{cr}}{\kappa}, 1\right)^\alpha \times \max\left(\frac{S_{cr}}{\kappa}, 1\right)^{-1.200} \times 0.9938^{\text{Age}} \times [1.012\text{ if female}]$$
   * $\kappa = 0.7$ (F) / $0.9$ (M); $\alpha = -0.241$ (F) / $-0.302$ (M).
   * Input clamp: $S_{cr} \ge 0.05\text{ mg/dL}$.

2. **Cockcroft-Gault CrCl with 3-Tier Dosing Weight**:
   $$\text{CrCl} = \frac{(140 - \text{Age}) \times \text{Weight}_{\text{dosing}}}{72 \times S_{cr}} \times [0.85\text{ if female}]$$
   * $\text{IBW}_{\text{male}} = 50 + 2.3 \times (\text{Ht}_{in} - 60)$; $\text{IBW}_{\text{female}} = 45.5 + 2.3 \times (\text{Ht}_{in} - 60)$.
   * Underweight ($\text{Actual} < \text{IBW}$): Use Actual Weight.
   * Normal ($1.0 \le \text{Actual}/\text{IBW} \le 1.2$): Use IBW.
   * Obese ($\text{Actual} > 1.2 \times \text{IBW}$): Use Adjusted Body Weight:
     $$\text{ABW} = \text{IBW} + 0.4 \times (\text{Actual} - \text{IBW})$$

3. **MELD-Na Score (2016 UNOS/OPTN)**:
   $$\text{MELD-Na} = \text{MELD} + 1.32 \times (137 - \text{Na}) - [0.033 \times \text{MELD} \times (137 - \text{Na})]$$
   * Clamped: $\text{Na} \in [125, 137]$, $\text{Creatinine} \in [1.0, 4.0]$, $\text{Bilirubin} \ge 1.0$, $\text{INR} \ge 1.0$.

4. **Child-Pugh Score**:
   * Evaluates Bilirubin, Albumin, INR, Ascites, and Encephalopathy $\to$ Class A (5–6), Class B (7–9), Class C (10–15).

5. **Pathogen Risk Multiplier ($\kappa_{\text{immuno}}$)**:
   $$\kappa_{\text{immuno}} = 1 + \sum_{p} \sigma\left(\frac{L_p - \theta_p}{s_p}\right)$$
   * Scales active viral replication and bacteremia ($TTP < 12\text{ h}$). Can **only decrease** allowable drug ceilings.

---

### Engine 3: Pharmacovigilance & Dosage Verification Engine (PVE)

1. **The Deterministic Ceiling Law**:
   $$\text{Ceiling} = \min\Big(\text{LabelMax},\ \text{DERS}_{\text{hard}},\ \text{Band}_{\text{renal}}(\text{eGFR}) \times \text{Band}_{\text{hepatic}}(\text{ChildPugh}) \times \text{LabelMax},\ \div \kappa_{\text{immuno}}\Big)$$

2. **The Zero-Hallucinated-Dose Principle**:
   * **The AI model NEVER outputs a numeric dose.** It outputs an enum key: `LOOKUP_REF(VANC_AUC_TIER_2)`.
   * Engine 3 deterministically resolves the exact dose from precompiled, signed lookup tables.

3. **Narrow-Therapeutic-Index (NTI) Register**:
   * **Metformin**: Absolute contraindication if $\text{eGFR} < 30\text{ mL/min/1.73m}^2$ (fatal lactic acidosis).
   * **Vancomycin**: Target AUC/MIC $400–600$; extend interval from q8–12h to q24–48h if $\text{CrCl} < 30\text{ mL/min}$.
   * **Gentamicin**: Hartford nomogram $7\text{ mg/kg}$; course capped at 96 hours; trough $< 2\ \mu\text{g/mL}$.
   * **Digoxin**: CrCl $< 60 \to$ reduce to $0.0625–0.125\text{ mg/day}$; lock if $K^+ < 3.2\text{ mEq/L}$.
   * **Enoxaparin**: CrCl $< 30 \to$ 50% dose reduction ($1\text{ mg/kg}$ q24h).
   * **Low-Dose Methotrexate**: Absolute contraindication if $\text{CrCl} < 30\text{ mL/min}$. Daily dosing prohibited.

4. **Tisdale QTc Prolongation Risk Summation**:
   * Additive drug-risk summation. Score $\ge 11$ trips a mandatory hardware alert and locks additional QT-prolonging agents.

---

### Engine 4: Deterministic Watchdog Interlock Engine (WIE)
* **Runtime**: Freestanding Rust (`#![no_std]`), zero heap allocation, $O(1)$ lookup complexity.
* **Three Operational States**:
  * `State 0: NORMAL` (Actuators active, baseline monitoring).
  * `State 1: CAUTION` (Soft limit warning, setpoint clamped, AI proposals frozen).
  * `State 2: HARDWARE_LOCKOUT` (ASTM F2761 trip, relay de-energized, pump motor halted, IEC 60601-1-8 high-priority alarm).
* **Trip Latency**:
  * Electronic solid-state cutoff: **$\le 2.0\text{ ms}$**.
  * Complete mechanical relay dropout: **$\le 12.0\text{ ms}$**.
* **Safety Invariant**: WIE trip matrix is **mode-invariant**. Even in a disaster, patient safety interlocks never degrade.

---

### Engine 5: Cognitive Orchestration & Audit Engine (COE)
* **Compute**: AMD Instinct MI300X via ROCm 6.x and vLLM.
* **Dual-Model Safety Ensemble**: Runs `Llama-3.1-8B` (reasoning) alongside `Llama-Guard-3-8B` (auditing) on a single GPU (`--gpu-memory-utilization 0.45` each). Any guard disagreement triggers an automatic reject.
* **Constrained Decoding**: Enforces Context-Free Grammars (XGrammar) restricting JSON output strictly to pre-compiled FHIR ValueSets (SNOMED CT, LOINC, RxNorm).
* **RFC 9162 Append-Only Merkle Audit Tree**:
  $$\text{Leaf}_i = \text{SHA-256}(0\text{x}00 \parallel E_i), \quad \text{Chain}_i = \text{SHA-256}(\text{Chain}_{i-1} \parallel \text{Leaf}_i)$$
  Signed hourly with Ed25519 Signed Tree Heads (STH).

---

### Engine 6: Operational Command Engine (OCE) & Hospital Logistics
* **Hospital Escalation Index ($E_I$)**:
  $$E_I = w_1 \left(\frac{\text{ED Boarding Time}}{\mu_{\text{boarding}}}\right) + w_2 \left(\frac{\text{ICU Occupancy}}{\text{Total ICU Beds}}\right) + w_3 \left(\frac{\text{PACU Holds}}{\text{OR Capacity}}\right)$$
  * Tier 0 ($< 1.0$): Nominal.
  * Tier 1 ($1.0–1.5$): Charge nurse alert; discharge lounge expedited.
  * Tier 2 ($1.5–2.0$): Observation bed conversion; elective admissions throttled.
  * Tier 3 ($\ge 2.0$): Command Center activation; elective surgeries paused.
* **Autonomous Bed Turnover Loop**: RTLS patient exit event $\to$ auto-dispatch EVS $\to$ verified clean $\to$ bed marked `AVAILABLE` with zero phone calls.
* **Massive Hemorrhage Protocol ("The 7 Ts")**: Triggered by Shock Index $> 1.0$ or $\text{ABC} \ge 2$; auto-coordinates Blood Bank, Trauma, Lab, and initiates balanced $1:1:1$ transfusion with continuous BLE/RFID cold-chain tracking.
* **Nurse-Driven Protocols (NDPs)**: Standing order sets for Sepsis 1-hour bundle, ACS chest pain (ECG $< 10\text{ min}$), and hypoglycemia.
* **Dual-Division ICU Environmental Control**: BACnet/SC interface commanding ASHRAE 170/241 airflow:
  * Negative Pressure AIIR: $\ge -2.5\text{ Pa}$ ($-0.01\text{ in. w.g.}$), $\ge 12\text{ ACH}$.
  * Positive Pressure PE: $\ge +2.5\text{ Pa}$ ($+0.01\text{ in. w.g.}$), $\ge 20\text{ ACH}$.
  * Inter-division swing pod inversion completed in $< 180\text{ seconds}$.

---

## 4. The Three Operational Regimes Matrix

| Domain | ROUTINE | SURGE | DISASTER |
| :--- | :--- | :--- | :--- |
| **Command Center (OCE)** | Elective optimization; routine bed turns | Escalation Tiers 1–3 active; reverse triage armed | HICS Incident Command; elective services halted |
| **Safety Kernel (Plane A)** | Closed-loop device control; standard alarms | Standard closed-loop; filtered nuisance alarms | **Maximum redundancy; safety interlocks invariant** |
| **Cognitive AI (Plane B)** | Longitudinal trends; CDS advisory | Bottleneck queueing; nurse protocol matching | Mass-casualty triage (START/SALT); regional coordination |
| **Nurse Autonomy** | Standard standing orders | Accelerated triage labs | Disaster triage protocols (auto-logging) |
| **ICU Architecture** | Fixed Medical vs Surgical division | Dynamic swing-pod flexing | Universal surge pods; max-capacity airlock locks |
| **Network & Comms** | Cloud sync; regional FHIR feeds | Traffic prioritized for alarms | Hardened local optical mesh; WAN disconnected |

---

## 5. Technical Implementation Blueprint

```
bio-os/
├── crates/
│   └── bioos-kernel/              # Plane A: Rust (#![no_std]) Microkernel
│       ├── Cargo.toml
│       └── src/
│           ├── lib.rs             # Crate root
│           ├── amsv.rs            # 64-byte Atomic Memory State Vector + Seqlock
│           ├── engine1_ese.rs     # H-index > 20 potassium gate & sensor drift
│           ├── engine2_bpe.rs     # CKD-EPI 2021, Cockcroft-Gault, MELD-Na, κ_immuno
│           ├── engine3_pve.rs     # Dettli ceiling law & NTI drug tables
│           └── engine4_wie.rs     # Deterministic O(1) Watchdog Interlock State Machine
│
├── services/
│   ├── cognitive_plane/           # Plane B: AMD ROCm / vLLM Service
│   │   ├── engine5_coe.py         # Constrained JSON decoder + Merkle audit log
│   │   └── amd_vllm_adapter.py    # ROCm 6.x GPU connector
│   │
│   └── command_center/            # Engine 6: Hospital Operational Command (OCE)
│       ├── engine6_oce.py         # Escalation Index, RTLS bed loop, HICS state
│       └── fhir_facade.py         # FHIR R4/R5 Subscriptions & HL7 v2 MLLP
│
└── web/                           # Real-Time Medical Flight Deck UI
    ├── index.html                 # High-contrast clinical cockpit & command tiles
    ├── app.js                     # Telemetry streaming & hardware watchdog trips
    └── style.css                  # Safety-critical design system
```

---

*Authored for the BioSentinel OS Open-Source Medical Operating System Project.*
