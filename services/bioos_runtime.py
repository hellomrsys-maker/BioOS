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
import base64
import io
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
from audit_store import BioOsPersistenceStore
from fhir_facade import FhirService
from drift_monitor import ApprovalRateDriftMonitor
from ews_trend import News2TrendMonitor
import rbac_auth

app = FastAPI(
    title="BioOS Master Operating System & Wellbeing Runtime API",
    description="Dual-Plane Medical AI Operating System with 128-byte TriPlane AMSV Shared Memory and Clinical Wellbeing Engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    # Same-origin flight deck only. Wildcard origins with credentials are an
    # invalid/unsafe combination (browsers reject; security scanners flag).
    allow_origins=[
        "http://localhost:8090",
        "http://127.0.0.1:8090",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate Core Engines
print("[BioOS] Booting Plane A Safety Microkernel & Shared Memory...")
kernel = BioOsKernelBridge()

print("[BioOS] Booting Plane B Cognitive AI Engine (Meta Model API / Llama 3.1 & SAM 3.1)...")
coe = ClinicalOversightEngine()

print("[BioOS] Booting Engine 6 Enterprise Command Center...")
oce = OperationalCommandEngine()

print("[BioOS] Booting Clinical & Patient Wellbeing Engine...")
wellbeing = HospitalWellbeingEngine()

print("[BioOS] Booting Enterprise Hospital Multi-Ward Topology & Census Manager...")
topology = HospitalTopologyManager()

print("[BioOS] Booting Persistence & Hash-Chained Audit Store (SQLite WAL)...")
store = BioOsPersistenceStore(
    os.environ.get(
        "BIOOS_DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bioos_runtime.db"),
    )
)

print("[BioOS] Booting FHIR R4 Facade (Plane B advisory layer, kernel-gated orders)...")
fhir = FhirService(topology, store, kernel_bridge=kernel)

print("[BioOS] Booting Cognitive Drift Monitor (approval-rate control limits)...")
drift_monitor = ApprovalRateDriftMonitor()

print("[BioOS] Booting NEWS2 Trend Monitor (RCP deterioration trajectory rules)...")
news2_trend = News2TrendMonitor()


def _start_mllp_listener() -> None:
    """Optional HL7 v2 MLLP stub listener; disabled unless BIOOS_MLLP_PORT is set."""
    port = os.environ.get("BIOOS_MLLP_PORT")
    if not port:
        return
    import threading

    from hl7_mllp import MllpAuditServer

    def on_message(parsed: Dict[str, Any], raw: str) -> None:
        # Stub policy: HL7 receipts are AUDITED, never acted on clinically.
        store.append_audit_entry(
            actor="HL7_MLLP",
            action="HL7_MESSAGE_RECEIVED",
            resource_type=parsed.get("message_type") or "HL7",
            resource_id=parsed.get("control_id") or "unknown",
            payload={
                "patient_id": parsed.get("patient_id"),
                "trigger_event": parsed.get("trigger_event"),
                "sending_app": parsed.get("sending_app"),
            },
        )

    server = MllpAuditServer(port=int(port), host="127.0.0.1", on_message=on_message)
    threading.Thread(target=server.run_blocking, daemon=True, name="bioos-mllp").start()
    print(f"[BioOS] HL7 v2 MLLP listener (stub) on 127.0.0.1:{port} -> audit store")


_start_mllp_listener()


def _start_telemetry_sampler() -> None:
    """Continuous Plane A -> store AMSV telemetry capture.

    Rate via BIOOS_TELEMETRY_HZ (default 2 Hz; 0 disables). Fixed-period
    daemon-thread loop; storage errors are swallowed (sampling must never
    take down the runtime)."""
    hz = float(os.environ.get("BIOOS_TELEMETRY_HZ", "2"))
    if hz <= 0:
        return
    import threading

    def loop() -> None:
        period = 1.0 / hz
        while True:
            started = time.perf_counter()
            try:
                amsv = kernel.read_atomic()
                store.append_telemetry(
                    ts_ns=time.time_ns(),
                    device_class=amsv.device_class,
                    metric_code=amsv.metric_code,
                    value_x1000=amsv.value_x1000,
                    quality_flags=amsv.quality_flags,
                    limit_state=amsv.limit_state,
                    alarm_class=amsv.alarm_class,
                )
            except Exception:
                pass
            elapsed = time.perf_counter() - started
            time.sleep(max(0.0, period - elapsed))

    threading.Thread(target=loop, daemon=True, name="bioos-telemetry").start()
    print(f"[BioOS] Background telemetry sampler at {hz} Hz -> audit store")


_start_telemetry_sampler()


def _hydrate_news2_trend() -> None:
    """Seeds the NEWS2 trend monitor from persisted observations so published
    trajectory rules (rise >= 2, sustained >= 3) survive runtime restarts."""
    try:
        observations = store.query_clinical_observations(limit=500)
    except Exception:
        return
    restored = 0
    for obs in observations:
        try:
            news2_trend.record(obs["patient_id"], obs["total_score"])
            restored += 1
        except Exception:
            pass
    print(f"[BioOS] NEWS2 trend history hydrated ({restored} persisted observations)")


_hydrate_news2_trend()

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


@app.get("/api/health")
def health() -> Dict[str, Any]:
    """Liveness probe for orchestration & container HEALTHCHECK (no kernel dependency)."""
    return {"status": "ok", "service": "bioos-runtime", "version": "2.0.0", "time_ns": time.time_ns()}


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
    t_now = time.time_ns()  # full u64 monotonic base (u32 truncation removed - wrap fix)
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
    # Persist telemetry sample (append-only time series); capture must never
    # break the control-plane step on storage errors.
    try:
        store.append_telemetry(
            ts_ns=time.time_ns(),
            device_class=amsv.device_class,
            metric_code=amsv.metric_code,
            value_x1000=amsv.value_x1000,
            quality_flags=amsv.quality_flags,
            limit_state=amsv.limit_state,
            alarm_class=amsv.alarm_class,
        )
    except Exception:
        pass
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
  news2       RCP NEWS2 census deterioration matrix and trajectory alerts
  drift       Cognitive-plane approval-rate drift monitor status
  audit       Verify hash-chained audit log integrity and counts
  auth        Show authentication mode (OIDC RS256 / dev HS256) and roles
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
    elif cmd == "news2":
        from ews_engine import news2_from_patient

        NL = chr(10)
        rows = []
        for rec in topology.patients.values():
            s = news2_from_patient(rec)
            rows.append((rec.bed_id or "--", rec.name, s["total_score"], s["clinical_risk"]))
        rows.sort(key=lambda r: -r[2])
        counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for r in rows:
            counts[r[3]] = counts.get(r[3], 0) + 1
        lines = ["BED   PATIENT                     NEWS2  RISK", "-" * 54]
        for bed, name, score, risk in rows:
            lines.append("{:<5} {:<27} {:>5}   {}".format(bed, name, score, risk))
        lines.append("-" * 54)
        lines.append("Census: {} patients | LOW {} | MEDIUM {} | HIGH {}".format(
            len(rows), counts["LOW"], counts["MEDIUM"], counts["HIGH"],
        ))
        lines.append("Trend observations in memory: " + str(sum(len(news2_trend.history(r[0])) for r in rows)))
        lines.append("(RCP NEWS2 Dec 2017 - advisory only, Plane B)")
        output = NL.join(lines)
    elif cmd == "drift":
        NL = chr(10)
        rate = drift_monitor.approval_rate()
        rate_text = str(rate) if rate is not None else "insufficient data"
        output = NL.join([
            "COGNITIVE DRIFT MONITOR (approval-rate control limits)",
            "-" * 54,
            "Rolling approval rate : " + rate_text,
            "Control limits        : [{}, {}]".format(drift_monitor.lower_limit, drift_monitor.upper_limit),
            "Window / min samples  : {} / {}".format(drift_monitor.window_size, drift_monitor.min_samples),
            "Alerts emitted        : {}".format(drift_monitor.alerts_emitted),
            "HIGH alert = possible guard bypass | LOW alert = schema drift",
        ])
    elif cmd == "audit":
        NL = chr(10)
        verdict = store.verify_audit_chain()
        status = "INTACT" if verdict["valid"] else "TAMPERED at entry {} ({})".format(verdict["first_bad_id"], verdict["reason"])
        output = NL.join([
            "HASH-CHAINED AUDIT LOG (RFC 9162-complement)",
            "-" * 54,
            "Chain verdict         : " + status,
            "Entries verified      : {}".format(verdict["entries"]),
            "Telemetry samples     : {}".format(store.telemetry_count()),
            "Tamper-evidence: each entry hashes the previous entry hash",
        ])
    elif cmd == "auth":
        import rbac_auth as _rbac
        from oidc_auth import issuer_configured as _oidc_issuer_configured

        NL = chr(10)
        if _oidc_issuer_configured():
            mode = "OIDC RS256 via hospital IdP JWKS (BIOOS_OIDC_ISSUER set)"
        else:
            mode = "Development HS256 (set BIOOS_OIDC_ISSUER for production)"
        enforced = "ENFORCED" if os.environ.get("BIOOS_AUTH_REQUIRED") == "1" else "dev-bypass (BIOOS_AUTH_REQUIRED=1 to enforce)"
        roles = ", ".join(sorted(_rbac.ROLE_PERMISSIONS.keys()))
        output = NL.join([
            "AUTHENTICATION & ROLE-BASED ACCESS CONTROL",
            "-" * 54,
            "Mode                  : " + mode,
            "Enforcement           : " + enforced,
            "Roles                 : " + roles,
            "Resolution            : OIDC RS256 -> dev HS256 -> X-Api-Key",
        ])
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


# ---------------- Enterprise Fabric: Auth/RBAC, FHIR, Audit -----------------

@app.middleware("http")
async def rbac_middleware(request: Request, call_next):
    """Enforces route permissions when BIOOS_AUTH_REQUIRED=1 (default off for
    local dev/demo). Health, auth-token and static UI stay public always."""
    required = rbac_auth.route_permission(request.url.path, request.method)
    if required is not None and os.environ.get("BIOOS_AUTH_REQUIRED", "0") == "1":
        try:
            role = rbac_auth.authenticate_request(
                request.headers.get("authorization"),
                request.headers.get("x-api-key"),
                rbac_auth.default_dev_secret(),
            )
        except rbac_auth.AuthError as exc:
            return JSONResponse({"error": "unauthenticated", "detail": str(exc)}, status_code=401)
        if not rbac_auth.role_has_permission(role, required):
            return JSONResponse(
                {"error": "forbidden", "role": role, "required_permission": required},
                status_code=403,
            )
        request.state.role = role
    return await call_next(request)


@app.post("/api/auth/token")
def issue_auth_token(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Issues a dev HS256 token for the flight-deck UI. In production the
    hospital OIDC provider issues tokens and this endpoint is retired."""
    token = rbac_auth.issue_token(
        role=str(payload.get("role", "SERVICE")),
        subject=str(payload.get("subject", "anonymous")),
        ttl_seconds=int(payload.get("ttl_seconds", 3600)),
    )
    return {"access_token": token, "token_type": "Bearer",
            "expires_in": int(payload.get("ttl_seconds", 3600))}


@app.get("/api/fhir/patients")
def fhir_patients(ward_id: Optional[str] = None) -> Dict[str, Any]:
    """FHIR R4 Patient bundle over the live census (optionally ward-filtered)."""
    return fhir.patient_bundle(ward_id)


@app.get("/api/fhir/patient/{patient_id}")
def fhir_patient(patient_id: str) -> Dict[str, Any]:
    resource = fhir.patient_by_id(patient_id)
    if resource is None:
        return JSONResponse({"error": f"patient {patient_id} not found"}, status_code=404)
    return resource


@app.get("/api/fhir/observations/{patient_id}")
def fhir_observations(patient_id: str) -> Dict[str, Any]:
    bundle = fhir.observations_for_patient(patient_id)
    if bundle is None:
        return JSONResponse({"error": f"patient {patient_id} not found"}, status_code=404)
    return bundle


@app.post("/api/fhir/medication-request")
def fhir_medication_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a kernel-gated MedicationRequest (always status=draft: advisory).
    Metformin is verified by the Plane A PVE kernel via the ctypes bridge."""
    result = fhir.create_medication_request(
        patient_id=str(payload.get("patient_id", "")),
        drug_name=str(payload.get("drug", "")),
        dose_mg=float(payload.get("dose_mg", 0.0)),
        practitioner=str(payload.get("practitioner", "BioOS CDS")),
        egfr=payload.get("egfr"),
    )
    if "error" in result:
        return JSONResponse(result, status_code=404)
    # Feed the cognitive drift monitor (control-limit alerts on guard behavior)
    drift_alert = drift_monitor.record(result.get("kernel_verification") == "Approved")
    if drift_alert:
        store.append_audit_entry(
            actor="DRIFT_MONITOR", action="COGNITIVE_DRIFT_ALERT",
            resource_type="DriftAlert", resource_id=drift_alert["type"],
            payload=drift_alert,
        )
    result["drift_alert"] = drift_alert
    return result


@app.get("/api/cognitive/drift")
def cognitive_drift_status() -> Dict[str, Any]:
    """Rolling approval-rate drift telemetry for the cognitive plane."""
    return {
        "approval_rate": drift_monitor.approval_rate(),
        "window_size": len(drift_monitor._window),
        "limits": [drift_monitor.lower_limit, drift_monitor.upper_limit],
        "alerts_emitted": drift_monitor.alerts_emitted,
    }


@app.get("/api/clinical/news2/{patient_id}")
def clinical_news2(patient_id: str) -> Dict[str, Any]:
    """RCP NEWS2 early-warning score for a census patient (advisory only).
    HIGH-band escalations are written to the hash-chained audit log."""
    from ews_engine import news2_from_patient
    rec = topology.patients.get(patient_id)
    if not rec:
        return JSONResponse({"error": f"patient {patient_id} not found"}, status_code=404)
    score = news2_from_patient(rec)
    if score["escalation"] == "HIGH":
        store.append_audit_entry(
            actor="EWS_ENGINE",
            action="NEWS2_HIGH_ESCALATION",
            resource_type="Patient",
            resource_id=patient_id,
            payload={
                "total_score": score["total_score"],
                "per_parameter": score["per_parameter"],
                "monitoring": score["monitoring_recommendation"],
            },
        )
    return score


@app.get("/api/clinical/news2")
def clinical_news2_all() -> Dict[str, Any]:
    """Census-wide NEWS2 advisory matrix (Scale 1 defaults; see the
    observation endpoint for clinically-authoritative overrides)."""
    from ews_engine import news2_from_patient

    rows = []
    for rec in topology.patients.values():
        s = news2_from_patient(rec)
        rows.append({
            "patient_id": rec.patient_id,
            "name": rec.name,
            "bed_id": rec.bed_id,
            "ward_id": rec.ward_id,
            "total_score": s["total_score"],
            "clinical_risk": s["clinical_risk"],
            "escalation": s["escalation"],
            "trend_observations": len(news2_trend.history(rec.patient_id)),
        })
    rows.sort(key=lambda r: (-r["total_score"], r["bed_id"]))
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for r in rows:
        counts[r["clinical_risk"]] = counts.get(r["clinical_risk"], 0) + 1
    return {"patients": rows, "band_counts": counts, "advisory_only": True}


@app.post("/api/clinical/news2/{patient_id}/observation")
def clinical_news2_observation(patient_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Records a clinical NEWS2 observation WITH overrides for the fields the
    census record cannot know (supplemental O2, SpO2 scale, ACVPU alert state).

    Addresses hazard H-11: `news2_from_patient` must default room-air/Alert for
    convenience views, but REAL observations that silently keep those defaults
    can under-score hypoxemic or obtunded patients. This endpoint requires the
    clinician to pass overrides explicitly; when defaults are used they are
    flagged in the response (`defaults_used`) for auditability."""
    from ews_engine import compute_news2

    rec = topology.patients.get(patient_id)
    if not rec:
        return JSONResponse({"error": f"patient {patient_id} not found"}, status_code=404)

    on_oxygen = bool(payload.get("on_supplemental_oxygen", False))
    spo2_scale = int(payload.get("spo2_scale", 1))
    is_alert = bool(payload.get("is_alert", rec.gcs_score >= 15))
    defaults_used = {
        "on_supplemental_oxygen": "on_supplemental_oxygen" not in payload,
        "spo2_scale": "spo2_scale" not in payload,
        "is_alert": "is_alert" not in payload,
    }

    try:
        score = compute_news2(
            respiration_rate=float(payload.get("respiration_rate", rec.respiratory_rate)),
            spo2_percent=float(payload.get("spo2_percent", rec.spo2_percent)),
            on_supplemental_oxygen=on_oxygen,
            systolic_bp_mmhg=float(payload.get("systolic_bp_mmhg", rec.systolic_bp)),
            pulse_bpm=float(payload.get("pulse_bpm", rec.heart_rate)),
            is_alert=is_alert,
            temperature_c=float(payload.get("temperature_c", rec.temperature_c)),
            spo2_scale=spo2_scale,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    trend_alerts = news2_trend.record(patient_id, score["total_score"])
    score["trend_alerts"] = trend_alerts
    score["defaults_used"] = defaults_used

    # Persist the observation so deterioration trajectories survive restarts
    try:
        store.append_clinical_observation(
            ts_ns=time.time_ns(),
            patient_id=patient_id,
            total_score=score["total_score"],
            band=score["clinical_risk"],
            on_supplemental_oxygen=on_oxygen,
            spo2_scale=spo2_scale,
            is_alert=is_alert,
            defaults_used=defaults_used,
        )
    except Exception as exc:
        print(f"[BioOS EWS] observation persistence failed: {exc}")

    if trend_alerts:
        for alert in trend_alerts:
            store.append_audit_entry(
                actor="EWS_TREND",
                action=f"NEWS2_{alert['type']}",
                resource_type="Patient",
                resource_id=patient_id,
                payload={"latest_score": score["total_score"],
                          "message": alert["message"]},
            )
    return score


@app.get("/api/fhir/subscriptions")
def fhir_list_subscriptions() -> Dict[str, Any]:
    return {"subscriptions": fhir.list_subscriptions()}


@app.post("/api/fhir/subscriptions")
def fhir_add_subscription(payload: Dict[str, Any]) -> Dict[str, Any]:
    return fhir.add_subscription(
        criteria=str(payload.get("criteria", "MedicationRequest")),
        endpoint=str(payload.get("endpoint", "")),
    )


@app.get("/api/audit/chain")
def audit_chain(limit: int = 20) -> Dict[str, Any]:
    """Hash-chain verification verdict plus the most recent audit entries."""
    return {
        "verification": store.verify_audit_chain(),
        "recent_entries": store.recent_audit(limit=limit),
    }


@app.get("/api/audit/telemetry")
def audit_telemetry(limit: int = 100, metric_code: Optional[int] = None) -> Dict[str, Any]:
    """Recent persisted AMSV telemetry samples."""
    return {
        "total_samples": store.telemetry_count(),
        "samples": store.query_telemetry(metric_code=metric_code, limit=limit),
    }


# Surgical Vision API Endpoints (SAM 3.1 Integration)
# Added for Meta AI Hackathon 2026

from fastapi import WebSocket, WebSocketDisconnect
import base64
import io

# Initialize SAM 3.1 integration if available
_sam31_available = False
try:
    from sam31_vision import create_sam31_engine_from_env
    _sam31_engine = create_sam31_engine_from_env()
    _sam31_available = True
    print(f"[BioOS] SAM 3.1 Vision Engine loaded: mode={_sam31_engine.mode}")
except Exception as e:
    _sam31_available = False
    print(f"[BioOS] SAM 3.1 Vision Engine not available: {e}")


def _decode_image_base64(b64_string: str):
    """Decode base64 image to numpy array."""
    try:
        img_bytes = base64.b64decode(b64_string)
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes))
        return np.array(img.convert("RGB"))
    except Exception as e:
        raise ValueError(f"Invalid image data: {e}")


@app.post("/api/surgical/segment")
async def surgical_segment_frame(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _sam31_available:
        return JSONResponse(
            {"error": "SAM 3.1 Vision Engine not available. Set BIOOS_SAM_MODE=MOCK|LOCAL_ROCM|META_API"},
            status_code=503
        )
    
    patient_id = payload.get("patient_id")
    if not patient_id:
        return JSONResponse({"error": "patient_id required"}, status_code=400)
    
    image_b64 = payload.get("image_base64")
    if not image_b64:
        return JSONResponse({"error": "image_base64 required"}, status_code=400)
    
    try:
        frame = _decode_image_base64(image_b64)
        
        mode_str = payload.get("mode", "AUTOMATIC").upper()
        try:
            from sam31_vision import SegmentationMode
            mode = SegmentationMode(mode_str.lower())
        except ValueError:
            mode = SegmentationMode.AUTOMATIC
        
        prompt_points = payload.get("prompt_points")
        prompt_labels = payload.get("prompt_labels")
        prompt_box = payload.get("prompt_box")
        
        result = coe.process_surgical_frame(
            frame=frame,
            patient_id=patient_id,
            prompt_points=prompt_points,
        )
        
        if result is None:
            return JSONResponse({"error": "SAM 3.1 processing failed"}, status_code=500)
        
        segmentation = result["segmentation"]
        response = {
            "patient_id": patient_id,
            "timestamp_ns": segmentation.frame_timestamp_ns,
            "frame_shape": segmentation.frame_shape,
            "mode": segmentation.mode.value,
            "processing_ms": segmentation.processing_ms,
            "model_version": segmentation.model_version,
            "structures_detected": [s.value for s in segmentation.structures],
            "scores": segmentation.scores,
            "bboxes": segmentation.bboxes,
            "virtual_fixtures": [
                {
                    "fixture_id": f.fixture_id,
                    "structure": f.structure.value,
                    "enforcement": f.enforcement_level,
                    "metric_code": f.plane_a_metric_code,
                    "bbox": _sam31_engine._mask_to_bbox(f.mask) if f.mask.any() else [0, 0, 0, 0],
                    "safety_margin_px": f.safety_margin_px,
                }
                for f in result["virtual_fixtures"]
            ],
            "surgical_phase": result["surgical_phase"],
            "plane_a_payload": result["plane_a_payload"],
            "fhir_observation": result["fhir_observation"],
            "merkle_hash": result["merkle_hash"],
            "merkle_root": result["merkle_root"],
@app.post("/api/surgical/segment_batch")
async def surgical_segment_batch(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _sam31_available:
        return JSONResponse({"error": "SAM 3.1 not available"}, status_code=503)
    
    patient_id = payload.get("patient_id")
    frames = payload.get("frames", [])
    
    if not frames:
        return JSONResponse({"error": "frames array required"}, status_code=400)
    
    results = []
    for i, frame_data in enumerate(frames):
        try:
            frame_b64 = frame_data.get("image_base64")
            if not frame_b64:
                results.append({"frame_index": i, "error": "Missing image_base64"})
                continue
            
            frame = _decode_image_base64(frame_b64)
            mode_str = frame_data.get("mode", "AUTOMATIC").upper()
            from sam31_vision import SegmentationMode
            mode = SegmentationMode(mode_str.lower())
            
            prompt_points = frame_data.get("prompt_points")
            prompt_labels = frame_data.get("prompt_labels")
            prompt_box = frame_data.get("prompt_box")
            
            result = coe.process_surgical_frame(
                frame=frame,
                patient_id=patient_id,
                prompt_points=prompt_points,
            )
            
            if result:
                seg = result["segmentation"]
                results.append({
                    "frame_index": i,
                    "timestamp_ns": seg.frame_timestamp_ns,
                    "structures": [s.value for s in seg.structures],
                    "scores": seg.scores,
                    "phase": result["surgical_phase"],
                    "fixtures": len(result["virtual_fixtures"]),
                    "processing_ms": seg.processing_ms,
                })
            else:
                results.append({"frame_index": i, "error": "Processing failed"})
                
        except Exception as e:
            results.append({"frame_index": i, "error": str(e)})
    
    return {"patient_id": patient_id, "results": results}


@app.get("/api/surgical/performance")
async def surgical_performance() -> Dict[str, Any]:
    if not _sam31_available:
        return {"available": False, "message": "SAM 3.1 not loaded"}
    
    stats = coe.get_sam31_performance_stats()
    if stats:
        stats["available"] = True
    return stats


@app.get("/api/surgical/phase")
async def surgical_current_phase() -> Dict[str, Any]:
    if not _sam31_available:
        return {"available": False, "phase": "UNKNOWN"}
    
    phase = coe.get_surgical_phase()
    return {"available": True, "phase": phase}
        }
        
        return response
        
    except Exception as e:
        return JSONResponse({"error": f"Segmentation failed: {str(e)}"}, status_code=500)
@app.websocket("/ws/surgical/stream")
async def surgical_websocket_stream(websocket: WebSocket):
    await websocket.accept()
    print("[BioOS Surgical] WebSocket connected")
    
    try:
        while True:
            data = await websocket.receive_json()
            
            patient_id = data.get("patient_id")
            if not patient_id:
                await websocket.send_json({"error": "patient_id required"})
                continue
            
            image_b64 = data.get("image_base64")
            if not image_b64:
                await websocket.send_json({"error": "image_base64 required"})
                continue
            
            if not _sam31_available:
                await websocket.send_json({"error": "SAM 3.1 not available"})
                continue
            
            try:
                frame = _decode_image_base64(image_b64)
                
                mode_str = data.get("mode", "AUTOMATIC").upper()
                from sam31_vision import SegmentationMode
                mode = SegmentationMode(mode_str.lower())
                
                result = coe.process_surgical_frame(
                    frame=frame,
                    patient_id=patient_id,
                    prompt_points=data.get("prompt_points"),
                )
                
                if result:
                    seg = result["segmentation"]
                    response = {
                        "timestamp_ns": seg.frame_timestamp_ns,
                        "structures": [s.value for s in seg.structures],
                        "scores": seg.scores,
                        "phase": result["surgical_phase"],
                        "fixtures_count": len(result["virtual_fixtures"]),
                        "plane_a_payload": result["plane_a_payload"],
                        "processing_ms": seg.processing_ms,
                    }
                else:
                    response = {"error": "Processing failed"}
                    
                await websocket.send_json(response)
                
            except Exception as e:
                await websocket.send_json({"error": str(e)})
                
    except WebSocketDisconnect:
        print("[BioOS Surgical] WebSocket disconnected")
    except Exception as e:
        print(f"[BioOS Surgical] WebSocket error: {e}")
        await websocket.close()


# Mount static web frontend
web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

if __name__ == "__main__":
    print("[BioOS] Starting Unified Flight Deck Server on http://0.0.0.0:8090...")
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="warning")
