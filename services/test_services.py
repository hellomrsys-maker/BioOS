"""
Comprehensive Service Test Suite for BioOS Plane B & Enterprise Layers
Tests:
- Engine 5 (COE): AMD ROCm inference, XGrammar JSON constrained generation, Merkle tree root hashing
- Engine 6 (OCE): Hospital Escalation Index, RTLS bed transitions, MHP 7 Ts, Standing Orders, HVAC, HICS Reverse Triage
"""

import sys
import os

# Add paths to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "cognitive_plane")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "command_center")))

from engine5_coe import ClinicalOversightEngine, RFC9162MerkleTree
from engine6_oce import (
    OperationalCommandEngine, HospitalTelemetry, OperationalRegime, BedStatus
)

def test_engine5_coe():
    print("[TEST] Running Engine 5 (COE) tests...")
    coe = ClinicalOversightEngine()
    
    # Valid lookup ref
    fhir_order, safe = coe.generate_constrained_clinical_recommendation(
        patient_id="PT-9941",
        biomarker_summary={"cr": 1.1, "egfr": 72.0},
        proposed_action_type="MedicationRequest",
        lookup_ref_enum="NTI_VANCOMYCIN_STANDARD_AUC"
    )
    assert safe is True
    assert fhir_order["resourceType"] == "MedicationRequest"
    assert fhir_order["dosageInstruction"][0]["doseAndRate"][0]["doseQuantity"]["value"] == 1500.0
    
    # Invalid hallucinated token rejection
    fhir_bad, bad_safe = coe.generate_constrained_clinical_recommendation(
        patient_id="PT-9941",
        biomarker_summary={"cr": 1.1},
        proposed_action_type="MedicationRequest",
        lookup_ref_enum="HALLUCINATED_RANDOM_DRUG"
    )
    assert bad_safe is False
    assert fhir_bad["status"] == "rejected_by_guard"

    # Merkle tree root hash
    root = coe.merkle_tree.get_root_hash()
    assert len(root) == 64
    print(f" -> Engine 5 PASS! Merkle Tree Root Hash: {root[:16]}...")

def test_engine6_oce():
    print("[TEST] Running Engine 6 (OCE) tests...")
    oce = OperationalCommandEngine()

    # 1. Routine Escalation Index
    telem_routine = HospitalTelemetry(
        ed_census=30, ed_waiting=5, ed_treatment_bays=40,
        icu_occupied_beds=18, icu_licensed_beds=25,
        nurses_on_duty=45, mandated_nurse_floor=45,
        active_emergency_or_cases=3, staffed_operating_rooms=10,
        critical_supply_inventory_ratio=0.95
    )
    rep_routine = oce.calculate_escalation_index(telem_routine)
    print(f" -> Routine E_I: {rep_routine.escalation_index} (Regime: {rep_routine.regime.value})")
    assert rep_routine.regime in [OperationalRegime.ROUTINE, OperationalRegime.SURGE]

    # 2. Disaster Surge Escalation Index
    telem_disaster = HospitalTelemetry(
        ed_census=95, ed_waiting=60, ed_treatment_bays=40,
        icu_occupied_beds=25, icu_licensed_beds=25,
        nurses_on_duty=20, mandated_nurse_floor=45,
        active_emergency_or_cases=12, staffed_operating_rooms=10,
        critical_supply_inventory_ratio=0.20
    )
    rep_disaster = oce.calculate_escalation_index(telem_disaster)
    print(f" -> Disaster E_I: {rep_disaster.escalation_index} (Regime: {rep_disaster.regime.value})")
    assert rep_disaster.regime == OperationalRegime.DISASTER

    # 3. RTLS Bed Transitions
    bed = BedStatus.OCCUPIED
    bed = oce.transition_bed_state(bed, "PATIENT_DISCHARGED")
    assert bed == BedStatus.DIRTY
    bed = oce.transition_bed_state(bed, "EVS_BADGE_DETECTED")
    assert bed == BedStatus.CLEANING
    bed = oce.transition_bed_state(bed, "UV_CYCLE_COMPLETE")
    assert bed == BedStatus.INSPECTED
    bed = oce.transition_bed_state(bed, "SUPERVISOR_QR_VERIFIED")
    assert bed == BedStatus.AVAILABLE
    print(" -> RTLS Bed Lifecycle Transitions: PASS")

    # 4. MHP 7 Ts Trigger
    mhp = oce.evaluate_mhp_activation(
        heart_rate=135,
        systolic_bp=80,
        penetrating_trauma=True,
        fast_ultrasound_positive=True,
        base_deficit=-8.5,
        teg_r_time_mins=12.5,
        teg_max_amplitude_mm=42.0,
        teg_ly30_percent=5.2
    )
    assert mhp["mhp_triggered"] is True
    assert len(mhp["teg_guidance"]) == 3
    print(" -> Massive Hemorrhage Protocol (MHP): PASS")

    # 5. Standing Orders (Sepsis & Hypoglycemia)
    orders = oce.evaluate_standing_orders(
        temperature_c=39.2,
        heart_rate=115,
        respiratory_rate=24,
        wbc_count=16.5,
        serum_lactate_mmol_l=3.4,
        blood_glucose_mg_dl=54.0,
        chest_pain=False
    )
    assert len(orders) >= 2
    protocols = [o["protocol"] for o in orders]
    assert "SEPSIS_1_HOUR_BUNDLE" in protocols
    assert "HYPOGLYCEMIA_RESCUE" in protocols
    print(f" -> Standing Orders Triggered: {protocols}")

    # 6. HVAC Cascade
    hvac_aiir = oce.evaluate_hvac_pressure("AIIR_NEGATIVE_PRESSURE", -2.6, 14.0)
    assert hvac_aiir["compliant"] is True
    assert hvac_aiir["containment_alarm"] is False

    hvac_leak = oce.evaluate_hvac_pressure("AIIR_NEGATIVE_PRESSURE", -0.2, 8.0)
    assert hvac_leak["containment_alarm"] is True
    print(" -> HVAC Containment Pressure Checks: PASS")

    # 7. Reverse Triage Early Discharge
    triage = oce.evaluate_reverse_triage_candidate(
        patient_id="SURGE-PT-12",
        predicted_48h_mortality_percent=2.1,
        requires_icu_vasopressors=False,
        requires_mechanical_ventilation=False,
        home_oxygen_capable=True
    )
    assert triage["reverse_triage_eligible"] is True
    print(f" -> Reverse Triage: {triage['disposition']}")

def test_wellbeing_engine():
    print("[TEST] Running Clinical & Patient Wellbeing Engine tests...")
    from wellbeing_engine import HospitalWellbeingEngine, ClinicianProfile, PatientRoomWellbeing
    wellbeing = HospitalWellbeingEngine()

    # 1. Clinician Cognitive Load & Burnout Lock
    rn_low = ClinicianProfile("TEST-RN-1", "Test Nurse Low", "ICU_RN", shift_hours_elapsed=4.0, active_patients_count=1, alarms_experienced_last_hour=5)
    cli_low = wellbeing.compute_cognitive_load(rn_low)
    assert cli_low < 50.0
    assert rn_low.assignment_locked is False

    rn_high = ClinicianProfile("TEST-RN-2", "Test Nurse High", "ICU_RN", shift_hours_elapsed=12.5, active_patients_count=3, high_acuity_patients_count=3, alarms_experienced_last_hour=60, consecutive_shift_days=5)
    cli_high = wellbeing.compute_cognitive_load(rn_high)
    assert cli_high >= 85.0
    assert rn_high.assignment_locked is True
    print(f" -> Nurse Cognitive Load: Low={cli_low}, High={cli_high} (Assignment Locked: {rn_high.assignment_locked})")

    # 2. Inpatient Circadian & Acoustic Envelope
    room_day = PatientRoomWellbeing("ROOM-1", "PT-1", ambient_lux=650.0, noise_level_db=42.0)
    wellbeing.evaluate_inpatient_room(room_day, current_hour_24=14.0)
    assert room_day.circadian_phase == "DAY_PROMOTING"
    assert room_day.acoustic_envelope_breach is False

    room_night_loud = PatientRoomWellbeing("ROOM-2", "PT-2", ambient_lux=30.0, noise_level_db=52.0)
    wellbeing.evaluate_inpatient_room(room_night_loud, current_hour_24=23.0)
    assert room_night_loud.circadian_phase == "NIGHT_RESTORATION"
    assert room_night_loud.acoustic_envelope_breach is True
    print(" -> Inpatient Circadian Phase & Acoustic Envelope Checks: PASS")

    # 3. Intelligent Nuisance Alarm Filter
    artifact_alarm = wellbeing.filter_nuisance_alarm(spo2_drop=True, hr_variance=False, motion_detected=True)
    assert artifact_alarm["action"] == "SUPPRESS_NUISANCE_ALARM"
    assert artifact_alarm["sound_chime"] is False

    real_alarm = wellbeing.filter_nuisance_alarm(spo2_drop=True, hr_variance=True, motion_detected=False)
    assert real_alarm["action"] == "ESCALATE_PHYSIOLOGICAL_DESATURATION"
    assert real_alarm["sound_chime"] is True
    print(" -> Nuisance Alarm Suppression: PASS")

def test_os_command_executor():
    print("[TEST] Running BioOS Microkernel Terminal Command Executor tests...")
    from bioos_runtime import execute_os_command
    
    # 1. ps command
    res_ps = execute_os_command({"command": "ps"})
    assert "ACTUATOR_1KHZ" in res_ps["output"]
    assert "ENVELOPE_100HZ" in res_ps["output"]
    print(" -> OS Command 'ps': PASS")

    # 2. dev command
    res_dev = execute_os_command({"command": "dev"})
    assert "BD Alaris Infusion" in res_dev["output"]
    assert "Hamilton G5 Vent" in res_dev["output"]
    print(" -> OS Command 'dev': PASS")

    # 3. mem command
    res_mem = execute_os_command({"command": "mem"})
    assert "Cache Line 0" in res_mem["output"]
    assert "Cache Line 1" in res_mem["output"]
    print(" -> OS Command 'mem': PASS")

    # 4. wellbeing command
    res_wb = execute_os_command({"command": "wellbeing"})
    assert "Average Clinician CLI" in res_wb["output"]
    print(" -> OS Command 'wellbeing': PASS")

def test_hospital_topology():
    print("[TEST] Running Enterprise Hospital Topology & Multi-Patient Census tests...")
    from hospital_topology import HospitalTopologyManager, PatientRecord
    mgr = HospitalTopologyManager()

    # 1. Facility size verification
    summary = mgr.get_hospital_summary()
    assert summary["total_licensed_beds"] == 78
    assert summary["occupied_beds"] >= 8
    print(f" -> Hospital Total Beds: {summary['total_licensed_beds']}, Occupied: {summary['occupied_beds']}")

    # 2. Admission test
    new_pt = PatientRecord(
        patient_id="TEST-PT-99", mrn="MRN-TEST-1", name="Test Inpatient", age=45, sex="M",
        diagnosis="Acute Appendicitis", esi_triage_score=3, ward_id="ED_MAIN", bed_id="",
        attending_md="Dr. Test, MD", primary_rn="RN Test", admission_timestamp=1000.0
    )
    ok, msg = mgr.admit_patient(new_pt, "ED_MAIN")
    assert ok is True
    assert new_pt.patient_id in mgr.patients
    old_bed = new_pt.bed_id
    assert mgr.wards["ED_MAIN"].beds[old_bed].status == "OCCUPIED"
    print(f" -> Admission: PASS ({old_bed})")

    # 3. Transfer test (ED -> MedSurg)
    t_ok, t_msg = mgr.transfer_patient(new_pt.patient_id, "MEDSURG_NORTH")
    assert t_ok is True
    assert mgr.wards["ED_MAIN"].beds[old_bed].status == "DIRTY"  # EVS cleaning triggered
    assert new_pt.ward_id == "MEDSURG_NORTH"
    print(f" -> Transfer & RTLS Bed Dirtying: PASS (New bed: {new_pt.bed_id})")

    # 4. Discharge test
    d_ok, d_msg = mgr.discharge_patient(new_pt.patient_id)
    assert d_ok is True
    assert new_pt.patient_id not in mgr.patients
    print(" -> Discharge & Census Decompression: PASS")

    # 5. Pharmacy Surveillance & DDI
    pharm = mgr.get_pharmacy_surveillance()
    assert pharm["total_active_infusions"] >= 5
    assert len(pharm["active_ddi_alerts"]) >= 1
    print(f" -> Pharmacy NTI & DDI Surveillance: PASS ({pharm['total_active_infusions']} infusions active)")



def test_new_engine_shell_commands():
    print("[TEST] BioOS shell: news2 / drift / audit / auth commands...")
    from bioos_runtime import execute_os_command

    news2 = execute_os_command({"command": "news2"})
    assert "NEWS2" in news2["output"] and "Census:" in news2["output"]

    drift = execute_os_command({"command": "drift"})
    assert "COGNITIVE DRIFT MONITOR" in drift["output"]
    assert "Control limits" in drift["output"]

    audit = execute_os_command({"command": "audit"})
    assert "HASH-CHAINED AUDIT LOG" in audit["output"]
    assert "INTACT" in audit["output"] or "TAMPERED" in audit["output"]

    auth = execute_os_command({"command": "auth"})
    assert "AUTHENTICATION" in auth["output"]
    assert "PHARMACIST" in auth["output"]  # role list present

    help_out = execute_os_command({"command": "help"})
    for cmd_name in ("news2", "drift", "audit", "auth"):
        assert cmd_name in help_out["output"]
    print(" -> Shell engine commands PASS (news2/drift/audit/auth + help)")


if __name__ == "__main__":
    test_new_engine_shell_commands()
    test_engine5_coe()
    test_engine6_oce()
    test_wellbeing_engine()
    test_os_command_executor()
    test_hospital_topology()
    print("\nALL BIOOS ENTERPRISE HOSPITAL OPERATING SYSTEM COMPONENT TESTS PASSED PERFECTLY!")
