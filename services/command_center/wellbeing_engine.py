# -*- coding: utf-8 -*-
"""
BioOS Clinical & Patient Wellbeing Engine
Implements clinician cognitive load tracking, alert fatigue suppression,
shift ergonomics, circadian lighting controls, and restorative sleep envelopes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time
import math

@dataclass
class ClinicianProfile:
    clinician_id: str
    name: str
    role: str  # "ICU_RN", "ATTENDING", "RESIDENT", "PHARMACIST"
    shift_hours_elapsed: float = 0.0
    active_patients_count: int = 1
    high_acuity_patients_count: int = 0
    alarms_experienced_last_hour: int = 12
    consecutive_shift_days: int = 1
    cognitive_load_index: float = 25.0  # 0 to 100
    burnout_risk_level: str = "LOW"  # LOW, MODERATE, HIGH, CRITICAL
    assignment_locked: bool = False

@dataclass
class PatientRoomWellbeing:
    room_id: str
    patient_id: str
    ambient_lux: float = 650.0  # Lux (day target: 500-1000, night target: <50)
    circadian_phase: str = "DAY_PROMOTING"  # DAY_PROMOTING, DUSK_TRANSITION, NIGHT_RESTORATION
    noise_level_db: float = 38.5  # dB (day max: 45, night max: 35)
    acoustic_envelope_breach: bool = False
    sleep_efficiency_score: float = 88.0  # 0 to 100%
    delirium_risk_score: str = "MINIMAL"  # MINIMAL, ELEVATED, SEVERE
    alarms_suppressed_last_hour: int = 24  # Non-actionable alarms filtered
    actionable_alerts_count: int = 1

class HospitalWellbeingEngine:
    def __init__(self):
        self.clinicians: Dict[str, ClinicianProfile] = {
            "RN-101": ClinicianProfile("RN-101", "Sarah Chen, BSN, CCRN", "ICU_RN", 4.5, 2, 1, 14, 2, 42.0, "LOW", False),
            "RN-102": ClinicianProfile("RN-102", "Marcus Miller, RN", "ICU_RN", 9.5, 3, 2, 38, 4, 78.5, "MODERATE", False),
            "RN-103": ClinicianProfile("RN-103", "Elena Rostova, CCRN", "ICU_RN", 11.2, 3, 3, 56, 5, 89.2, "CRITICAL", True),
            "MD-201": ClinicianProfile("MD-201", "Dr. David Thorne, MD", "ATTENDING", 6.0, 12, 4, 22, 3, 55.0, "MODERATE", False),
        }
        
        self.patient_rooms: Dict[str, PatientRoomWellbeing] = {
            "ICU-POD-A-01": PatientRoomWellbeing("ICU-POD-A-01", "PT-88219", 680.0, "DAY_PROMOTING", 41.2, False, 84.0, "MINIMAL", 19, 2),
            "ICU-POD-A-02": PatientRoomWellbeing("ICU-POD-A-02", "PT-94102", 720.0, "DAY_PROMOTING", 48.6, True, 72.0, "ELEVATED", 32, 1),
            "ICU-POD-B-01": PatientRoomWellbeing("ICU-POD-B-01", "PT-77341", 35.0, "NIGHT_RESTORATION", 32.1, False, 92.0, "MINIMAL", 14, 0),
            "ICU-POD-B-02": PatientRoomWellbeing("ICU-POD-B-02", "PT-60293", 28.0, "NIGHT_RESTORATION", 34.0, False, 89.0, "MINIMAL", 18, 1),
        }

    def compute_cognitive_load(self, c: ClinicianProfile) -> float:
        """
        Calculates clinician Cognitive Load Index (0-100) based on:
        - Shift duration fatigue factor (exponential after 8 hours)
        - Patient load and acuity ratio
        - Alarm density (fatigue driver)
        - Consecutive working days
        """
        shift_factor = c.shift_hours_elapsed * 4.0
        if c.shift_hours_elapsed > 8.0:
            shift_factor += (c.shift_hours_elapsed - 8.0) ** 1.6 * 5.0
            
        acuity_factor = (c.active_patients_count * 8.0) + (c.high_acuity_patients_count * 15.0)
        alarm_factor = min(30.0, c.alarms_experienced_last_hour * 0.6)
        consecutive_factor = (c.consecutive_shift_days - 1) * 4.0
        
        raw_cli = shift_factor + acuity_factor + alarm_factor + consecutive_factor
        cli = max(5.0, min(100.0, raw_cli))
        c.cognitive_load_index = round(cli, 1)
        
        if cli < 50.0:
            c.burnout_risk_level = "LOW"
            c.assignment_locked = False
        elif cli < 75.0:
            c.burnout_risk_level = "MODERATE"
            c.assignment_locked = False
        elif cli < 85.0:
            c.burnout_risk_level = "HIGH"
            c.assignment_locked = False
        else:
            c.burnout_risk_level = "CRITICAL"
            c.assignment_locked = True  # Safety Interlock: Prevent new acute admissions
            
        return c.cognitive_load_index

    def evaluate_inpatient_room(self, room: PatientRoomWellbeing, current_hour_24: float) -> PatientRoomWellbeing:
        """
        Evaluates room circadian lighting and acoustic envelope.
        Daytime: 07:00 to 19:00 -> Target 500-1000 lux, Max Noise 45 dB
        Nighttime: 19:00 to 07:00 -> Target <50 lux, Max Noise 35 dB
        """
        is_day = 7.0 <= current_hour_24 < 19.0
        
        if is_day:
            room.circadian_phase = "DAY_PROMOTING"
            room.acoustic_envelope_breach = (room.noise_level_db > 45.0)
        else:
            room.circadian_phase = "NIGHT_RESTORATION"
            room.acoustic_envelope_breach = (room.noise_level_db > 35.0)
            
        # Delirium risk rises with acoustic breaches and sleep fragmentation
        if room.acoustic_envelope_breach:
            room.sleep_efficiency_score = max(40.0, room.sleep_efficiency_score - 2.5)
        else:
            room.sleep_efficiency_score = min(98.0, room.sleep_efficiency_score + 0.5)
            
        if room.sleep_efficiency_score < 60.0:
            room.delirium_risk_score = "SEVERE"
        elif room.sleep_efficiency_score < 78.0:
            room.delirium_risk_score = "ELEVATED"
        else:
            room.delirium_risk_score = "MINIMAL"
            
        return room

    def filter_nuisance_alarm(self, spo2_drop: bool, hr_variance: bool, motion_detected: bool) -> Dict:
        """
        CLSI / IEEE 11073-compliant alarm nuisance mitigation:
        If SpO2 drop is detected simultaneously with significant motion artifact 
        and no autonomic heart rate variance, the alarm is suppressed as probe displacement artifact.
        """
        if spo2_drop and motion_detected and not hr_variance:
            return {
                "action": "SUPPRESS_NUISANCE_ALARM",
                "classification": "MOTION_ARTIFACT_TRANSDUCER_SLIP",
                "sound_chime": False,
                "log_message": "Transient SpO2 probe artifact suppressed. Zero nurse disruption."
            }
        elif spo2_drop and hr_variance:
            return {
                "action": "ESCALATE_PHYSIOLOGICAL_DESATURATION",
                "classification": "GENUINE_HYPOXIA_CRISIS",
                "sound_chime": True,
                "log_message": "Concordant SpO2 drop and autonomic HR response detected. Immediate bedside alarm."
            }
        else:
            return {
                "action": "ROUTINE_MONITOR",
                "classification": "STABLE",
                "sound_chime": False,
                "log_message": "Vitals within normal limits."
            }

    def get_summary_metrics(self) -> Dict:
        for c in self.clinicians.values():
            self.compute_cognitive_load(c)
            
        avg_cli = sum(c.cognitive_load_index for c in self.clinicians.values()) / len(self.clinicians)
        burnout_locks = sum(1 for c in self.clinicians.values() if c.assignment_locked)
        total_suppressed = sum(r.alarms_suppressed_last_hour for r in self.patient_rooms.values())
        avg_sleep_eff = sum(r.sleep_efficiency_score for r in self.patient_rooms.values()) / len(self.patient_rooms)
        
        return {
            "timestamp": time.time(),
            "average_cognitive_load_index": round(avg_cli, 1),
            "clinicians_in_critical_burnout": burnout_locks,
            "total_alarms_suppressed_last_hour": total_suppressed,
            "average_patient_sleep_efficiency_pct": round(avg_sleep_eff, 1),
            "clinicians": [c.__dict__ for c in self.clinicians.values()],
            "patient_rooms": [r.__dict__ for r in self.patient_rooms.values()]
        }

if __name__ == "__main__":
    engine = HospitalWellbeingEngine()
    print("Testing Clinical Wellbeing Engine:")
    metrics = engine.get_summary_metrics()
    print("Average Clinician Cognitive Load:", metrics["average_cognitive_load_index"])
    print("Clinicians with Assignment Lock (Critical Fatigue):", metrics["clinicians_in_critical_burnout"])
    print("Total Nuisance Alarms Suppressed (Last Hour):", metrics["total_alarms_suppressed_last_hour"])
    print("Average Inpatient Sleep Efficiency:", metrics["average_patient_sleep_efficiency_pct"])
