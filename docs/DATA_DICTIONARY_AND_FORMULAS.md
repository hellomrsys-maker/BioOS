# BioOS Medical Data Dictionary, Mathematical Formulas & Safety Registers
**Standard Compliance:** IEC 62304 Class C, CLSI C56-A, ASTM F2761, ISO/IEEE 11073 SDC  
**System Version:** 1.0.0-PROD  

---

## 1. Laboratory & Sensor Physics Thresholds

### 1.1 Hemolysis, Icterus, Lipemia (HIL) Indices (CLSI C56-A)
- **Hemolysis Index ($H$):**
  - $H \le 20\text{ mg/dL}$ (Equivalent free hemoglobin): **ACCEPTABLE**. Potassium reading valid.
  - $H > 20\text{ mg/dL}$: **UNACCEPTABLE (VOID)**. Pre-analytical artifact due to mechanical cell lysis.
  - **Clinical Safety Rule:** $\text{If } H > 20 \implies \text{Potassium} = \text{VOID (NaN)}$. Flag `QUALITY_HEMOLYSIS_REJECTED`. The system *refuses* to emit any potassium value to downstream clinical dosing or alert engines to prevent fatal pseudohyperkalemia intervention.
- **Icterus Index ($I$):** Bilirubin interference threshold $> 15\text{ mg/dL}$. Flags total protein and creatinine Jaffe assays.
- **Lipemia Index ($L$):** Turbidity interference threshold $> 250\text{ mg/dL}$. Flags electrolyte indirect ISE dilution.

### 1.2 Physical Infusion Actuator Safety Limits
- **Hydrostatic Occlusion Pressure:**
  - Soft Warning: $8.0\text{ psi}$ ($413\text{ mmHg}$).
  - Hard Trip Deadline: $10.2\text{ psi}$ ($525\text{ mmHg}$) $\implies$ Cut motor power $\le 2\text{ ms}$.
- **Ultrasonic Air-In-Line Detection:**
  - Cumulative Bubble Threshold: $\ge 25\ \mu\text{L}$ within a sliding $15\text{-minute}$ window $\implies$ Trip shutoff valve $\le 2\text{ ms}$.
  - Single Bolus Bubble: $> 50\ \mu\text{L} \implies$ Immediate emergency line clamp.
- **Lower Limit of Quantitation (LLoQ):**
  - Viral PCR (HIV/HCV): LLoQ $= 20\text{ IU/mL}$. Values $< 20$ are left-censored to $0\text{ IU/mL}$ with `<LLOQ` flag.
  - High-Sensitivity Troponin I (hs-cTnI): LLoQ $= 2.0\text{ ng/L}$. Values $< 2.0$ censored.

---

## 2. Biometric & Pharmacokinetic Formulas (Engine 2)

### 2.1 2021 CKD-EPI Race-Free eGFR Formula
$$\text{eGFR} = 142 \times \min\left(\frac{S_{\text{cr}}}{\kappa}, 1\right)^\alpha \times \max\left(\frac{S_{\text{cr}}}{\kappa}, 1\right)^{-1.200} \times 0.9938^{\text{Age}} \times [1.012 \text{ if female}]$$
Where:
- $\text{Female}$: $\kappa = 0.7\text{ mg/dL}$, $\alpha = -0.241$
- $\text{Male}$: $\kappa = 0.9\text{ mg/dL}$, $\alpha = -0.302$
- $S_{\text{cr}}$ is standardized serum creatinine in $\text{mg/dL}$.
- $\text{Age}$ is in years.

### 2.2 Devine Ideal Body Weight (IBW) & Adjusted Body Weight (ABW)
- **Devine Formula:**
  - $\text{Male IBW (kg)} = 50.0 + 0.905 \times (\text{Height}_{\text{cm}} - 152.4)$
  - $\text{Female IBW (kg)} = 45.5 + 0.905 \times (\text{Height}_{\text{cm}} - 152.4)$
- **Body Mass Index (BMI):**
  $$\text{BMI} = \frac{\text{Weight}_{\text{kg}}}{(\text{Height}_{\text{m}})^2}$$
- **Weight Selection Rule:**
  - If $\text{BMI} < 18.5$: $\text{Dosing Weight} = \text{TBW}$ (Total Body Weight).
  - If $18.5 \le \text{BMI} < 25.0$: $\text{Dosing Weight} = \text{IBW}$.
  - If $\text{BMI} \ge 25.0$: $\text{Dosing Weight} = \text{ABW} = \text{IBW} + 0.40 \times (\text{TBW} - \text{IBW})$.

### 2.3 Cockcroft-Gault Creatinine Clearance ($CrCl$)
$$CrCl = \frac{(140 - \text{Age}) \times \text{Dosing Weight}_{\text{kg}}}{72 \times S_{\text{cr}}} \times [0.85 \text{ if female}]$$

### 2.4 Jelliffe Kinetic Clearance (Acute Kidney Injury)
When serum creatinine changes dynamically by $> 0.3\text{ mg/dL/day}$, steady-state formulas fail.
$$\text{Kinetic } CrCl = \frac{\text{Creatinine Production Rate} \times \left(1 - \frac{\Delta S_{\text{cr}} \times \text{Volume of Distribution}}{\text{Baseline } S_{\text{cr}} \times \Delta t}\right)}{S_{\text{cr, mean}}}$$

### 2.5 MELD-Na (2016) Equation (End-Stage Liver Disease)
$$\text{MELD(i)} = 9.57 \times \ln(\text{Cr}) + 3.78 \times \ln(\text{Bilirubin}) + 11.20 \times \ln(\text{INR}) + 6.43$$
$$\text{MELD-Na} = \text{MELD(i)} + 1.32 \times (137 - \text{Na}) - \left[0.033 \times \text{MELD(i)} \times (137 - \text{Na})\right]$$
Boundaries: $\text{Cr} \in [1.0, 4.0]\text{ mg/dL}$, $\text{Bilirubin} \ge 1.0\text{ mg/dL}$, $\text{INR} \ge 1.0$, $\text{Na} \in [125, 137]\text{ mEq/L}$.

### 2.6 Immunocompromise Risk Factor ($\kappa_{\text{immuno}}$)
$$\kappa_{\text{immuno}} = 1.0 + \sum_{j} w_j$$
Weights:
- Absolute Neutrophil Count ($ANC < 500/\mu\text{L}$): $+0.80$
- Active Solid Organ Transplant on Immunosuppressants: $+0.60$
- Corticosteroid Therapy ($\ge 20\text{ mg/day}$ prednisone equivalent $> 14\text{ days}$): $+0.40$
- Severe Protein-Calorie Malnutrition (Albumin $< 2.5\text{ g/dL}$): $+0.25$

---

## 3. Pharmacological Safety Registers (Engine 3)

### 3.1 Narrow Therapeutic Index (NTI) Register Table

| Drug ID | Drug Name | Route | Clearance Organ | Hard Contraindication Boundary | Therapeutic Monitoring Target | Maximum Daily Dose |
|---|---|---|---|---|---|---|
| `NTI_METFORMIN` | Metformin Hydrochloride | PO | Renal | $\text{eGFR} < 30\text{ mL/min/1.73m}^2$ (Immediate Lockout) | Serum Lactate $< 2.0\text{ mmol/L}$ | $2000\text{ mg/day}$ (Halved if $\text{eGFR } 30-44$) |
| `NTI_VANCOMYCIN` | Vancomycin IV | IVPB | Renal | Unadjusted dose with $\text{CrCl} < 20$ without level | Target AUC/MIC $400-600\text{ mg}\cdot\text{h/L}$ | $2000\text{ mg}$ single loading; interval based on CrCl |
| `NTI_GENTAMICIN` | Gentamicin Sulfate | IVPB | Renal | Acute anuria ($CrCl < 10$) | Trough $< 1.0\ \mu\text{g/mL}$, Peak $5-10\ \mu\text{g/mL}$ | $7\text{ mg/kg}$ once daily (Hartford nomogram) |
| `NTI_DIGOXIN` | Digoxin | IV/PO | Renal (85%) | Hypokalemia ($K^+ < 3.5$) or $\text{CrCl} < 15$ unadjusted | Target Serum Level $0.5 - 0.9\text{ ng/mL}$ | $0.25\text{ mg/day}$ ($0.125\text{ mg}$ if impaired) |
| `NTI_ENOXAPARIN` | Enoxaparin Sodium | SubQ | Renal | $\text{CrCl} < 30$ at standard $1\text{ mg/kg q12h}$ | Anti-Xa target $0.6 - 1.0\text{ IU/mL}$ | Dose adjust to $1\text{ mg/kg q24h}$ if $\text{CrCl} < 30$ |
| `NTI_METHOTREXATE` | Methotrexate | PO/IV | Renal | $\text{CrCl} < 30$ or concurrent NSAIDs | Leucovorin rescue monitoring | $25\text{ mg/week}$ (Rheum); Oncology per protocol |

### 3.2 Dettli Linear Elimination Law
For drugs cleared predominantly by renal excretion:
$$K_e = K_{nr} + \alpha \times CrCl$$
The renal clearance band is:
$$\text{Band}_{\text{renal}} = \frac{CrCl_{\text{patient}}}{120.0}$$
Safety Clamping:
$$\text{Max Permissible Dose} = \min\left(\text{LabelMax}, \text{DERS}_{\text{hard}}, \text{Band}_{\text{renal}} \times \text{Band}_{\text{hepatic}} \times \text{LabelMax}, \frac{\text{LabelMax}}{\kappa_{\text{immuno}}}\right)$$

### 3.3 Tisdale Drug-Induced QTc Score Register
Risk Factors:
1. Age $\ge 68$ years: 1 point
2. Female sex: 1 point
3. Loop diuretic administration: 1 point
4. Serum $K^+ \le 3.5\text{ mEq/L}$: 2 points
5. Admission QTc $\ge 450\text{ ms}$: 2 points
6. Acute Myocardial Infarction: 2 points
7. Sepsis: 3 points
8. Heart Failure with reduced ejection fraction: 3 points
9. One QTc-prolonging drug: 3 points
10. $\ge 2$ QTc-prolonging drugs: 3 additional points (Total 6 points)

**Risk Stratification:**
- Low Risk: $\le 6$ points (Standard monitoring)
- Moderate Risk: $7 - 10$ points (Telemetry alert, electrolyte optimization)
- High Risk: $\ge 11$ points (**HARD LOCKOUT**: Blocks concurrent prescription/infusion of Class IA/III antiarrhythmics, haloperidol, fluoroquinolones, or ondansetron without signed attending override).

---

## 4. Hospital Escalation & Operational Metrics (Engine 6)

### 4.1 Hospital Escalation Index ($E_I$) Formula
$$E_I = 0.35 \times E_{\text{ED}} + 0.25 \times I_{\text{ICU}} + 0.20 \times N_{\text{Deficit}} + 0.10 \times O_{\text{OR}} + 0.10 \times S_{\text{Supply}}$$
Where each variable is normalized to $[0.0, 1.0]$:
- $E_{\text{ED}} = \frac{\text{Current ED Census} + \text{Waiting Room Count}}{\text{Total ED Treatment Bays}}$
- $I_{\text{ICU}} = \frac{\text{Occupied ICU Beds}}{\text{Licensed ICU Beds}}$
- $N_{\text{Deficit}} = \max\left(0.0, 1.0 - \frac{\text{Rosters On-Duty Nurses}}{\text{Mandated Staffing Floor}}\right)$
- $O_{\text{OR}} = \frac{\text{Active Emergency OR Cases}}{\text{Staffed Operating Rooms}}$
- $S_{\text{Supply}} = 1.0 - \min\left(1.0, \frac{\text{Lowest Critical Stock Count}}{\text{Safety Threshold Buffer}}\right)$

### 4.2 Operating Regimes
- **Tier 0 (ROUTINE):** $E_I < 0.40$
- **Tier 1 (YELLOW SURGE):** $0.40 \le E_I < 0.60$ (Defer non-urgent maintenance, alert EVS)
- **Tier 2 (ORANGE SURGE):** $0.60 \le E_I < 0.75$ (Cancel elective elective cases, expedite reverse triage)
- **Tier 3 (RED DISASTER):** $E_I \ge 0.75$ or Mass Casualty Declaration (HICS Incident Commander mobilized, RTTL triage discharges activated, MHP standing activation).
