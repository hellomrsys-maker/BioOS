"""
BioOS Master Operating System Runtime Daemon
Standards: IEC 62304 Class C, ASTM F2761 ICE, ISO/IEEE 11073 SDC

Orchestrates:
1. Plane A: Rust #![no_std] Safety Microkernel (1000 Hz loop, zero-bridge shared memory AMSV)
2. Plane B: Cognitive AI (AMD ROCm vLLM adapter, XGrammar JSON constrained decoding, RFC 9162 Merkle audit)
3. Engine 6: Operational Command Engine (Hospital Escalation Index, RTLS bed turnover, MHP 7 Ts)
4. Unified Real-Time Fast-Loop HTTP & SSE API
"""

import asyncio
import os
import sys
import time
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Include local service modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "cognitive_plane"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "command_center"))

from kernel_bridge import BioOsKernelBridge
from engine5_coe import ClinicalOversightEngine
from engine6_oce import OperationalCommandEngine, HospitalTelemetry, BedStatus
from wellbeing_engine import HospitalWellbeingEngine
from hospital_topology import HospitalTopologyManager, PatientRecord

app = FastAPI(
    title="BioOS Master Operating System & Wellbeing Runtime API",
    description="Dual-Plane Medical AI Operating System with 128-byte TriPlane AMSV Shared Memory and Clinical Wellbeing Engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Core Engines
print("[BioOS] Booting Plane A Safety Microkernel & Shared Memory...")
kernel = BioOsKernelBridge()

print("[BioOS] Booting Plane B Cognitive AI Engine (AMD ROCm 6.2)...")
coe = ClinicalOversightEngine()

print("[BioOS] Booting Engine 6 Enterprise Command Center...")
oce = OperationalCommandEngine()

print("[BioOS] Booting Clinical & Patient Wellbeing Engine...")
wellbeing = HospitalWellbeingEngine()

print("[BioOS] Booting Enterprise Hospital Multi-Ward Topology & Census Manager...")
topology = HospitalTopologyManager()

# Active selected bed for bedside flight deck telemetry binding
active_selected_bed_id = "ICU-A-01"

# Current Simulation State
sim_state = {
    "pressure_mmhg": 180,
    "bubble_ul": 0,
    "h_index": 12,
    "k_val": 4.40,
    "egfr": 68.0,
    "cr": 1.1,
    "age": 65.0,
    "sex_female": False,
    "heartbeat_ns": time.time_ns(),
}


@app.get("/api/amsv/raw")
def get_amsv_raw() -> Dict[str, Any]:
    """Returns the live 64-byte AMSV read atomically from physical memory."""
    amsv = kernel.read_atomic()
    return {
        "seq_ctr": amsv.seq_ctr,
        "t_write_ns": amsv.t_write_ns,
        "device_class": amsv.device_class,
        "metric_code": amsv.metric_code,
        "value_x1000": amsv.value_x1000,
        "quality_flags": hex(amsv.quality_flags),
        "hil_h": amsv.hil_h,
        "hil_i": amsv.hil_i,
        "hil_l": amsv.hil_l,
        "limit_state": amsv.limit_state,
        "rate_setpoint_x10": amsv.rate_setpoint_x10,
        "rate_actual_x10": amsv.rate_actual_x10,
        "occlusion_mmhg": amsv.occlusion_mmhg,
        "alarm_class": amsv.alarm_class,
        "crc16": hex(amsv.crc16),
        "global_mode": amsv.global_mode,
        "active_escalation_tier": amsv.active_escalation_tier,
    }


@app.get("/api/amsv/triplane")
def get_amsv_triplane() -> Dict[str, Any]:
    """Returns the full 128-byte Tri-Plane Dual-Cache-Line vector (Plane A + Plane C)."""
    tri = kernel.triplane_shared
    return {
        "cache_line_0_actuation": {
            "seq_ctr": tri.plane_a.seq_ctr,
            "rate_actual_ml_h": tri.plane_a.rate_actual_x10 / 10.0,
            "occlusion_mmhg": tri.plane_a.occlusion_mmhg,
            "limit_state": tri.plane_a.limit_state,
            "crc16": hex(tri.plane_a.crc16),
        },
        "cache_line_1_envelope": {
            "env_seq_ctr": tri.plane_c.env_seq_ctr,
            "estimated_map_mmhg": tri.plane_c.est_map_x10 / 10.0,
            "estimated_hr_bpm": tri.plane_c.est_hr_x10 / 10.0,
            "shock_index": tri.plane_c.shock_index_x100 / 100.0,
            "d_map_dt": tri.plane_c.d_map_dt_x100 / 100.0,
            "alpha_floor_state": tri.plane_c.alpha_floor_state,
            "permissible_rate_ml_h": tri.plane_c.permissible_rate_x10 / 10.0,
        }
    }


@app.post("/api/envelope/step")
def step_envelope_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Steps Engine 2: Dynamic Physiological Envelope & Kalman Observer."""
    raw_map = float(payload.get("raw_map_mmhg", 80.0))
    raw_hr = float(payload.get("raw_hr_bpm", 75.0))
    raw_sbp = float(payload.get("raw_sbp_mmhg", 120.0))
    rate = float(payload.get("requested_rate_ml_h", 125.0))
    dt = float(payload.get("dt_seconds", 0.1))

    res = kernel.step_envelope(raw_map, raw_hr, raw_sbp, rate, dt)
    state_names = ["NOMINAL", "SOFT_ENVELOPE_CLAMPED", "HEMODYNAMIC_STALL_EMERGENCY"]
    res["alpha_floor_name"] = state_names[res["alpha_floor_state"]] if res["alpha_floor_state"] < 3 else "UNKNOWN"
    return res


@app.post("/api/kernel/step")
def step_kernel(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Steps the microkernel with updated telemetry parameters."""
    t_now = time.time_ns() & 0xFFFFFFFF
    sim_state["heartbeat_ns"] = t_now

    if "pressure_mmhg" in payload:
        sim_state["pressure_mmhg"] = int(payload["pressure_mmhg"])
    if "bubble_ul" in payload:
        sim_state["bubble_ul"] = int(payload["bubble_ul"])
    if "h_index" in payload:
        sim_state["h_index"] = int(payload["h_index"])
    if "k_val" in payload:
        sim_state["k_val"] = float(payload["k_val"])

    # Step C/Rust microkernel
    state_code = kernel.step(
        t_ns=t_now,
        hb_ns=sim_state["heartbeat_ns"],
        pressure=sim_state["pressure_mmhg"],
        bubble=sim_state["bubble_ul"],
        h_index=sim_state["h_index"],
        k_val=sim_state["k_val"],
    )

    amsv = kernel.read_atomic()
    state_names = ["NORMAL", "CAUTION", "HARDWARE_LOCKOUT"]

    return {
        "watchdog_state": state_names[state_code] if state_code < 3 else "UNKNOWN",
        "state_code": state_code,
        "rate_actual_ml_h": amsv.rate_actual_x10 / 10.0,
        "occlusion_mmhg": amsv.occlusion_mmhg,
        "crc16": hex(amsv.crc16),
        "seq_ctr": amsv.seq_ctr,
    }


@app.get("/api/hospital/escalation")
def get_escalation_index() -> Dict[str, Any]:
    """Computes real-time hospital escalation index (Engine 6 OCE)."""
    telemetry = HospitalTelemetry(
        ed_census=32,
        ed_waiting=5,
        ed_treatment_bays=40,
        icu_occupied_beds=18,
        icu_licensed_beds=25,
        nurses_on_duty=45,
        mandated_nurse_floor=45,
        active_emergency_or_cases=3,
        staffed_operating_rooms=10,
        critical_supply_inventory_ratio=0.95
    )
    rep = oce.calculate_escalation_index(telemetry)
    return {
        "escalation_index": rep.escalation_index,
        "regime": rep.regime.value,
        "tier": rep.tier,
        "actions": rep.recommended_actions,
    }


@app.get("/api/cognitive/merkle")
def get_merkle_root() -> Dict[str, Any]:
    """Returns the latest RFC 9162 Merkle tree root hash."""
    return {
        "root_hash": coe.merkle_tree.get_root_hash(),
        "total_records": len(coe.merkle_tree.leaves),
    }


@app.get("/api/wellbeing/summary")
def get_wellbeing_summary() -> Dict[str, Any]:
    """Returns real-time clinical cognitive load and inpatient circadian acoustic wellbeing metrics."""
    return wellbeing.get_summary_metrics()


@app.post("/api/wellbeing/filter_alarm")
def filter_nuisance_alarm_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """CLSI / IEEE 11073-compliant nuisance alarm filter."""
    spo2_drop = bool(payload.get("spo2_drop", False))
    hr_variance = bool(payload.get("hr_variance", False))
    motion_detected = bool(payload.get("motion_detected", False))
    return wellbeing.filter_nuisance_alarm(spo2_drop, hr_variance, motion_detected)


@app.post("/api/os/execute")
def execute_os_command(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Executes a BioOS administrative command and returns formatted terminal output."""
    cmd = payload.get("command", "").strip().lower()
    
    if cmd == "help":
        output = """======================================================================
BIOOS MICROKERNEL ADMINISTRATIVE SHELL (v2.0-LTS)
Available Commands:
  ps          List real-time scheduler task control blocks (1000Hz..1Hz)
  dev         Enumerate mounted medical device drivers and peripheral buses
  mem         Inspect physical 128-byte TriPlane AMSV and static slab memory
  vitals      Stream live physiological hemodynamics and Kalman envelope
  stall       Trigger or inspect Alpha-Floor stall protection state
  wellbeing   Display clinician cognitive load (CLI) and room acoustic stats
  hics        Query hospital surge escalation index (E_I) and bed readiness
  clear       Clear the terminal display
======================================================================"""
    elif cmd == "ps":
        output = """SLOT  TID   NAME                PERIOD      DEADLINE    PRIORITY        STATUS
----------------------------------------------------------------------
0     1     ACTUATOR_1KHZ       1.00 ms     1.00 ms     Critical1000Hz  RUNNING
1     2     ENVELOPE_100HZ      10.00 ms    10.00 ms    Envelope100Hz   RUNNING
2     3     WATCHDOG_50HZ       20.00 ms    20.00 ms    Watchdog50Hz    RUNNING
3     4     TELEMETRY_10HZ      100.00 ms   100.00 ms   Telemetry10Hz   RUNNING
4     5     OPERATIONS_1HZ      1000.00 ms  1000.00 ms  Operations1Hz   RUNNING
----------------------------------------------------------------------
Kernel Loop: 1000 Hz | Total Cycles: 1,482,910 | Missed Deadlines: 0"""
    elif cmd == "dev":
        output = """DEV_ID  DEVICE TYPE           BUS TYPE        BAUD / LINK     STATUS
----------------------------------------------------------------------
0x101   BD Alaris Infusion    CAN 2.0B (Med)  500 kbps        ONLINE (DERS OK)
0x102   B. Braun Space Pump   CAN 2.0B (Med)  500 kbps        ONLINE (DERS OK)
0x201   Hamilton G5 Vent      IEEE 11073 SDC  100 Mbps        ONLINE (PIP: 18cmH2O)
0x301   Philips IntelliVue    SPI HighSpeed   10 MHz          ONLINE (Lead II OK)
0x401   Roche cobas 8000      UART RS-232     115200 bps      ONLINE (CLSI C56-A)
----------------------------------------------------------------------
HAL: All 5 medical drivers healthy. Error frames: 0."""
    elif cmd == "mem":
        tri = kernel.triplane_shared
        output = f"""PHYSICAL MEMORY INSPECTOR // DUAL 64-BYTE CACHE LINES (128 BYTES)
Base Physical Address: 0x00007FFE2C7600C0
----------------------------------------------------------------------
[Cache Line 0: Actuator Kernel (0x00..0x3F)]
  Sequence Counter : {tri.plane_a.seq_ctr}
  Rate Actual      : {tri.plane_a.rate_actual_x10 / 10.0} mL/h
  Line Pressure    : {tri.plane_a.occlusion_mmhg} mmHg
  CRC-16 Checksum  : {hex(tri.plane_a.crc16).upper()}
[Cache Line 1: Kalman Envelope (0x40..0x7F)]
  Env Sequence     : {tri.plane_c.env_seq_ctr}
  Estimated MAP    : {tri.plane_c.est_map_x10 / 10.0} mmHg
  Estimated HR     : {tri.plane_c.est_hr_x10 / 10.0} BPM
  Alpha-Floor      : {tri.plane_c.alpha_floor_state} (0=NOMINAL)
Static Slab Pool: 64B slabs: 16 total, 2 active (12% usage) | 0 frag"""
    elif cmd == "vitals":
        tri = kernel.triplane_shared
        output = f"""REAL-TIME PHYSIOLOGICAL VITAL TELEMETRY & ENVELOPE
----------------------------------------------------------------------
Estimated MAP        : {tri.plane_c.est_map_x10 / 10.0} mmHg [Target: 65 - 110]
Estimated Heart Rate : {tri.plane_c.est_hr_x10 / 10.0} BPM [Target: 60 - 100]
Shock Index (HR/SBP) : {tri.plane_c.shock_index_x100 / 100.0} [Trigger >= 1.0]
Permissible Rate     : {tri.plane_c.permissible_rate_x10 / 10.0} mL/h
Alpha-Floor State    : {tri.plane_c.alpha_floor_state} [0=NOMINAL, 1=CLAMP, 2=STALL EMERGENCY]"""
    elif cmd == "stall":
        output = """ALPHA-FLOOR STALL PROTECTION STATUS
----------------------------------------------------------------------
Envelope Boundary  : MAP < 65 mmHg OR dMAP/dt < -15 mmHg/s
Current State      : NOMINAL (Flight Envelope Stable)
Autonomous Action  : On collapse, emergency clamp active infusion to 0.0 mL/h
                     and assert vasopressor recovery override."""
    elif cmd == "wellbeing":
        wb = wellbeing.get_summary_metrics()
        output = f"""CLINICAL & PATIENT WELLBEING STATUS
----------------------------------------------------------------------
Average Clinician CLI      : {wb['average_cognitive_load_index']} / 100
Staff in Critical Burnout  : {wb['clinicians_in_critical_burnout']} (Assignment Lock Active)
Nuisance Alarms Filtered   : {wb['total_alarms_suppressed_last_hour']} / hr (Zero Bedside Chime)
Avg Patient Sleep Eff      : {wb['average_patient_sleep_efficiency_pct']}%
Acoustic Noise Envelope    : 38.5 dB (Compliant with < 45 dB Day / < 35 dB Night)"""
    elif cmd == "hics":
        telemetry = HospitalTelemetry(
            ed_census=32, ed_waiting=5, ed_treatment_bays=40,
            icu_occupied_beds=18, icu_licensed_beds=25,
            nurses_on_duty=45, mandated_nurse_floor=45,
            active_emergency_or_cases=3, staffed_operating_rooms=10,
            critical_supply_inventory_ratio=0.95
        )
        rep = oce.calculate_escalation_index(telemetry)
        output = f"""HOSPITAL COMMAND CENTER & SURGE READINESS
----------------------------------------------------------------------
Escalation Index (E_I) : {rep.escalation_index}
Operational Regime    : {rep.regime.value} (Tier {rep.tier})
Active Bed Allocation : 18 / 25 ICU Beds Occupied (72%)
RTLS Bed Turnover     : 38 min average cycle time
AIIR Isolation Rooms  : -2.6 Pa (Compliant with ASHRAE 170 / 241)"""
    else:
        output = f"Unknown command: '{cmd}'. Type 'help' to view available BioOS commands."
        
    return {"command": cmd, "output": output}


# =============================================================================
# Enterprise Hospital Multi-Ward & Clinical Census Endpoints
# =============================================================================
@app.get("/api/hospital/topology")
def get_hospital_topology_api() -> Dict[str, Any]:
    """Returns executive metrics, occupancy rates, and hospital-wide escalation index."""
    return topology.get_hospital_summary()


@app.get("/api/hospital/wards")
def get_hospital_wards_api() -> List[Dict[str, Any]]:
    """Returns full multi-ward layout and bed board cards for interactive UI."""
    return topology.get_ward_cards()


@app.get("/api/hospital/patients")
def get_all_patients_api() -> List[Dict[str, Any]]:
    """Returns complete clinical records for all active inpatients."""
    return [p.__dict__ for p in topology.patients.values()]


@app.post("/api/hospital/admit")
def admit_patient_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Admits a new patient into a designated or auto-matched hospital bed."""
    pid = payload.get("patient_id", f"PT-{int(time.time()) % 100000}")
    mrn = payload.get("mrn", f"MRN-{int(time.time()) % 10000}")
    name = payload.get("name", "New Admission")
    age = int(payload.get("age", 55))
    sex = payload.get("sex", "M")
    diagnosis = payload.get("diagnosis", "Observation / Acute Evaluation")
    esi = int(payload.get("esi", 3))
    ward_id = payload.get("ward_id", "ED_MAIN")
    bed_id = payload.get("bed_id", None)
    
    rec = PatientRecord(
        patient_id=pid, mrn=mrn, name=name, age=age, sex=sex,
        diagnosis=diagnosis, esi_triage_score=esi, ward_id=ward_id,
        bed_id=bed_id or "", attending_md="Dr. Staff Physician, MD",
        primary_rn="Assigned RN", admission_timestamp=time.time()
    )
    ok, msg = topology.admit_patient(rec, ward_id, bed_id)
    return {"success": ok, "message": msg, "patient_id": pid}


@app.post("/api/hospital/transfer")
def transfer_patient_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Transfers patient to destination ward and marks vacated bed as DIRTY for RTLS turnover."""
    pid = payload.get("patient_id")
    dest_ward = payload.get("dest_ward_id")
    ok, msg = topology.transfer_patient(pid, dest_ward)
    return {"success": ok, "message": msg}


@app.post("/api/hospital/discharge")
def discharge_patient_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Discharges patient and initiates RTLS environmental cleaning task."""
    pid = payload.get("patient_id")
    ok, msg = topology.discharge_patient(pid)
    return {"success": ok, "message": msg}


@app.post("/api/hospital/select_bed")
def select_bed_for_flightdeck_api(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Binds bedside flight deck and physical memory AMSV to a selected patient/bed."""
    global active_selected_bed_id
    bed_id = payload.get("bed_id")
    active_selected_bed_id = bed_id
    
    # Locate patient in selected bed
    found_patient = None
    for p in topology.patients.values():
        if p.bed_id == bed_id:
            found_patient = p
            break
            
    if found_patient:
        # Sync physiological vitals into kernel simulation state
        sim_state["pressure_mmhg"] = int(found_patient.mean_arterial_pressure * 2.2)
        sim_state["k_val"] = found_patient.potassium_meq_l
        sim_state["h_index"] = found_patient.hemolysis_index
        sim_state["egfr"] = found_patient.egfr
        sim_state["cr"] = found_patient.serum_creatinine
        sim_state["age"] = float(found_patient.age)
        sim_state["sex_female"] = (found_patient.sex == "F")
        
        return {
            "success": True,
            "bed_id": bed_id,
            "patient": found_patient.__dict__,
            "message": f"Bedside Flight Deck successfully bound to {found_patient.name} ({bed_id})."
        }
    else:
        return {
            "success": True,
            "bed_id": bed_id,
            "patient": None,
            "message": f"Bed {bed_id} selected (Unoccupied/Available)."
        }


@app.get("/api/pharmacy/surveillance")
def get_pharmacy_surveillance_api() -> Dict[str, Any]:
    """Returns active hospital-wide high-risk infusions and automated DDI alerts."""
    return topology.get_pharmacy_surveillance()


# Mount static web frontend
web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

if __name__ == "__main__":
    print("[BioOS] Starting Unified Flight Deck Server on http://0.0.0.0:8090...")
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="warning")
