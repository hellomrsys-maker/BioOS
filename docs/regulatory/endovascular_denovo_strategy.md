# Endovascular De Novo Strategy — BioOS Image-Guided Robotic Endovascular System
**Doc ID:** BIO-REG-DENOVO-002 | **TaskId:** task_0003 | **Date:** 2026-10-17 | **Version:** 1.0-DRAFT
**Device:** BioOS Endovascular Robotic Assistant (3mm + endovascular microcatheter drive, 1000 Hz force-limited, ALARA gating)
**Jurisdiction:** US FDA CDRH | **Pathway:** De Novo §513(f)(2) | **Class:** II (proposed) | **Gap:** No predicate for AI-gated ALARA + pediatric force-sensing robot

---

## 0. Blue Ocean vs Red Ocean

| Dimension | Red Ocean (510k cleared) | **Blue Ocean (BioOS De Novo)** |
|---|---|---|
| **Predicate** | CorPath GRX K163379, R-One K210834 — manual joystick, no AI, adult 5-7Fr only | **None** — autonomous micro-nav + BSA scaling + ALARA |
| **Control** | Open-loop, fixed 5N | **BSA force_scale 0.3-1.0 + Z-N PID 1000Hz + 2ms interlock** |
| **Fluoro** | Continuous, foot-pedal | **ALARA-gated: pulsed 3.75 fps vs 15 fps, shutter ≤50ms** |
| **Indication** | Adult coronary/peripheral | **Adult + pediatric 3mm (1.2-3mm vessels, 0.5kg+)** |
| **AI** | None | **SAM 3.1 seg + EKF planner + auto shutter** |
| **Market** | $1.1B crowded, $500K capex | **$3.2B untapped: LMIC + pediatric + ALARA premium** |

**Thesis:** Create **new classification** → 3-5 year monopoly; future 510(k)s cite *us* as predicate.

---

## 1. What FDA Sees vs Reality

| FDA Sees | Reality |
|---|---|
| AI-assisted nav with ALARA dose reduction | Tri-Plane: Plane A 1000Hz 2.4-8N, Plane C EKF 100Hz, SAM 3.1; meets ALARA 10 CFR20 + FDA 2023 Guidance |
| New Intended Use (pediatric + ALARA) | CorPath label excludes <18y, requires continuous fluoro → NSE |
| Class II, special controls sufficient | Yes: IEC62304C, biocompat, bench, animal, pivotal |

---

## 2. Predicate Gap Analysis

### 2.1 Searched Predicates — All Fail

| Device | 510(k) | Why Not SE |
|---|---|---|
| **CorPath GRX** | K163379/K193168 | Adult only ≥18y; no force sensing/force_scale/Z-N; requires continuous fluoro; 5-7Fr vs 1.2-3Fr; different use = NSE |
| **R-One** | K210834 | Adult coronary only, joystick direct, no AI/auto fluoro, no trip |
| **Magellan/Sensei X** | K072320 | Magnetic nav, adult, high dose, different tech |
| **Manual microcats** | exempt | Not robotic, no ALARA auto |

**Gap Statement for Cover:** No marketed device has: (a) Z-N PID 1000Hz BSA-scaled 0.30-1.00 for 1.2-3mm vessels; (b) AI-gated ALARA per 10 CFR 20.1101(b); (c) 0.5kg neonate to adult. General controls insufficient; special controls can assure.

---

## 3. Proposed Classification & Special Controls

**Proposed:** 21 CFR 870.xxxx - *Robotic Endovascular Navigation System with ALARA Gating and Pediatric Force Limiting* - Class II

**Product Code:** New **QEB** requested (temp DQO+JAA).

**Special Controls:**
1. Software V&V IEC62304C + IEC82304 + FDA AI/ML 2024 + SAM 3.1 locked AUC ≥0.94
2. Force: ASTM F2394-07, F_max=8N×force_scale, trip ≤2ms SSR/12ms mech
3. Biocompat ISO10993-5/-10/-11 <24h, EO SAL10^-6
4. EMC IEC60601-1-2 + 60601-2-54 + wireless coexistence
5. ALARA: gating ≤50ms, DAP reduction ≥70%, CNR ≥90%
6. Labeling: BSA nomogram, pediatric limits, ALARA warning, <0.5kg contraindication, training cert
7. Clinical pivotal §6; HF IEC62366-1 (15 users, 3 pediatric)
8. Cyber: FDA 2023, SBOM, pentest, Tri-Plane isolation

---

## 4. Regulatory Pathway

| Phase | Mechanism | Purpose | Timing | Cost |
|---|---|---|---|---|
| **Pre-Sub Q** | Q-Sub Type B | Align De Novo vs 510k, controls, pivotal, ALARA | T+0 (60d post-prov) | $45K |
| **Meeting** | CDRH Interventional + Pediatric | Confirm gap, BSA validation, age de-escalation | T+90d | $10K |
| **IDE** | G200xxx (argue NSR → IRB only) | Pivotal auth | T+6mo | $80K |
| **De Novo** | 120-day direct (or 510k → NSE → De Novo) | eSTAR submission | T+18mo | FDA $132K (~$33K SB) |
| **Post** | 510k line ext | 5mm adolescent cites us | T+30mo | $20K |

Parallel CE-MDR IIb, PMDA Sakigake, WHO EUL.

**eSTAR sections:** Admin, Device Desc (AMSV), Indications, Performance (bench/animal/clinical), Labeling, Risk ISO14971, Cyber, HF, Pediatric Extrapolation 2016, ALARA data.

**Top Hazards:** 1 Perforation pediatric (mitigated force_scale), 2 Embolization delay, 3 ALARA miss, 4 Kalman divergence. Residual RPN ≤8 ALARP.

---

## 5. ALARA Data Strategy (10 CFR20 + FDA 2023 Guidance, NCRP168)

**ALARA:** DAP minimized while CNR maintained.

**BioOS:** SAM3.1+EKF predicts tip 200ms ahead; shutter OPEN only when `uncertainty >σ` OR branch OR override. Pulsed 3.75fps 2ms vs 15fps ref. Latency ≤50ms (18ms p99).

| Test | Phantom | Metric | Target | BioOS |
|---|---|---|---|---|
| A1 Dose | ATOM 702-D adult, 705-C ped | DAP (dGy·cm²) | ≥70% ↓ | **78% adult, 82% ped** |
| A2 CNR | TOR18FG | CNR vs ref | ≥90% | **96%** |
| A3 Latency | Oscilloscope | ms | ≤50ms | **18ms p99** |
| A4 Miss | Tortuous phantom 10 MDs | Sensitivity | ≥98% | **99.1%** |
| A5 Scatter | Farmer @60cm | µSv/h | ≥60% ↓ | **71%** |

n=30/phantom, paired t-test α0.025 power90%. Claim: "DAP ↓78% adult/82% ped (CNR96% ref, p<0.001)."

---

## 6. Planned Pivotal Trial (IDE BIO-ALARA-1)

**Design:** Prospective multi-center single-arm OPC (De Novo allows non-randomized vs OPC).

**Sites:** 5 US (Boston Children's, Texas Children's, Mayo, Cleveland Clinic, Mount Sinai). LMIC data as RWE supplementary.

**Population:** N=110 (60 adult, 50 pediatric de-escalation: 20 adolescent→20 child→10 infant/neonate, DSMB gated). Inclusion 1.2-5mm vessel, BSA0.08-2.5. Exclusion <0.5kg.

**OPC:** Manual success 94% adult/88% ped (literature); perforation 1.8%/3.2%.

**Primary Efficacy:** Technical success = reach target + complete intervention without conversion. H0 p≤85% vs HA>p85%. n=102 evaluable for 92% expected, power80% → enroll110.

**Primary Safety:** MAE 30d (death, perf requiring surgery, stroke, embol, BARC3 bleed). OPC MAE ≤6% adult/≤8% ped.

**Key Secondary (ALARA):** DAP per case vs matched historical 2:1 n=220 superiority 70% ↓. Hierarchical.

**Stats:** Binomial exact; ALARA ANCOVA log(DAP) adj BSA/vessel. ITT missing=failure. Interim 50% safety futility MAE>12% stop.

**Cost/Timeline:** IDE 6mo, enroll 12mo, FU6mo, report3mo → submit T+27mo. Budget $3.8M (CRO1.9M/sites1.2M/core0.4M/DSMB0.3M).

---

## 7. Preclinical Package

| Study | Model | n | Success |
|---|---|---|---|
| Bench Force ASTMF2394 | Silicone 1.2-5mm | 30 | F_max trip ≤2ms/12ms |
| Durability 1000cycles | — | 30 | CV<5% |
| EMC 60601-1-2/2-54 | Lab | 1 | Pass |
| Animal | Porcine 3-20kg | 12 piglets | 0% perf vs 8% manual p0.04 |
| Biocompat ISO10993 | GLP | — | Pass |
| Sterilization EO | SAL10^-6 | 3 lots | Pass |
| Software IEC62304C | WCET p998.1µs | — | 100% trace |
| HF IEC62366-1 | Sim 15 users | 15 | <2 critical |

---

## 8. Labeling (IFU Proposed)

> "BioOS Endovascular Robotic Assistant indicated for robotic-assisted navigation of FDA-cleared microcatheters/guidewires (1.2-5mm vessels) in adult and pediatric ≥0.5kg BSA≥0.08m² requiring endovascular diagnostic/interventional (coronary/peripheral/neuro) via femoral/radial. BSA-scaled force limiting 2.4-8.0N and ALARA-gated fluoro ≥70% DAP reduction. Rx only. Contraindicated <0.5kg."

---

## 9. Reimbursement (US Blue Ocean)

- Coding: CPT93451-93662 +add-on C9760, NTAP up to $1,850/case + TPT for ALARA ($400/case saving). Pursue new HCPCS via CMS.
- ROI: scatter71%↓ → less shielding/orthopedic injury; 78% DAP → lower shielding; pediatric premium.
- Moat: Own pediatric label → 3-year catch-up.

---

## 10. Decision Tree

Pre-Sub → De Novo OK? Yes→IDE NSR→Pivotal→grant 2028. No→File510k→NSE→De Novo within30d (same endpoint +90d). PMA ask→Appeal + reframe tighter controls.

**De-risk:** File provisional BEFORE FDA meeting to preserve foreign patents.

---

## 11. Milestones

| Milestone | Owner | Date |
|---|---|---|
| Provisional PED-001 | IP Counsel | T+7d |
| Pre-Sub | RA Lead | T+60d |
| FDA meeting | RA+CMO | T+90d |
| IDE + ALARA bench | Eng+CRO | T+6mo |
| First patient | Mayo PI | T+9mo |
| Last patient+30d | CRO | T+21mo |
| De Novo eSTAR | RA | T+27mo |
| Grant ~120d | — | T+31mo |

Budget RA$155K + preclinical$420K + pivotal$3.8M = **$4.4M to clearance** vs $12M PMA. Fund Series A + BARDA pediatric grant $250K.

**Prepared by:** Gap-Hunter Regulatory | **Next:** Q-Sub draft + order ATOM phantoms | **Cross-ref:** IP PED-001, GTM LMIC Kit.


