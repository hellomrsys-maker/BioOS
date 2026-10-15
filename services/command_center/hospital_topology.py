# -*- coding: utf-8 -*-
"""
BioOS Enterprise Hospital Topology & Real-Time Patient Census
Standards: HL7 FHIR R4, Canadian Triage and Acuity Scale (CTAS) / Emergency Severity Index (ESI)
Humber River Hospital (HRH) & Johns Hopkins Capacity Command Center architectural patterns.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time
import math

@dataclass
class PatientRecord:
    patient_id: str
    mrn: str
    name: str
    age: int
    sex: str  # "M" or "F"
    diagnosis: str
    esi_triage_score: int  # 1 (Resuscitation) to 5 (Non-urgent)
    ward_id: str
    bed_id: str
    attending_md: str
    primary_rn: str
    admission_timestamp: float
    
    # Live Hemodynamics & Vitals
    heart_rate: int = 75
    systolic_bp: int = 120
    diastolic_bp: int = 80
    mean_arterial_pressure: int = 93
    spo2_percent: float = 98.5
    respiratory_rate: int = 16
    temperature_c: float = 37.0
    gcs_score: int = 15
    
    # Laboratory Biomarkers
    serum_creatinine: float = 1.0
    egfr: float = 85.0
    potassium_meq_l: float = 4.2
    hemolysis_index: int = 8  # CLSI C56-A
    bilirubin_mg_dl: float = 0.8
    inr: float = 1.05
    platelet_count_k: int = 240
    
    # High-Risk Active Infusions
    active_infusions: List[Dict] = field(default_factory=list)
    
    # Clinical Discharge Barriers & Milestones
    discharge_ready: bool = False
    pending_barriers: List[str] = field(default_factory=list)
    requires_isolation: bool = False
    isolation_type: Optional[str] = None  # "AIIR_AIRBORNE", "CONTACT", "DROPLET", None
    requires_telemetry: bool = True

@dataclass
class HospitalBed:
    bed_id: str
    ward_id: str
    bed_number: str
    bed_type: str  # "ICU", "PCU", "MED_SURG", "ED_BAY", "OR_SUITE", "PACU_BAY", "LOUNGE_CHAIR"
    is_occupied: bool = False
    patient_id: Optional[str] = None
    status: str = "AVAILABLE"  # "AVAILABLE", "OCCUPIED", "DIRTY", "CLEANING", "UV_INSPECTED", "MAINTENANCE"
    is_negative_pressure: bool = False
    hvac_pressure_pa: float = 0.0
    telemetry_connected: bool = True
    last_cleaned_timestamp: float = field(default_factory=time.time)

@dataclass
class HospitalWard:
    ward_id: str
    name: str
    ward_type: str  # "EMERGENCY", "ICU", "STEP_DOWN", "MED_SURG", "PERIOPERATIVE", "DISCHARGE"
    floor: int
    licensed_capacity: int
    mandated_nurse_ratio: float  # Nurses per patient (e.g. 0.5 for 1:2, 1.0 for 1:1, 0.25 for 1:4)
    staffed_nurses_on_duty: int
    beds: Dict[str, HospitalBed] = field(default_factory=dict)

class HospitalTopologyManager:
    def __init__(self):
        self.wards: Dict[str, HospitalWard] = {}
        self.patients: Dict[str, PatientRecord] = {}
        self._initialize_hospital_facility()
        self._seed_initial_census()

    def _initialize_hospital_facility(self):
        """Initializes authentic multi-ward hospital topology (50+ active beds)."""
        # 1. Emergency Department (16 Bays)
        ed = HospitalWard("ED_MAIN", "Emergency Department", "EMERGENCY", floor=1, licensed_capacity=16, mandated_nurse_ratio=0.33, staffed_nurses_on_duty=5)
        for i in range(1, 17):
            b_type = "ED_BAY"
            b_num = f"ED-{i:02d}"
            is_neg = (i in [15, 16])  # Two negative pressure bays
            p_pa = -2.7 if is_neg else 0.0
            ed.beds[b_num] = HospitalBed(b_num, "ED_MAIN", b_num, b_type, is_negative_pressure=is_neg, hvac_pressure_pa=p_pa)
        self.wards["ED_MAIN"] = ed

        # 2. Intensive Care Unit Pod A - Medical/Surgical Critical Care (8 Beds)
        icu_a = HospitalWard("ICU_POD_A", "Medical Intensive Care (Pod A)", "ICU", floor=2, licensed_capacity=8, mandated_nurse_ratio=0.5, staffed_nurses_on_duty=4)
        for i in range(1, 9):
            b_num = f"ICU-A-{i:02d}"
            icu_a.beds[b_num] = HospitalBed(b_num, "ICU_POD_A", b_num, "ICU", is_negative_pressure=False, hvac_pressure_pa=0.0)
        self.wards["ICU_POD_A"] = icu_a

        # 3. Intensive Care Unit Pod B - Airborne Infectious Isolation (8 Beds, AIIR Negative Pressure)
        icu_b = HospitalWard("ICU_POD_B", "Isolation Intensive Care (Pod B - AIIR)", "ICU", floor=2, licensed_capacity=8, mandated_nurse_ratio=0.5, staffed_nurses_on_duty=4)
        for i in range(1, 9):
            b_num = f"ICU-B-{i:02d}"
            icu_b.beds[b_num] = HospitalBed(b_num, "ICU_POD_B", b_num, "ICU", is_negative_pressure=True, hvac_pressure_pa=-2.8)
        self.wards["ICU_POD_B"] = icu_b

        # 4. Progressive Care Unit / Step-Down (12 Beds)
        pcu = HospitalWard("PCU_STEPDOWN", "Progressive Care Telemetry (PCU)", "STEP_DOWN", floor=3, licensed_capacity=12, mandated_nurse_ratio=0.25, staffed_nurses_on_duty=3)
        for i in range(1, 13):
            b_num = f"PCU-{i:02d}"
            pcu.beds[b_num] = HospitalBed(b_num, "PCU_STEPDOWN", b_num, "PCU", is_negative_pressure=False, hvac_pressure_pa=0.0)
        self.wards["PCU_STEPDOWN"] = pcu

        # 5. Inpatient Medical-Surgical North (20 Beds)
        medsurg = HospitalWard("MEDSURG_NORTH", "Inpatient Med-Surg Acute (North)", "MED_SURG", floor=4, licensed_capacity=20, mandated_nurse_ratio=0.20, staffed_nurses_on_duty=4)
        for i in range(1, 21):
            b_num = f"MS-{i:02d}"
            medsurg.beds[b_num] = HospitalBed(b_num, "MEDSURG_NORTH", b_num, "MED_SURG", is_negative_pressure=False, hvac_pressure_pa=0.0)
        self.wards["MEDSURG_NORTH"] = medsurg

        # 6. Perioperative Suite & PACU (6 Theaters + 8 Recovery Bays)
        periop = HospitalWard("PERIOP_SUITE", "Surgical Theaters & PACU Recovery", "PERIOPERATIVE", floor=1, licensed_capacity=14, mandated_nurse_ratio=0.5, staffed_nurses_on_duty=7)
        for i in range(1, 7):
            b_num = f"OR-{i:02d}"
            periop.beds[b_num] = HospitalBed(b_num, "PERIOP_SUITE", b_num, "OR_SUITE", is_negative_pressure=False, hvac_pressure_pa=2.5)  # Positive pressure
        for i in range(1, 9):
            b_num = f"PACU-{i:02d}"
            periop.beds[b_num] = HospitalBed(b_num, "PERIOP_SUITE", b_num, "PACU_BAY", is_negative_pressure=False, hvac_pressure_pa=0.0)
        self.wards["PERIOP_SUITE"] = periop

    def _seed_initial_census(self):
        """Populates realistic hospital patients with diverse acuities and diagnoses."""
        initial_patients = [
            # Critical ICU Patients (Shock, Sepsis, ARDS)
            PatientRecord(
                "PT-88219", "MRN-10029", "Eleanor Vance", 68, "F", "Septic Shock / Pneumonia", 1,
                "ICU_POD_A", "ICU-A-01", "Dr. David Thorne, MD", "Elena Rostova, CCRN", time.time() - 36000,
                heart_rate=118, systolic_bp=78, diastolic_bp=48, mean_arterial_pressure=58, spo2_percent=92.1,
                respiratory_rate=26, serum_creatinine=2.4, egfr=24.5, potassium_meq_l=4.6, hemolysis_index=8,
                active_infusions=[
                    {"drug": "Norepinephrine", "rate_mcg_min": 14.0, "target": "MAP >= 65"},
                    {"drug": "Vasopressin", "rate_units_min": 0.03, "target": "SVR"}
                ],
                requires_telemetry=True, requires_isolation=False
            ),
            PatientRecord(
                "PT-94102", "MRN-10044", "Arthur Pendelton", 72, "M", "Severe ARDS / Viral Pneumonitis", 1,
                "ICU_POD_B", "ICU-B-01", "Dr. David Thorne, MD", "Marcus Miller, RN", time.time() - 54000,
                heart_rate=98, systolic_bp=104, diastolic_bp=62, mean_arterial_pressure=76, spo2_percent=89.4,
                respiratory_rate=24, serum_creatinine=1.6, egfr=44.0, potassium_meq_l=5.1, hemolysis_index=12,
                active_infusions=[
                    {"drug": "Propofol", "rate_mcg_kg_min": 35.0, "target": "RASS -4"},
                    {"drug": "Fentanyl", "rate_mcg_hr": 100.0, "target": "CPOT <= 2"}
                ],
                requires_telemetry=True, requires_isolation=True, isolation_type="AIIR_AIRBORNE"
            ),
            PatientRecord(
                "PT-77341", "MRN-10118", "Rajesh Patel", 59, "M", "NSTEMI / Cardiogenic Shock Post-PCI", 2,
                "ICU_POD_A", "ICU-A-02", "Dr. Sarah Jenkins, MD", "Sarah Chen, BSN", time.time() - 24000,
                heart_rate=88, systolic_bp=96, diastolic_bp=58, mean_arterial_pressure=70, spo2_percent=97.0,
                respiratory_rate=18, serum_creatinine=1.2, egfr=68.0, potassium_meq_l=4.1, hemolysis_index=6,
                active_infusions=[
                    {"drug": "Heparin", "rate_units_hr": 1150.0, "target": "aPTT 60-80"}
                ]
            ),
            # Step-Down (PCU) Patients
            PatientRecord(
                "PT-60293", "MRN-10201", "Maria Santos", 64, "F", "Diabetic Ketoacidosis (Resolving)", 2,
                "PCU_STEPDOWN", "PCU-01", "Dr. Sarah Jenkins, MD", "Chloe Bennett, RN", time.time() - 48000,
                heart_rate=82, systolic_bp=118, diastolic_bp=74, mean_arterial_pressure=88, spo2_percent=98.0,
                respiratory_rate=16, serum_creatinine=1.1, egfr=62.0, potassium_meq_l=4.3, hemolysis_index=9,
                active_infusions=[
                    {"drug": "Regular Insulin", "rate_units_hr": 2.5, "target": "BG 140-180"}
                ],
                pending_barriers=["Subcutaneous Insulin Transition", "Endocrinology Clearance"]
            ),
            PatientRecord(
                "PT-55104", "MRN-10255", "Robert Kowalski", 76, "M", "Acute Decompensated Heart Failure", 3,
                "PCU_STEPDOWN", "PCU-02", "Dr. Michael Chang, MD", "Chloe Bennett, RN", time.time() - 72000,
                heart_rate=74, systolic_bp=128, diastolic_bp=78, mean_arterial_pressure=94, spo2_percent=96.0,
                respiratory_rate=16, serum_creatinine=1.8, egfr=38.0, potassium_meq_l=4.5, hemolysis_index=5,
                discharge_ready=True, pending_barriers=["Pending SNF Bed Placement"]
            ),
            # Emergency Department Patients
            PatientRecord(
                "PT-11092", "MRN-10389", "James Wilson", 45, "M", "Acute Appendicitis (Pre-Op)", 3,
                "ED_MAIN", "ED-01", "Dr. Robert Vance, MD", "Kevin Nguyen, RN", time.time() - 7200,
                heart_rate=92, systolic_bp=132, diastolic_bp=84, mean_arterial_pressure=100, spo2_percent=99.0,
                respiratory_rate=18, serum_creatinine=0.9, egfr=98.0, potassium_meq_l=4.0, hemolysis_index=4,
                pending_barriers=["Awaiting OR Theater 2 Availability"]
            ),
            PatientRecord(
                "PT-11095", "MRN-10412", "Hannah Davis", 31, "F", "Asthma Exacerbation", 3,
                "ED_MAIN", "ED-02", "Dr. Robert Vance, MD", "Kevin Nguyen, RN", time.time() - 3600,
                heart_rate=102, systolic_bp=124, diastolic_bp=80, mean_arterial_pressure=94, spo2_percent=94.5,
                respiratory_rate=22, serum_creatinine=0.7, egfr=115.0, potassium_meq_l=3.9, hemolysis_index=3
            ),
            # Med-Surg Patients
            PatientRecord(
                "PT-44019", "MRN-10178", "Dorothy Miller", 82, "F", "Total Hip Arthroplasty (Post-Op Day 2)", 4,
                "MEDSURG_NORTH", "MS-01", "Dr. Michael Chang, MD", "Samuel Taylor, RN", time.time() - 172800,
                heart_rate=70, systolic_bp=116, diastolic_bp=72, mean_arterial_pressure=86, spo2_percent=98.0,
                respiratory_rate=14, serum_creatinine=1.0, egfr=58.0, potassium_meq_l=4.2, hemolysis_index=4,
                discharge_ready=False, pending_barriers=["PT Gait Training (>50ft required)", "Oral Pain Control Conversion"]
            )
        ]

        for p in initial_patients:
            self.patients[p.patient_id] = p
            # Mark bed as occupied
            ward = self.wards.get(p.ward_id)
            if ward and p.bed_id in ward.beds:
                bed = ward.beds[p.bed_id]
                bed.is_occupied = True
                bed.patient_id = p.patient_id
                bed.status = "OCCUPIED"

    def get_hospital_summary(self) -> Dict:
        """Computes comprehensive executive metrics across all hospital units."""
        total_beds = sum(len(w.beds) for w in self.wards.values())
        occupied_beds = sum(sum(1 for b in w.beds.values() if b.is_occupied) for w in self.wards.values())
        dirty_cleaning_beds = sum(sum(1 for b in w.beds.values() if b.status in ["DIRTY", "CLEANING"]) for w in self.wards.values())
        available_beds = sum(sum(1 for b in w.beds.values() if b.status == "AVAILABLE") for w in self.wards.values())
        
        ed_census = sum(1 for p in self.patients.values() if p.ward_id == "ED_MAIN")
        icu_census = sum(1 for p in self.patients.values() if "ICU" in p.ward_id)
        
        # Calculate Hospital Escalation Index (E_I)
        # E_I = (Occupied + 1.5 * ED Boarders) / Total Capacity
        ed_boarders = sum(1 for p in self.patients.values() if p.ward_id == "ED_MAIN" and len(p.pending_barriers) > 0)
        ei = (occupied_beds + 1.5 * ed_boarders) / max(1, total_beds)
        ei_clamped = min(1.5, round(ei, 3))
        
        # Determine regime
        if ei_clamped < 0.85:
            regime = "ROUTINE"
            tier = 0
        elif ei_clamped < 0.95:
            regime = "SURGE_TIER_1"
            tier = 1
        elif ei_clamped < 1.05:
            regime = "SURGE_TIER_2"
            tier = 2
        else:
            regime = "DISASTER_HICS"
            tier = 3

        return {
            "total_licensed_beds": total_beds,
            "occupied_beds": occupied_beds,
            "occupancy_rate_percent": round((occupied_beds / max(1, total_beds)) * 100, 1),
            "dirty_turnover_beds": dirty_cleaning_beds,
            "available_ready_beds": available_beds,
            "ed_census": ed_census,
            "icu_census": icu_census,
            "ed_boarders_count": ed_boarders,
            "escalation_index": ei_clamped,
            "operating_regime": regime,
            "surge_tier": tier,
            "active_patients_count": len(self.patients)
        }

    def get_ward_cards(self) -> List[Dict]:
        """Returns structured data for the master bed board view."""
        ward_list = []
        for w in self.wards.values():
            occupied = sum(1 for b in w.beds.values() if b.is_occupied)
            beds_data = []
            for b in w.beds.values():
                p_data = None
                if b.patient_id and b.patient_id in self.patients:
                    p = self.patients[b.patient_id]
                    p_data = {
                        "patient_id": p.patient_id,
                        "mrn": p.mrn,
                        "name": p.name,
                        "age": p.age,
                        "sex": p.sex,
                        "diagnosis": p.diagnosis,
                        "esi": p.esi_triage_score,
                        "vitals": {
                            "hr": p.heart_rate,
                            "map": p.mean_arterial_pressure,
                            "spo2": p.spo2_percent,
                            "rr": p.respiratory_rate
                        },
                        "infusions_count": len(p.active_infusions),
                        "isolation": p.isolation_type,
                        "discharge_ready": p.discharge_ready
                    }
                beds_data.append({
                    "bed_id": b.bed_id,
                    "bed_number": b.bed_number,
                    "status": b.status,
                    "is_occupied": b.is_occupied,
                    "is_negative_pressure": b.is_negative_pressure,
                    "hvac_pa": b.hvac_pressure_pa,
                    "patient": p_data
                })
            
            ward_list.append({
                "ward_id": w.ward_id,
                "name": w.name,
                "ward_type": w.ward_type,
                "floor": w.floor,
                "capacity": len(w.beds),
                "occupied": occupied,
                "occupancy_pct": round((occupied / len(w.beds)) * 100, 1),
                "staffed_nurses": w.staffed_nurses_on_duty,
                "required_nurses": math.ceil(occupied * w.mandated_nurse_ratio),
                "in_staffing_ratio": (w.staffed_nurses_on_duty >= math.ceil(occupied * w.mandated_nurse_ratio)),
                "beds": beds_data
            })
        return ward_list

    def admit_patient(self, patient: PatientRecord, target_ward_id: str, target_bed_id: Optional[str] = None) -> Tuple[bool, str]:
        """Admits or allocates a patient into an available bed."""
        ward = self.wards.get(target_ward_id)
        if not ward:
            return False, f"Ward {target_ward_id} does not exist."

        # Find bed
        bed = None
        if target_bed_id:
            bed = ward.beds.get(target_bed_id)
            if not bed or bed.is_occupied or bed.status != "AVAILABLE":
                return False, f"Requested bed {target_bed_id} is unavailable (Status: {bed.status if bed else 'None'})."
        else:
            # Auto-match bed
            for b in ward.beds.values():
                if not b.is_occupied and b.status == "AVAILABLE":
                    if patient.requires_isolation and not b.is_negative_pressure:
                        continue
                    bed = b
                    break

        if not bed:
            return False, f"No compliant available bed found in {ward.name}."

        patient.ward_id = ward.ward_id
        patient.bed_id = bed.bed_id
        bed.is_occupied = True
        bed.patient_id = patient.patient_id
        bed.status = "OCCUPIED"
        self.patients[patient.patient_id] = patient
        return True, f"Patient {patient.name} admitted to {bed.bed_id}."

    def transfer_patient(self, patient_id: str, dest_ward_id: str) -> Tuple[bool, str]:
        """Transfers patient from one ward to another and triggers RTLS turnover on old bed."""
        patient = self.patients.get(patient_id)
        if not patient:
            return False, f"Patient {patient_id} not found."

        old_ward = self.wards.get(patient.ward_id)
        dest_ward = self.wards.get(dest_ward_id)
        if not dest_ward:
            return False, f"Destination ward {dest_ward_id} not found."

        # Find available bed in destination
        dest_bed = None
        for b in dest_ward.beds.values():
            if not b.is_occupied and b.status == "AVAILABLE":
                dest_bed = b
                break

        if not dest_bed:
            return False, f"No available beds in {dest_ward.name} to accommodate transfer."

        # Release old bed -> Sets state to DIRTY for RTLS cleaning
        if old_ward and patient.bed_id in old_ward.beds:
            old_b = old_ward.beds[patient.bed_id]
            old_b.is_occupied = False
            old_b.patient_id = None
            old_b.status = "DIRTY"

        # Assign new bed
        patient.ward_id = dest_ward.ward_id
        patient.bed_id = dest_bed.bed_id
        dest_bed.is_occupied = True
        dest_bed.patient_id = patient.patient_id
        dest_bed.status = "OCCUPIED"

        return True, f"Patient {patient.name} successfully transferred from {old_ward.name if old_ward else 'Prior'} to {dest_bed.bed_id} in {dest_ward.name}. Old bed marked DIRTY for EVS turnover."

    def discharge_patient(self, patient_id: str) -> Tuple[bool, str]:
        """Processes patient discharge and triggers RTLS 5-stage cleaning lifecycle."""
        patient = self.patients.get(patient_id)
        if not patient:
            return False, f"Patient {patient_id} not found."

        ward = self.wards.get(patient.ward_id)
        if ward and patient.bed_id in ward.beds:
            bed = ward.beds[patient.bed_id]
            bed.is_occupied = False
            bed.patient_id = None
            bed.status = "DIRTY"  # EVS cleaning dispatched

        del self.patients[patient_id]
        return True, f"Patient {patient.name} discharged. Bed {patient.bed_id} flagged DIRTY. Environmental Services (EVS) cleaning task priority dispatched."

    def get_pharmacy_surveillance(self) -> Dict:
        """Hospital-wide surveillance of active high-risk infusions and Drug-Drug Interactions (DDI)."""
        active_infusions_list = []
        ddi_alerts = []

        for p in self.patients.values():
            for inf in p.active_infusions:
                active_infusions_list.append({
                    "patient_id": p.patient_id,
                    "patient_name": p.name,
                    "ward": p.ward_id,
                    "bed": p.bed_id,
                    "drug": inf.get("drug"),
                    "rate": inf.get("rate_mcg_min") or inf.get("rate_units_hr") or inf.get("rate_mcg_hr") or inf.get("rate_mcg_kg_min"),
                    "target": inf.get("target")
                })

            # Check DDI: E.g., Sepsis Norepinephrine + Vasopressin combined titration
            drugs = [inf.get("drug") for inf in p.active_infusions]
            if "Norepinephrine" in drugs and "Vasopressin" in drugs:
                ddi_alerts.append({
                    "severity": "MODERATE_CO_TITRATION",
                    "patient_id": p.patient_id,
                    "patient_name": p.name,
                    "message": "Dual vasopressor titration active (Norepinephrine + Vasopressin). SVR and peripheral ischemia monitoring required."
                })
            if p.egfr < 30.0 and any("Metformin" in d for d in drugs):
                ddi_alerts.append({
                    "severity": "CRITICAL_CONTRAINDICATION",
                    "patient_id": p.patient_id,
                    "patient_name": p.name,
                    "message": f"Metformin active with eGFR {p.egfr} < 30 mL/min! High risk of fatal lactic acidosis. Immediate hold required."
                })

        return {
            "total_active_infusions": len(active_infusions_list),
            "infusions": active_infusions_list,
            "active_ddi_alerts": ddi_alerts
        }

if __name__ == "__main__":
    mgr = HospitalTopologyManager()
    summary = mgr.get_hospital_summary()
    print("Hospital Topology Summary:")
    print("Total Beds:", summary["total_licensed_beds"])
    print("Occupied Beds:", summary["occupied_beds"])
    print("Occupancy Rate:", summary["occupancy_rate_percent"], "%")
    print("Escalation Index:", summary["escalation_index"])
    print("Operating Regime:", summary["operating_regime"])
