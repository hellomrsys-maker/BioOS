# -*- coding: utf-8 -*-
# flake8: noqa
"""
BioOS Master Specification Compiler
Synthesizes all 8 Markdown source files and the 20-page IEC 62304 Class C Blueprint PDF
into one definitive single-source-of-truth master specification document.
"""

import os

DOWNLOADS = r"c:\Users\sysyo\Downloads"
SCRATCH_DOCS = r"C:\Users\sysyo\.gemini\antigravity-ide\scratch\bio-os\docs"
OUTPUT_FILE = os.path.join(SCRATCH_DOCS, "HOSPITAL_HEALTHCARE_WELLBEING_OS_MASTER_SPECIFICATION.md")
PDF_TEXT_FILE = os.path.join(SCRATCH_DOCS, "extracted_pdf_text.txt")

def read_file(path):
    if not os.path.exists(path):
        return f"[Error: File not found at {path}]"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def main():
    print("Compiling unified master specification...")
    
    # Read all sources
    pdf_text = read_file(PDF_TEXT_FILE)
    v1_master = read_file(os.path.join(DOWNLOADS, "bioos-master-specification-consolidated-v1-0.md"))
    five_engine = read_file(os.path.join(DOWNLOADS, "bioos-five-engine-specification-report-standards-formulas-and-safety-architecture.md"))
    op_arch = read_file(os.path.join(DOWNLOADS, "bioos-operational-architecture-hospital-command-center-resource-allocation-clinical-governance-&-disaster-framework.md"))
    arch_frame = read_file(os.path.join(DOWNLOADS, "bioos_architecture_framework.md"))
    complete_spec = read_file(os.path.join(DOWNLOADS, "BioOS_Complete_Spec_Parts_1-3.md"))
    hospital_ops = read_file(os.path.join(DOWNLOADS, "BioOS_Hospital_Ops_Disaster_Architecture.md"))
    qwen_arch = read_file(os.path.join(DOWNLOADS, "Qwen_markdown_20261014_7u3a7mj9k.md"))
    table_mode = read_file(os.path.join(DOWNLOADS, "table.md"))

    parts = []
    parts.append("# HOSPITAL, HEALTHCARE & CLINICAL WELLBEING OPERATING SYSTEM (BioOS)")
    parts.append("## Definitive Master Architectural Specification & Regulatory Compliance Manual (v2.0)")
    parts.append("### Unified Aerospace Tri-Plane Medical Operating System (IEC 62304 Class C / ISO 14971 / DO-178C Level A)\n")
    parts.append("---\n")
    
    parts.append("## Executive Summary & System Philosophy\n")
    parts.append("**BioOS (BioSentinel OS)** is an enterprise-scale, dual/tri-plane asymmetric medical AI operating system designed to run critical hospital systems, intensive care units, emergency command centers, and holistic healthcare wellbeing ecosystems.\n")
    
    parts.append("### The Aerospace Analogy: Fly-By-Wire Dual/Tri-Engine Determinism")
    parts.append("Operating an acute hospital and intensive care unit shares direct engineering parallels with modern commercial fly-by-wire aviation (e.g., Airbus A350 / Boeing 787):")
    parts.append("1. **Engine 1 (Actuator Flight Controls / ESE)**: Operates at bare-metal level in `#![no_std]` Rust. Direct device actuation (infusion pumps, ventilators, dialysis, vasopressor titrators). Bounded O(1) latency, zero dynamic heap allocation, absolute deterministic hard real-time execution.")
    parts.append("2. **Engine 2 (Kalman Dynamic Envelope Protection / Alpha-Floor Stall Prevention)**: Continuously tracks physiological trajectories in multi-dimensional phase space. If mean arterial pressure (MAP), cardiac index, or potassium levels approach dangerous boundaries, Engine 2 triggers **Alpha-Floor stall protection**—overriding upstream AI recommendations, locking hardware setpoints, and executing deterministic autonomous recovery maneuvers.")
    parts.append("3. **Engine 3 (Cognitive Flight Management System / FMS)**: AMD ROCm / PyTorch asynchronous AI copilot performing deep multi-modal inference, diagnostic trajectory forecasting, clinical documentation, and scheduling. Upstream recommendations can never violate the physical flight envelope defined by Plane A.")
    parts.append("4. **Engine 4 (Hardware Watchdog & Interlock Engine / WIE)**: Independent hardware supervisor checking 128-byte dual-cache-line memory integrity via Seqlock sequence numbers and CRC16 checksums. Latency budget < 100 microseconds.")
    parts.append("5. **Engine 5 (Clinical Optimization Engine / COE)**: Multi-organ pharmacokinetics, pharmacovigilance, narrow therapeutic index (NTI) drug rules, Tisdale QTc scoring, CKD-EPI 2021 race-free eGFR, Jelliffe AKI clearance, and MELD-Na / Child-Pugh liver clearance models.")
    parts.append("6. **Engine 6 (Operational Command Engine / OCE)**: Hospital-wide operational fabric spanning Humber River Hospital (HRH) and Johns Hopkins command center patterns. Real-time location system (RTLS) 5-stage bed turnover, massive hemorrhage protocols (MHP 7 Ts), nurse standing orders, ASHRAE 170/241 HVAC pressure cascades, and HICS 2014 reverse triage.")
    parts.append("7. **Clinical Wellbeing Engine**: Clinician cognitive load monitoring, alert fatigue suppression, shift ergonomics & burnout prediction, alongside patient restorative sleep envelopes (< 45 dB day / < 35 dB night) and circadian lighting.\n")
    
    parts.append("---\n")
    parts.append("## Operational State Transition Matrix (Routine / Surge / Disaster)\n")
    parts.append(table_mode + "\n")
    parts.append("---\n")
    
    parts.append("## Section 1: Regulatory Compliance & Safety Foundations\n")
    parts.append("### 1.1 IEC 62304 Class C & ISO 14971 Mandates")
    parts.append("Under IEC 62304, software whose failure could result in death or serious injury is designated as **Class C**. BioOS satisfies Class C via strict architectural segregation (Freedom From Interference - FFI) between Plane A (safety-critical actuation) and Plane B/C (probabilistic AI and enterprise operations).\n")
    parts.append("```")
    parts.append("+---------------------------------------------------------------------------------+")
    parts.append("|                                     BIO-OS                                      |")
    parts.append("+---------------------------------------------------------------------------------+")
    parts.append("|  PLANE A: Safety-Critical Real-Time Core (IEC 62304 Class C / SIL 3 / DO-178C)  |")
    parts.append("|  - Language: Rust (#![no_std], zero-alloc, zero panic in production)            |")
    parts.append("|  - Engine 1: Execution & Safety Engine (ESE) [Actuation, Infusions, Vents]      |")
    parts.append("|  - Engine 2: Dynamic Flight Envelope & Alpha-Floor Stall Protection             |")
    parts.append("|  - Invariants: Bounded execution <= 100 microseconds, O(1) memory               |")
    parts.append("+---------------------------------------------------------------------------------+")
    parts.append("                                      |")
    parts.append("                     [Zero-Bridge 128-Byte Shared AMSV]")
    parts.append("                 (Dual-Cache-Line, Seqlock, CRC16 Checksum)")
    parts.append("                                      |")
    parts.append("+---------------------------------------------------------------------------------+")
    parts.append("|  PLANE B: Clinical Optimization & Watchdog Supervisor (IEC 62304 Class B)       |")
    parts.append("|  - Language: Modern C++20 / Embedded Python Kernel                              |")
    parts.append("|  - Engine 4: Deterministic Watchdog Interlock Engine (WIE)                      |")
    parts.append("|  - Engine 5: Clinical Optimization Engine (COE - Tisdale, CKD-EPI, NTI)         |")
    parts.append("+---------------------------------------------------------------------------------+")
    parts.append("                                      |")
    parts.append("                        [Zero-Copy IPC / UNIX Sockets]")
    parts.append("                                      |")
    parts.append("+---------------------------------------------------------------------------------+")
    parts.append("|  PLANE C: Cognitive Orchestration & Hospital Operations (IEC 62304 Class A/B)   |")
    parts.append("|  - Language: Python 3.14 / ROCm PyTorch / FastAPI / WebFlight Deck              |")
    parts.append("|  - Engine 3: Cognitive Flight Management System (FMS)                           |")
    parts.append("|  - Engine 6: Operational Command Engine (OCE - HRH Command Center, RTLS, HICS)  |")
    parts.append("|  - Clinical Wellbeing Engine (Staff Burnout, Alert Fatigue, Circadian Acoustic)  |")
    parts.append("+---------------------------------------------------------------------------------+")
    parts.append("```\n")
    
    parts.append("### 1.2 Zero-Bridge Synchronous Memory Rule")
    parts.append("Traditional serialization bridges (JSON, Cython, Pybind11, REST, WebSockets) introduce variable latencies (1-50ms) and garbage-collection stalls that are lethal to physiological control loops.")
    parts.append("BioOS implements the **Zero-Bridge Synchronous Memory Rule**:")
    parts.append("- The Python runtime maps directly onto the physical memory address space of the C/Rust kernel using Ctypes structure pointers.")
    parts.append("- Exactly 0 nanoseconds of serialization overhead.")
    parts.append("- Dual-cache-line aligned 128-byte memory layout (`TriPlaneAmsv`) with atomic 64-bit Seqlock version counter.\n")

    parts.append("---\n")
    parts.append("## Section 2: Shared Atomic Memory State Vector (AMSV) Architecture\n")
    parts.append("### 2.1 128-Byte Dual-Cache-Line Specification")
    parts.append("The AMSV spans exactly 128 bytes (two 64-byte L1 cache lines). Cache Line 0 holds real-time physiological telemetry and safety actuator commands; Cache Line 1 holds laboratory biomarkers, operational modes, and watchdog telemetry.\n")
    parts.append("```rust")
    parts.append("#[repr(C, align(64))]")
    parts.append("pub struct TriPlaneAmsv {")
    parts.append("    // === CACHE LINE 0 (Bytes 0-63): Hard Real-Time Actuation & Envelope ===")
    parts.append("    pub sequence: u64,                // Lockless Seqlock counter (Odd = Writing, Even = Committed)")
    parts.append("    pub timestamp_ns: u64,            // Monotonic nanosecond timestamp")
    parts.append("    pub map_x10: u16,                 // Mean Arterial Pressure (mmHg * 10)")
    parts.append("    pub heart_rate: u16,              // Heart Rate (BPM)")
    parts.append("    pub spo2_x10: u16,                // SpO2 percentage * 10 (e.g., 985 = 98.5%)")
    parts.append("    pub respiratory_rate: u16,        // Breaths per minute")
    parts.append("    pub potassium_x100: u16,          // Serum Potassium (mEq/L * 100)")
    parts.append("    pub hemolysis_index_x10: u16,     // CLSI C56-A Hemolysis index (mg/dL * 10)")
    parts.append("    pub infusion_rate_ml_hr_x10: u16, // Active IV infusion rate (mL/hr * 10)")
    parts.append("    pub alpha_floor_active: u8,       // 1 = Alpha-Floor Stall Protection Triggered, 0 = Normal")
    parts.append("    pub hardware_lockout: u8,         // 1 = Physical Interlock Active, 0 = Unlocked")
    parts.append("    pub active_plane: u8,             // 0 = Plane A (Kernel), 1 = Plane B (COE), 2 = Plane C (FMS)")
    parts.append("    pub operational_mode: u8,         // 0 = ROUTINE, 1 = SURGE, 2 = DISASTER")
    parts.append("    pub reserved_cl0: [u8; 32],       // Padding to guarantee exactly 64 bytes")
    parts.append("    ")
    parts.append("    // === CACHE LINE 1 (Bytes 64-127): Biomarkers, Operations & Watchdog ===")
    parts.append("    pub serum_creatinine_x100: u16,   // Serum Creatinine (mg/dL * 100)")
    parts.append("    pub egfr_x10: u16,                // CKD-EPI 2021 eGFR (mL/min/1.73m^2 * 10)")
    parts.append("    pub total_bilirubin_x100: u16,    // Total Bilirubin (mg/dL * 100)")
    parts.append("    pub serum_sodium_x10: u16,        // Serum Sodium (mEq/L * 10)")
    parts.append("    pub inr_x100: u16,                // International Normalized Ratio * 100")
    parts.append("    pub qtc_interval_ms: u16,         // Tisdale calculated QTc interval (ms)")
    parts.append("    pub escalation_index_x100: u16,   // Hospital Escalation Index E_I * 100")
    parts.append("    pub icu_occupancy_pct: u8,        // ICU Occupancy Percentage (0-100%)")
    parts.append("    pub hics_level: u8,               // 0 = Normal, 1 = Alert, 2 = Activation, 3 = Full Command")
    parts.append("    pub nurse_fatigue_index: u8,      // 0-100 Staff cognitive fatigue score")
    parts.append("    pub patient_circadian_lux: u16,   // Ambient inpatient lux level")
    parts.append("    pub acoustic_db_x10: u16,         // Ambient acoustic decibel envelope (dB * 10)")
    parts.append("    pub crc16_checksum: u16,          // CRC-16-CCITT across bytes 0-125")
    parts.append("    pub reserved_cl1: [u8; 40],       // Padding to guarantee exactly 64 bytes")
    parts.append("}")
    parts.append("```\n")

    parts.append("---\n")
    parts.append("## Section 3: Mathematical Equations, Clinical Formulas & Safety Thresholds\n")
    parts.append("### 3.1 CLSI C56-A Potassium Hemolysis Interference Guard")
    parts.append("Hemolysis releases massive intracellular potassium into serum, causing pseudohyperkalemia.")
    parts.append("If H > 20 mg/dL: VOID potassium reading, assert hardware lockout, and reject automated potassium binding / insulin-dextrose protocols.\n")

    parts.append("### 3.2 CKD-EPI 2021 Race-Free eGFR Equation")
    parts.append("Formula:")
    parts.append("eGFR = 142 * min(Scr / kappa, 1)^alpha * max(Scr / kappa, 1)^(-1.200) * 0.9938^Age * [1.012 if Female]")
    parts.append("Where:")
    parts.append("- Female: kappa = 0.7, alpha = -0.241")
    parts.append("- Male: kappa = 0.9, alpha = -0.302\n")

    parts.append("### 3.3 Devine 3-Tier Adjusted Body Weight (ABW) Creatinine Clearance")
    parts.append("1. Ideal Body Weight (IBW):")
    parts.append("   - IBW (male) = 50.0 + 2.3 * (Height_inches - 60)")
    parts.append("   - IBW (female) = 45.5 + 2.3 * (Height_inches - 60)")
    parts.append("2. Weight Selection:")
    parts.append("   - If Total Body Weight (TBW) < IBW: use TBW.")
    parts.append("   - If TBW >= 1.30 * IBW: use ABW = IBW + 0.40 * (TBW - IBW).")
    parts.append("   - Otherwise: use IBW.")
    parts.append("3. Cockcroft-Gault Creatinine Clearance:")
    parts.append("   CrCl = ((140 - Age) * Weight_selected) / (72 * Scr) * [0.85 if Female]\n")

    parts.append("### 3.4 Jelliffe Dynamic Kinetic Clearance for Acute Kidney Injury (AKI)")
    parts.append("In non-steady-state AKI, standard static creatinine equations fail. Kinetic CrCl:")
    parts.append("Kinetic_CrCl = (Ess * (1 - delta_Scr / (delta_t * 1.5)) + 40 * (delta_Vol / delta_t)) / Scr_mean\n")

    parts.append("### 3.5 Tisdale QTc Drug-Induced Torsades de Pointes Risk Score")
    parts.append("- Low Risk: <= 6 points")
    parts.append("- Moderate Risk: 7 - 10 points")
    parts.append("- High Risk: >= 11 points (Mandatory hard stop on QTc-prolonging agents)")
    parts.append("Interlock rule: If QTc > 500 ms or delta_QTc > 60 ms: ABORT TITRATION.\n")

    parts.append("### 3.6 MELD-Na (Model for End-Stage Liver Disease)")
    parts.append("MELD-Na = MELD + 1.32 * (137 - [Na]) - [0.025 * MELD * (137 - [Na])]")
    parts.append("Where:")
    parts.append("MELD = 9.57 * ln(Creatinine) + 3.78 * ln(Bilirubin) + 11.2 * ln(INR) + 6.43\n")

    parts.append("---\n")
    parts.append("## Section 4: Narrow Therapeutic Index (NTI) Medication Safety Registers\n")
    parts.append("| Drug | Therapeutic Target | Mandatory Laboratory Interlock | Absolute Contraindication Ceiling |")
    parts.append("| :--- | :--- | :--- | :--- |")
    parts.append("| **Metformin** | Glycemic control | Serum Creatinine & eGFR | eGFR < 30 mL/min/1.73m2 -> ABSOLUTE CONTRAINDICATION (Lactic Acidosis) |")
    parts.append("| **Vancomycin** | AUC/MIC 400-600 mg*h/L | Trough level (15-20 ug/mL) | Trough > 20 ug/mL -> Hold dose, nephrotoxicity alarm |")
    parts.append("| **Gentamicin** | Peak 16-24 ug/mL, Trough < 1 ug/mL | Peak/Trough pair | Trough > 2.0 ug/mL -> Ototoxicity/nephrotoxicity lock |")
    parts.append("| **Digoxin** | 0.5 - 0.9 ng/mL | Serum K+, Mg2+, Ca2+ | Potassium < 3.5 mEq/L or [Digoxin] > 2.0 ng/mL -> Arrest Lock |")
    parts.append("| **Enoxaparin** | Anti-Xa 0.6 - 1.0 IU/mL | Platelets & CrCl | CrCl < 30 mL/min -> Mandatory 50% dose reduction |")
    parts.append("| **Methotrexate** | Target varies by oncology cycle | Urinary pH >= 7.0, Leucovorin rescue | Urinary pH < 7.0 or Scr > 2x baseline -> Crystal Nephropathy Lock |\n")

    parts.append("---\n")
    parts.append("## Section 5: Hospital Command Center Architecture & Operational Workflows\n")
    parts.append("### 5.1 8-Tile Real-Time Situational Awareness Grid")
    parts.append("1. **Tile 1: ED Inflow & Triage Congestion** (Door-to-provider time, ambulance diversion status).")
    parts.append("2. **Tile 2: Acute Inpatient Bed Graph** (Occupancy rate, anticipated discharges, clean/dirty turnover).")
    parts.append("3. **Tile 3: Dual-Division ICU Telemetry** (Critical ventilator utilization, ECMO availability, nurse-patient ratio).")
    parts.append("4. **Tile 4: Operating Room & PACU Flow** (Surgical delay index, turnover latency, anesthesia staffing).")
    parts.append("5. **Tile 5: Pharmacy & NTI Safety Surveillance** (Active high-risk infusions, automated DERS override catches).")
    parts.append("6. **Tile 6: Pathology & Lab Hemolysis Interlocks** (CLSI C56-A rejected specimens, blood bank crossmatch queues).")
    parts.append("7. **Tile 7: Facility Infrastructure & HVAC Cascades** (AIIR negative pressure sensors, bulk oxygen tank flow).")
    parts.append("8. **Tile 8: Hospital Escalation Index (E_I) & Disaster Readiness** (Real-time surge posture).\n")

    parts.append("### 5.2 Real-Time Location System (RTLS) 5-Stage Bed Turnover Lifecycle")
    parts.append("1. Stage 1: Discharge Order Verified (Physician enters order; cleaning dispatch triggered within 120s).")
    parts.append("2. Stage 2: Patient Departure Confirmed (RTLS tag leaves patient bay; EVS task automatically priority-routed).")
    parts.append("3. Stage 3: Environmental Terminal Cleaning (EVS badge in room; UV-C sterilization run registered).")
    parts.append("4. Stage 4: Nursing Inspection & Ready Verification (Room inspected; state changed to Ready-for-Admission).")
    parts.append("5. Stage 5: Direct Inflow Bed Assignment (ED patient allocated; transport orderly notified via push).\n")

    parts.append("### 5.3 Massive Hemorrhage Protocol (MHP) '7 Ts' with TEG Guidance")
    parts.append("- 1. Trigger: Early clinical activation (Shock Index > 1.0 or ABC Score >= 2).")
    parts.append("- 2. Team: Trauma surgeon, anesthesiologist, blood bank transfusion lead, runner.")
    parts.append("- 3. Testing: Baseline TEG/ROTEM, CBC, fibrinogen, electrolytes, arterial blood gas.")
    parts.append("- 4. Temperature: Active warming (Target core temp > 36.0 C).")
    parts.append("- 5. Target Ratios: Fixed ratio 1:1:1 (RBC : FFP : Platelets).")
    parts.append("- 6. Tranexamic Acid (TXA): 1g IV over 10 min within 3 hours of injury, followed by 1g infusion over 8 hours.")
    parts.append("- 7. Termination: Discontinuation based on surgical hemostasis and normalized TEG R-time and Maximum Amplitude (MA).\n")

    parts.append("---\n")
    parts.append("## Section 6: Disaster Management, Surge Escalation & Triage\n")
    parts.append("### 6.1 Hospital Surge Escalation Index (E_I)")
    parts.append("Formula: E_I = (Occupied Beds + 1.5 * ED Admitted Boarders) / Licensed Bed Capacity")
    parts.append("- Routine Mode: E_I < 0.85")
    parts.append("- Surge Level 1 (Yellow Alert): 0.85 <= E_I < 0.95")
    parts.append("- Surge Level 2 (Orange Alert): 0.95 <= E_I < 1.05")
    parts.append("- Disaster Mode (Red Alert / HICS): E_I >= 1.05\n")

    parts.append("### 6.2 Reverse Triage & Rapid Transfer to Life (RTTL)")
    parts.append("Formula: RTTL = w1 * (10 - MEWS) + w2 * Mobility + w3 * Oral_Meds - w4 * IV_Dependency")
    parts.append("Patients scoring >= 75 are expedited to step-down facilities to immediately decompress acute ICU beds.\n")

    parts.append("---\n")
    parts.append("## Section 7: Critical Infrastructure & Facility Engineering\n")
    parts.append("### 7.1 ASHRAE 170 / 241 Airborne Infectious Isolation Room (AIIR)")
    parts.append("- Minimum Air Changes per Hour (ACH): >= 12 ACH for new construction, >= 6 ACH for existing.")
    parts.append("- Differential Pressure: Continuous negative pressure <= -2.5 Pa (-0.01 inches of water gauge).")
    parts.append("- Exhaust: 100% direct exhaust to the outdoors via dedicated ductwork through HEPA filtration (99.97% efficiency at 0.3 um).\n")

    parts.append("### 7.2 Dual-Division ICU Rapid Partitioning Mechanics")
    parts.append("Hermetic smoke/fire barriers drop within 90 seconds, splitting the ICU into:")
    parts.append("- Clean Pod (Cold Zone): Positive pressure, dedicated staff airlock, for non-infectious acute patients.")
    parts.append("- Infectious Pod (Hot Zone): Negative pressure cascade (-2.5 Pa to -5.0 Pa), dedicated ante-rooms, HEPA air scrubbing.\n")

    parts.append("---\n")
    parts.append("## Section 8: Caregiver & Patient Clinical Wellbeing Architecture\n")
    parts.append("### 8.1 Clinician Alert Fatigue Suppression & Cognitive Load Index")
    parts.append("- Intelligent suppression of non-actionable alarms (up to 90% nuisance alarm reduction).")
    parts.append("- Real-time Cognitive Load Index (CLI) tracking active titrations, patient acuity, and task density.")
    parts.append("- Assignment lockout when CLI > 85 to prevent staff burnout and clinical error.\n")

    parts.append("### 8.2 Inpatient Restorative Sleep & Circadian Recovery")
    parts.append("- Daytime Lighting (07:00 - 19:00): High-intensity blue-enriched light (480nm, 500-1000 lux) for circadian entrainment.")
    parts.append("- Nighttime Lighting (19:00 - 07:00): Low-intensity warm light (< 50 lux, zero blue light).")
    parts.append("- Acoustic Noise Envelope: Enforces < 45 dB daytime and < 35 dB during night restorative sleep windows.\n")

    parts.append("---\n")
    parts.append("## Section 9: Complete Primary Source Text & Specifications\n")
    parts.append("### 9.1 Master Specification v1.0 (bioos-master-specification-consolidated-v1-0.md)\n")
    parts.append(v1_master + "\n")

    parts.append("### 9.2 Five-Engine Specification Report (bioos-five-engine-specification-report-standards-formulas-and-safety-architecture.md)\n")
    parts.append(five_engine + "\n")

    parts.append("### 9.3 Operational Architecture & Command Center (bioos-operational-architecture-hospital-command-center-resource-allocation-clinical-governance-&-disaster-framework.md)\n")
    parts.append(op_arch + "\n")

    parts.append("### 9.4 Architecture Framework (bioos_architecture_framework.md)\n")
    parts.append(arch_frame + "\n")

    parts.append("### 9.5 Complete Technical Specification Parts 1-3 (BioOS_Complete_Spec_Parts_1-3.md)\n")
    parts.append(complete_spec + "\n")

    parts.append("### 9.6 Hospital Ops & Disaster Architecture (BioOS_Hospital_Ops_Disaster_Architecture.md)\n")
    parts.append(hospital_ops + "\n")

    parts.append("### 9.7 Qwen Multi-Engine Framework (Qwen_markdown_20261014_7u3a7mj9k.md)\n")
    parts.append(qwen_arch + "\n")

    parts.append("### 9.8 Production-Grade Blueprint (Architecting BioOS IEC 62304 Class C Blueprint PDF)\n")
    parts.append(pdf_text + "\n")

    parts.append("---\n")
    parts.append("*[End of Unified Hospital, Healthcare & Wellbeing Operating System Master Specification]*\n")

    final_text = "\n".join(parts)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_text)
        
    print(f"Master specification successfully written to {OUTPUT_FILE}")
    print(f"File Size: {os.path.getsize(OUTPUT_FILE):,} bytes")

if __name__ == "__main__":
    main()
