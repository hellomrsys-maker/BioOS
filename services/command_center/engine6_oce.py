"""
Engine 6: Operational Command Engine (OCE)
BioOS Enterprise Command Center & Disaster Surge Subsystem

Implements:
- Hospital Escalation Index (E_I)
- 5-Stage RTLS Automated Bed Turnover
- Massive Hemorrhage Protocol (MHP) '7 Ts' with TEG guidance
- Nurse-Driven Standing Orders (Sepsis 1-hr, ACS, Hypoglycemia)
- ASHRAE 170 / 241 HVAC Pressure Cascade Supervision
- HICS 2014 & Reverse Triage Early Discharge (RTTL / Kelen)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import time


class OperationalRegime(Enum):
    ROUTINE = "ROUTINE"       # E_I < 0.40
    SURGE = "SURGE"           # 0.40 <= E_I < 0.75
    DISASTER = "DISASTER"     # E_I >= 0.75 or Incident Command declared


class BedStatus(Enum):
    OCCUPIED = "OCCUPIED"
    DIRTY = "DIRTY"
    CLEANING = "CLEANING"
    INSPECTED = "INSPECTED"
    AVAILABLE = "AVAILABLE"


@dataclass
class HospitalTelemetry:
    ed_census: int
    ed_waiting: int
    ed_treatment_bays: int
    icu_occupied_beds: int
    icu_licensed_beds: int
    nurses_on_duty: int
    mandated_nurse_floor: int
    active_emergency_or_cases: int
    staffed_operating_rooms: int
    critical_supply_inventory_ratio: float  # 1.0 = fully stocked, 0.0 = stockout


@dataclass
class EscalationReport:
    escalation_index: float
    regime: OperationalRegime
    tier: int
    ed_crowding_component: float
    icu_strain_component: float
    nurse_deficit_component: float
    or_backlog_component: float
    supply_depletion_component: float
    recommended_actions: List[str]


class OperationalCommandEngine:
    """Enterprise hospital command center orchestration engine."""

    def __init__(self):
        self.regime = OperationalRegime.ROUTINE
        self.hics_active = False
        self.hics_incident_id: Optional[str] = None

    def calculate_escalation_index(self, telemetry: HospitalTelemetry) -> EscalationReport:
        """
        Calculates E_I = 0.35 * ED + 0.25 * ICU + 0.20 * NurseDeficit + 0.10 * OR + 0.10 * Supply
        """
        # 1. ED Crowding
        ed_bay_capacity = max(1, telemetry.ed_treatment_bays)
        ed_crowding = min(2.0, (telemetry.ed_census + telemetry.ed_waiting) / ed_bay_capacity)

        # 2. ICU Strain
        icu_capacity = max(1, telemetry.icu_licensed_beds)
        icu_strain = min(1.5, telemetry.icu_occupied_beds / icu_capacity)

        # 3. Nurse Deficit
        nurse_floor = max(1, telemetry.mandated_nurse_floor)
        nurse_deficit = max(0.0, 1.0 - (telemetry.nurses_on_duty / nurse_floor))

        # 4. OR Backlog
        or_capacity = max(1, telemetry.staffed_operating_rooms)
        or_backlog = min(1.5, telemetry.active_emergency_or_cases / or_capacity)

        # 5. Supply Depletion
        supply_depletion = max(0.0, 1.0 - min(1.0, telemetry.critical_supply_inventory_ratio))

        # Weighted Composite
        e_i = (
            0.35 * ed_crowding +
            0.25 * icu_strain +
            0.20 * nurse_deficit +
            0.10 * or_backlog +
            0.10 * supply_depletion
        )

        actions = []
        if e_i < 0.40 and not self.hics_active:
            regime = OperationalRegime.ROUTINE
            tier = 0
            actions.append("Nominal hospital operations. Routine elective admissions approved.")
        elif e_i < 0.60 and not self.hics_active:
            regime = OperationalRegime.SURGE
            tier = 1
            actions.append("Surge Tier 1: Alert EVS for expedited bed turnover; delay elective admissions.")
        elif e_i < 0.75 and not self.hics_active:
            regime = OperationalRegime.SURGE
            tier = 2
            actions.append("Surge Tier 2: Postpone elective surgical procedures; trigger PACU surge beds.")
        else:
            regime = OperationalRegime.DISASTER
            tier = 3
            actions.append("DISASTER TIER 3: Activate HICS Command Center; execute reverse triage discharges.")

        self.regime = regime

        return EscalationReport(
            escalation_index=round(e_i, 3),
            regime=regime,
            tier=tier,
            ed_crowding_component=round(ed_crowding, 3),
            icu_strain_component=round(icu_strain, 3),
            nurse_deficit_component=round(nurse_deficit, 3),
            or_backlog_component=round(or_backlog, 3),
            supply_depletion_component=round(supply_depletion, 3),
            recommended_actions=actions,
        )

    # -------------------------------------------------------------------------
    # 5-Stage RTLS Automated Bed Turnover
    # -------------------------------------------------------------------------
    def transition_bed_state(self, current_status: BedStatus, ble_beacon_event: str) -> BedStatus:
        """
        Manages RTLS automated transitions:
        Occupied -> Dirty -> Cleaning -> Inspected -> Available
        """
        if current_status == BedStatus.OCCUPIED and ble_beacon_event == "PATIENT_DISCHARGED":
            return BedStatus.DIRTY
        elif current_status == BedStatus.DIRTY and ble_beacon_event == "EVS_BADGE_DETECTED":
            return BedStatus.CLEANING
        elif current_status == BedStatus.CLEANING and ble_beacon_event == "UV_CYCLE_COMPLETE":
            return BedStatus.INSPECTED
        elif current_status == BedStatus.INSPECTED and ble_beacon_event == "SUPERVISOR_QR_VERIFIED":
            return BedStatus.AVAILABLE
        return current_status

    # -------------------------------------------------------------------------
    # Massive Hemorrhage Protocol (MHP) "7 Ts" Evaluation
    # -------------------------------------------------------------------------
    def evaluate_mhp_activation(
        self,
        heart_rate: int,
        systolic_bp: int,
        penetrating_trauma: bool,
        fast_ultrasound_positive: bool,
        base_deficit: float,
        teg_r_time_mins: Optional[float] = None,
        teg_max_amplitude_mm: Optional[float] = None,
        teg_ly30_percent: Optional[float] = None,
    ) -> Dict:
        """
        Evaluates Shock Index (HR / SBP) and ABC Score for MHP triggering.
        Provides targeted viscoelastic TEG guidance.
        """
        shock_index = heart_rate / max(1, systolic_bp)

        # ABC Score: 1 pt each for penetrating trauma, SBP <= 90, HR >= 120, positive FAST
        abc_score = 0
        if penetrating_trauma: abc_score += 1
        if systolic_bp <= 90: abc_score += 1
        if heart_rate >= 120: abc_score += 1
        if fast_ultrasound_positive: abc_score += 1

        mhp_triggered = (shock_index >= 1.0) or (abc_score >= 2) or (base_deficit <= -6.0)

        teg_guidance = []
        if teg_r_time_mins and teg_r_time_mins > 10.0:
            teg_guidance.append("Prolonged R-Time (>10 min): Transfuse Fresh Frozen Plasma (FFP)")
        if teg_max_amplitude_mm and teg_max_amplitude_mm < 50.0:
            teg_guidance.append("Low Maximum Amplitude (<50 mm): Transfuse Platelets / Cryoprecipitate")
        if teg_ly30_percent and teg_ly30_percent > 3.0:
            teg_guidance.append("Elevated LY30 (>3%): Administer Tranexamic Acid (TXA 1g IV)")

        return {
            "mhp_triggered": mhp_triggered,
            "shock_index": round(shock_index, 2),
            "abc_score": abc_score,
            "blood_ratio": "1:1:1 (4 units pRBC : 4 units FFP : 1 adult dose Platelets)",
            "temperature_target_celsius": ">= 36.0",
            "fibrinogen_target_g_l": ">= 1.5",
            "platelet_target": ">= 50 x 10^9/L",
            "teg_guidance": teg_guidance,
        }

    # -------------------------------------------------------------------------
    # Nurse-Driven Standing Orders
    # -------------------------------------------------------------------------
    def evaluate_standing_orders(
        self,
        temperature_c: float,
        heart_rate: int,
        respiratory_rate: int,
        wbc_count: Optional[float],
        serum_lactate_mmol_l: Optional[float],
        blood_glucose_mg_dl: Optional[float],
        chest_pain: bool,
    ) -> List[Dict]:
        """Autonomous protocol triggers based on objective biomarker gates."""
        orders = []

        # 1. Sepsis 1-Hour Bundle
        # SIRS criteria: 2 or more of (Temp > 38.3 or < 36.0, HR > 90, RR > 20, WBC > 12)
        sirs_count = 0
        if temperature_c > 38.3 or temperature_c < 36.0: sirs_count += 1
        if heart_rate > 90: sirs_count += 1
        if respiratory_rate > 20: sirs_count += 1
        if wbc_count and (wbc_count > 12.0 or wbc_count < 4.0): sirs_count += 1

        if (sirs_count >= 2 and serum_lactate_mmol_l and serum_lactate_mmol_l >= 2.0) or (serum_lactate_mmol_l and serum_lactate_mmol_l >= 4.0):
            orders.append({
                "protocol": "SEPSIS_1_HOUR_BUNDLE",
                "priority": "STAT_EMERGENCY",
                "actions": [
                    "Draw 2 sets of blood cultures prior to antibiotic initiation",
                    "Administer broad-spectrum empiric IV antibiotics within 60 minutes",
                    "Initiate 30 mL/kg IV crystalloid bolus for lactate >= 4.0 or hypotension",
                    "Repeat serum lactate within 2 to 4 hours",
                ]
            })

        # 2. Acute Coronary Syndrome (ACS)
        if chest_pain:
            orders.append({
                "protocol": "ACS_CHEST_PAIN_PATHWAY",
                "priority": "STAT",
                "actions": [
                    "Perform 12-lead Electrocardiogram (ECG) within <= 10 minutes",
                    "Administer Aspirin 324 mg chewable PO",
                    "Draw baseline high-sensitivity Cardiac Troponin (hs-cTnI)",
                    "Establish continuous continuous telemetry monitoring and IV access",
                ]
            })

        # 3. Severe Hypoglycemia
        if blood_glucose_mg_dl and blood_glucose_mg_dl < 70.0:
            orders.append({
                "protocol": "HYPOGLYCEMIA_RESCUE",
                "priority": "STAT_IMMEDIATE",
                "actions": [
                    "Administer 25 mL Dextrose 50% in Water (D50W) IV push",
                    "Recheck capillary blood glucose in 15 minutes",
                    "If IV access unavailable, administer Glucagon 1 mg IM",
                ]
            })

        return orders

    # -------------------------------------------------------------------------
    # ASHRAE 170 / 241 HVAC Pressure Cascade Supervision
    # -------------------------------------------------------------------------
    def evaluate_hvac_pressure(self, room_type: str, differential_pressure_pa: float, ach: float) -> Dict:
        """
        AIIR requires -2.5 Pa (+/- 0.5 Pa) and >= 12 ACH.
        Protective Environment requires +2.5 Pa and >= 12 ACH.
        """
        if room_type == "AIIR_NEGATIVE_PRESSURE":
            is_compliant = differential_pressure_pa <= -2.0 and ach >= 12.0
            alarm = differential_pressure_pa > -0.5  # Gradient reversed or lost
            target = "-2.5 Pa (+/- 0.5 Pa), >= 12 ACH"
        elif room_type == "PROTECTIVE_POSITIVE_PRESSURE":
            is_compliant = differential_pressure_pa >= 2.0 and ach >= 12.0
            alarm = differential_pressure_pa < 0.5
            target = "+2.5 Pa (+/- 0.5 Pa), >= 12 ACH"
        else:
            is_compliant = True
            alarm = False
            target = "Standard Room Pressure"

        return {
            "room_type": room_type,
            "measured_pressure_pa": differential_pressure_pa,
            "measured_ach": ach,
            "target": target,
            "compliant": is_compliant,
            "containment_alarm": alarm,
        }

    # -------------------------------------------------------------------------
    # HICS Disaster Reverse Triage (RTTL / Kelen Methodology)
    # -------------------------------------------------------------------------
    def evaluate_reverse_triage_candidate(
        self,
        patient_id: str,
        predicted_48h_mortality_percent: float,
        requires_icu_vasopressors: bool,
        requires_mechanical_ventilation: bool,
        home_oxygen_capable: bool,
    ) -> Dict:
        """
        Reverse Triage: In a mass casualty surge, identify inpatients with
        < 4.0% 48-hour mortality risk who can be safely discharged to home/convalescent care,
        instantly unlocking 20-30% bed capacity.
        """
        eligible = (
            predicted_48h_mortality_percent < 4.0 and
            not requires_icu_vasopressors and
            not requires_mechanical_ventilation
        )

        return {
            "patient_id": patient_id,
            "predicted_48h_mortality_percent": predicted_48h_mortality_percent,
            "reverse_triage_eligible": eligible,
            "disposition": "Expedited Early Discharge to Free Surge Bed" if eligible else "Retain Inpatient (High Acuity)",
            "safety_barrier": "Pre-discharge pulse oximetry, 48-hour telemedicine check, and oral medication handover" if eligible else "Vital organ support ongoing",
        }
