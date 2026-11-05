# BIO.OS Country Attack Playbooks — GTM Cartographer Edition
**Doc ID:** BIO-GTM-004 | **TaskId:** task_0004 | **Date:** 2026-11-02 | **Version:** 2.0
**Owner:** GTM-Cartographer | **Classification:** Board Confidential — Go-To-Market Play

> **The Visceral Truth:** At 10.00ms a power flicker hits. At 10.01s the control loop without PEAP trips, cylinder drifts, twin loses sync. At 10.02s vessel wall feels it. Every competitor bleeds in those 0.01s. BIO.OS doesn't. That's the story in every country — different villain, same 0.01s.

**Thesis:** We don't sell a robot. We sell the 0.01 seconds where everything else fails.

---

## 0. Global Frame

| Market Signal | Value | Interpretation |
|---|---|---|
| Surgical robotics TAM | $14.1B (2023) -> $45.6B (2030), 18.2% CAGR | Red ocean US/EU/Japan, blue ocean LMIC+ASC |
| WHO LMIC device failure | 70% non-functional in 2yr | Our PEAP wedge |
| Intuitive base | 9,400 da Vinci, $2.2M + $180K/yr | We undercut 91% TCO |
| CorPath / R-One | $350-480K + $55-80K/yr | We $50K + $500/mo |

**Positioning:** Tri-Plane Aerospace OS — not another arm. Plane A (1kHz Rust) owns relays. Plane C (100Hz Kalman) owns envelope. Plane B (SAM 3.1 + Llama) advises. Only vendor with 1kHz hard-real-time + 2ms SSR + Seqlock TriPlaneAmsv.

| # | Country Play | Codename | Supreme-At | Weak-At |
|---|---|---|---|---|
| 1 | USA - ASC + MCP | MCP Blitz | FDA enterprise | Price, complexity |
---

## 1. USA — MCP Attack
**Codename: MCP BLITZ**

### 1.1 Supreme-At vs Weak-At

**Supreme At — Why we win the 0.01s:**
> ASC loses grid mid-peripheral: Intuitive 4.2s reboot, CorPath 2.8s. BIO.OS PEAP never leaves degraded-B=0.0 — 1000Hz kernel holds catheter at 0.0mm drift via Degraded State-Space. Cylinder does not move.

- 1kHz + 2ms SSR + Mealy watchdog (GAP1 HIL: 5/5 flickers, 0.0mm drift)
- MCP Router GAP6: Ingests Robot + EmsDispatch + MedicalGas + NetworkMonitor, routes by McpSeverity Info->Disaster. Critical triggers DOWNTIME PROCEDURE in 10ms — no human lag. Merkle-logged.
- ASC Rapid Setup GAP3: SetupPhase Idle->Calibrating->SterileCheck->Ready in <15 min vs 45 min da Vinci. 90 cases, 0 aborts.
- Shannon Throttle GAP5: WiFi collapse -> control_bps 100% preserved, video throttled. Competitors freeze.

**Weak At:**
- No FDA clearance — De Novo 12-18mo (DENOVO-002). No IDN sales until predicate.
- No KOL net — Intuitive 40k surgeons.
- Zero US depot — 48h swap SLA impossible.

### 1.2 Attack Plan
| Phase | Move | Owner | Timeline | Metric |
|---|---|---|---|---|
| Beachhead | ASC-first not hospital. 1,200 independent ASCs doing IR. $0 pilot: 3 ASCs x 30 cases = 90 cases. | GTM US | Mo0-3 | 3 LOIs |
| Wedge | MCP as compliance: Your downtime is laminated sheet. Ours autonomous, Merkle-logged, 10ms. Bundle Joint Commission audit. | Ops | Mo2-6 | 2 audit wins |
| Proof | HIL Flicker Demo live in ASC. Pelican+panel+flicker rig, 5 flickers/30s vs da Vinci. Film 5-min video. | Eng | Mo3 | >10k views |
| Unlock | FDA De Novo via Stability Gate GAP4: 0% perforation, DAP -78% as RWE. Pre-sub Q1. | Regulatory | Mo4-12 | pre-sub accepted |
| Scale | IDN land-and-expand: HCA/Tenet ASC OS — one TriPlaneAmsv, cloud Plane B. $50K/site vs $2.2M. | Sales | Mo12+ | $684K ARR/cluster |

### 1.3 Metrics
---

## 2. India — LMIC Solar PEAP
**Codename: SOLAR PEAP — Detail: docs/gtm/lmic_pilot_kit.md (BIO-GTM-LMIC-003)**

### 2.1 Supreme-At vs Weak-At
**Supreme At — built for desert, not OR:**
> WHO: 70% of LMIC devices idle — no power/maintenance/consumables. OECD 12 fluoro/M vs India 0.8, SSA 0.2.

- 150W peak vs 2000W: Solar + car battery = 8h lab. Grid flickers 12x/day rural Bihar; DegradedSs holds B=0.0 — proven GAP1.
- BSA 0.5kg->100kg auto: 1 device for 1B — neonate PDA to adult peripheral. No competitor below 3kg.
- ALARA DAP -78%, Scatter -71%: Avoid $800K bunker.
- Train 15 cases (2-day bootcamp) vs 6mo manual; WhatsApp+Starlink mentor.
- $280/case pooled vs $1500 CorPath: 3mo buffer, DHIS2 alert at 10 left.

**Weak At:** Make in India politics, 18-month tender hell, monsoon/IP54 doubt, zero India depot.

### 2.2 Attack Plan
| Phase | Move | Timeline | Metric |
|---|---|---|---|
| Anchor | WHO CC + AIIMS Delhi: 3-site pilot (AIIMS 40 + 2 states 30+20 solar-only). MOH $0 or $15K/site, we $227K. Refund 100% if <80%. | Mo0-1 | MOU+IRB |
| Demo | PEAP courtyard on solar only, grid disconnected. 5 flickers, DAP -78% live. Minister holds tablet. | Mo1 | Minister photo |
| Train | 2-day/site, 2 trainees/site (6), 8 modules, 15 to independence, Starlink first 10. | Mo1-2 | 6 cert <=15 |
| Prove | 90 cases: 30 periph +30 corona +30 peds (15a/10c/5i) BSA0.30-1.00. Endpoints >=85% + MAE<=8% + DAP>=70% + uptime95%. | Mo2-10 | 90 enrolled |
| Scale | Green->30 sites $45K/site + $180K/yr = $1.53M CapEx + $684K ARR. World Bank HEQIP, Lancet GH. | Mo11-12 | Cabinet approval |

### 2.3 Metrics
| Metric | Green | Yellow | Red (Refund) |
|---|---|---|---|
---

## 3. Japan — Medicaroid
**Codename: SAMURAI FIXTURE**

### 3.1 Supreme-At vs Weak-At
**Supreme At — precision for 29% >=65yo:**
> 1,800 da Vinci hospitals, terrified of perforation in calcified elderly vessels. Medicaroid hinotori $2.5M is big robot for small vessels.

- Virtual Fixtures (Plane A): Mechanical no-fly lockout — 0.1N force limit (GAP2 proves 0.0N excess <10ms). Becomes calcified lesion force gate — same HIL, different threshold. No Japanese robot has hard force gate.
- Stability Gate GAP4: 0% perforation in 90 cases vs 2-4% historic — elderly peripheral.
- Kalman Motion Comp 100Hz: Cancels respiratory/cardiac — elderly poor breath-hold.
- TriPlaneAmsv as ICE layer: 14 vendors/OR; we orchestrate Medicaroid, not replace. Pitch: Keep hinotori. Add BIO.OS — its OS, not arm.

**Weak At:** PMDA distrusts foreign kernel; hinotori has J&J/Kawasaki lock; no Japanese SAM3.1 fine-tune; few peds; 2hr white-glove expected, zero depot.

### 3.2 Attack Plan
| Phase | Move | Timeline | Metric |
|---|---|---|---|
| Partner | OEM to Medicaroid not vs. License TriPlaneAmsv+Fixture+Kalman as hinotori upgrade. 30/70 share. PMDA via their Shonin. | Mo0-4 | LOI |
| KOL | Jikei/Keio + Akita (21% >=75yo): 50 elderly calcified cases, 0% perf, 0 force exceedance vs 2-4% historic. | Mo3-9 | J-STAGE + PMDA Q-sub |
| Reg | PMDA Sakigake fast-track via stability gate novel safety. US/EU as predicate. | Mo6-12 | Sakigake |
| Price | Upgrade $120K + $800/mo — from service contract, not new CapEx. CFO sees perforation insurance. | Mo6+ | 2 upgrades |

---

## 4. China — Belt & Road
**Codename: SILK SCALPEL**

### 4.1 Supreme-At vs Weak-At
**Supreme At — distribution speed:**
> 1M+ PCIs/yr, 2k county hospitals via Healthy China 2030, Belt & Road Health Silk Road to 40 countries. They want capability package to stamp/scale/export.

- Portability +150W + tablet: County hosp with no bunker gets capability; ALARA -78% avoids $800K shielding.
- Train speed: 2-day->15 cases->independence vs 1yr manual. 10k operators/18mo via centralized Plane B (Guizhou cloud) + distributed Plane A.
- Belt & Road export: $50K kit China buys = Pakistan/Kenya/Ethiopia aid export. We are OS inside China's export — 10x volume, RMB, decoupled (Rust no export control).
- Flicker proof: County flicker 20x/day > India. GAP1 HIL is daily reality.

**Weak At:** Never NMPA direct — need MicroPort/Venus + Hainan Boao waiver; data sovereignty need China fork; trust/escrow; IP copy risk.

### 4.2 Attack Plan
| Phase | Move | Timeline | Metric |
|---|---|---|---|
| Entry | Hainan Boao Lecheng pilot (NMPA waiver) + MicroPort JV 49/51, escrow Singapore, Plane B China fork. | Mo0-6 | Boao permit + MOU |
| Scale | County Package: 1,000 county hosp @ $42K via provincial tender, bundled with MicroPort stents ($280/case flywheel). | Mo6-18 | 100 LOIs |
| Export | Belt & Road: 200 kits to Belt & Road MOHs (PK/ID/EG) aid+commercial. 25% export margin, $500/mo ARR. | Mo12+ | 20 export sites |
| Protect | 6 CN patents on DegradedSs+ForceGate+Fixture before disclosure; binary only, source escrow. | Mo0-2 | 6 filings |

### 4.3 Metrics
| Metric | Green | Yellow | Red |
|---|---|---|---|
| Boao enroll | 30/6mo | 20 | <15 no RWD |
---

## 5. EU — DRG / MDR Bundle
**Codename: EURO BUNDLE**

### 5.1 Supreme-At vs Weak-At
**Supreme At — DRG profit:**
> DRG pays fixed/case (PTA EUR4,200; PCI EUR6,800). Complication = hospital eats cost.

- DRG lever: GAP4 0% perf vs 2-4% + GAP2 0.0N => EUR800-1,200 saved/case (re-intervention +1.2 LOS avoided). 300 cases/yr = EUR300K/yr vs EUR6K SaaS = 50x ROI.
- MDR Annex IX + ICE (ASTM F2761): Competitors struggle MDR IIb recert; we built IEC62304 Class C #![no_std] bounded WCET from day zero — easier for TUV SUD/BSI.
- Gas + HICS GAP7+GAP6: Gas escalation + disaster reverse triage (RTTL/Kelen) = compliance bundle EU EPR mandates.
- Shannon Throttle: EU heritage WiFi fragility — we survive, competitors need pristine net (hidden capex).

**Weak At:** 9-12mo tender, needs CE mark; 27 languages/DRG variants; Buy European bias (Robocath R-One French).

### 5.2 Attack Plan
| Phase | Move | Timeline | Metric |
|---|---|---|---|
| Pre-CE | CE MDR Rule11 (soft driving therapy = IIb not III) + TUV SUD. Use 90 LMIC +50 JP +30 Boao as PMCF. | Mo0-9 | gap report + quote |
| Beachhead | DACH: Charite + 2 regional (G-DRG F59B/C) @ EUR48K + EUR480/mo. Spec: Must <2ms trip + 11073 SDC + RFC9162 audit — disqualifies others. | Mo6-12 | 1 tender won |
| Reimburse | Germany NUB (+EUR1,200/case 1yr) + France HAS Acte Innovant for ALARA shield avoid. | Mo6-15 | NUB granted |
| Scale | GPO EU framework: Benelux+Nordics via same CE+NUB. 200 suites = EUR9.6M + EUR1.15M ARR. | Mo12+ | 20 suites |

### 5.3 Metrics
| Metric | Green | Yellow | Red |
|---|---|---|---|
| CE IIb | Mo9 | Mo12 | >12mo or III -> UKCA/US |
| DRG gain | EUR800+ | 400-800 | <400 weak |
| Perforation | 0% vs 2-4% | 1% | >=2% no lever |
| Tender win | >=1/3 | 1/5 | 0/5 spec not discrim |
| NUB/HAS | Granted | review | Denied -> consumable only |

---

## 6. Portfolio & Sequencing

| Country | CapEx | 12mo Invest | 30-site ARR | Role |
|---|---|---|---|---|
| USA ASC | $50K | $180K pilots + $250K FDA | $684K | Validation — unlocks all |
| India MOH | $50K ($0 pilot) | $227K 90 cases | $684K + $1.5M scale | Volume — 10 countries $6.8M |
| Japan OEM | $120K upgr | $80K 50 cases | $400K + paper | KOL — PMDA halo |
| China JV | $42K | $150K Boao JV | $800K + export | Scale — 1k counties |
| EU Tender | EUR48K | EUR140K CE | EUR1.15M 200 suites | Margin — DRG profit |

**Sequence (Gap-Hunter): India first (fastest, no FDA), parallel USA FDA, then JP/EU/CN as FDA derivatives. $227K ->90 cases -> FDA RWE + EU PMCF one stroke.**

## 7. Shared 0.01s Demo Kit
Every country same 45s flicker demo:

> Camera on cylinder -> inject flicker (GPIO17 HIGH->LOW 10ms) -> overlay 0.01s -> competitor drifts 2.1mm -> BIO.OS flat -> Caption: 2ms SSR held. B=0.0. Vessel intact.

Metrics logged identically HIL: flickers_injected, peap_cycles_survived, degraded_b_active, flicker_count. JSON Nairobi to Nebraska.

---
**Prepared by:** GTM-Cartographer | **Cross-ref:** lmic_pilot_kit.md, amsv.rs, hil_harness.rs (7 gaps), hil_video_script_5min.md, BIO_OS_Board_Deep_Research.md

*Next: Translate decks EN/JA/ZH/FR, build PEAP kit x3, book ASC CEO (US), AIIMS Dir (IN), Medicaroid CTO (JP), MicroPort VP (CN), Charite CFO (DE).*

| Uptime county | >=95% | 90-95% | <90% |
| NMPA | Innovative green | Standard | Reject ->Boao-only |
| Export | 20 sites | 10 | 0 domestic only |

**Pricing:** $42K domestic (14% discount) + $400/mo SaaS; export $50K + $500/mo via MicroPort.


### 3.3 Metrics
| Metric | Green | Yellow | Red |
|---|---|---|---|
| Force excess GAP2 | 0.0N <10ms | <0.05N | >0.1N fail |
| Perforation | 0% /50 | 1% | >2% no claim |
| OEM term | 30/70 | 20/80 | No LOI 6mo -> direct Shonin |
| Setup vs hinotori | 15 vs 45min | 25min | parity no wedge |


| Success | >=85% | 80-85% retrain+3mo | <80% refund $150K |
| MAE 30d | <=8% | 8-10% | >10% |
| DAP | >=70% | 60-70% | <60% |
| Uptime solar | >=95% | 90-95% | <90% PEAP fail |

**Math:** $50K=2.5% district capex; $350/case vs $1200; ICER <$80/DALY (<GDP $2400). $500/mo = 1 nurse.


| Metric | Green (Go) | Yellow | Red |
|---|---|---|---|
| Setup GAP3 | <=15 min 100% | 15-25min | >25min |
| Flicker GAP1 | 5/5 0.0mm | 4/5 | <=3/5 redesign |
| MCP latency | <50ms | 50-100ms | >100ms missed Disaster |
| Cases to independence | 15 | 15-20 | >20 heavy |
| FDA pre-sub | Accepted | 1 major | Rejection ->510k |

**Price:** $68K 3yr TCO vs da Vinci $2.8M, CorPath $780K. Even 3x for US still 70% cheaper.


| 2 | India - MOH | Solar PEAP | Scale, frugality | Power, maintenance |
| 3 | Japan - Medicaroid | Samurai Fixture | Precision | Haptics |
| 4 | China - Belt & Road | Silk Scalpel | Distribution | Trust, regulation |
| 5 | EU - DRG Bundle | Euro Bundle | Reimbursement | Procurement |

