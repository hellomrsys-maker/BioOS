//! C-ABI Foreign Function Interface (FFI) for BioOS
//!
//! Exposes zero-overhead, zero-copy native symbols for physical memory sharing
//! between the Rust #![no_std] safety kernel and Python/C/Julia layers.

use crate::amsv::{
    AtomicMemoryStateVector, PhysiologicalEnvelopeVector, SeqlockAmsv, TriPlaneAmsv,
};
use crate::engine1_ese::{EnvironmentalSensorEngine, SensorStatus};
use crate::engine2_bpe::{BiometricPharmacokineticEngine, PatientBiometrics, Sex};
use crate::engine3_pve::{DrugIdentifier, PharmacologicalVerificationEngine, VerificationOutcome};
use crate::engine4_wie::HardwareWatchdogEngine;
use crate::engine_envelope::PhysiologicalEnvelopeEngine;

static GLOBAL_AMSV: SeqlockAmsv = SeqlockAmsv::new();
static mut GLOBAL_WATCHDOG: HardwareWatchdogEngine = HardwareWatchdogEngine::new();
static mut GLOBAL_ENVELOPE: PhysiologicalEnvelopeEngine = PhysiologicalEnvelopeEngine::new();
static mut GLOBAL_TRIPLANE: TriPlaneAmsv = TriPlaneAmsv {
    plane_a: AtomicMemoryStateVector {
        seq_ctr: 0,
        t_write_ns: 0,
        device_class: 1,
        metric_code: 0,
        value_x1000: 0,
        quality_flags: 1,
        hil_h: 0,
        hil_i: 0,
        hil_l: 0,
        limit_state: 0,
        rate_setpoint_x10: 1250,
        rate_actual_x10: 1250,
        occlusion_mmhg: 180,
        alarm_class: 0,
        crc16: 0,
        global_mode: 0,
        active_escalation_tier: 0,
        facility_census_bitmap: 0,
        hics_incident_id: 0,
        system_checksum: 0,
    },
    plane_c: PhysiologicalEnvelopeVector {
        env_seq_ctr: 0,
        est_map_x10: 800,
        est_hr_x10: 750,
        shock_index_x100: 62,
        d_map_dt_x100: 0,
        alpha_floor_state: 0,
        slew_clamped: 0,
        permissible_rate_x10: 1250,
        dynamic_margin_x100: 1000,
        kalman_variance_p00_x100: 100,
        kalman_variance_p11_x100: 100,
        reserved: [0; 22],
        env_crc16: 0,
        env_checksum: 0,
    },
};

/// Returns raw pointer to the exact physical 64-byte AMSV memory location
#[no_mangle]
pub extern "C" fn bioos_amsv_get_raw_ptr() -> *mut AtomicMemoryStateVector {
    GLOBAL_AMSV.read(); // ensure initialized
    &GLOBAL_AMSV as *const _ as *mut AtomicMemoryStateVector
}

/// Returns raw pointer to the complete 128-byte Tri-Plane Dual-Cache-Line Vector
#[no_mangle]
pub extern "C" fn bioos_triplane_get_raw_ptr() -> *mut TriPlaneAmsv {
    // addr_of_mut! is safe: it only forms a raw pointer, no dereference occurs.
    core::ptr::addr_of_mut!(GLOBAL_TRIPLANE)
}

/// Executes one cycle of Engine 2: Dynamic Physiological Envelope & Kalman Observer.
///
/// # Safety
///
/// - `out_alpha_state`, if non-null, must be valid for writes of one `u8`.
/// - `out_allowed_rate`, if non-null, must be valid for writes of one `f32`.
/// - Exported C-ABI: C/ctypes callers are outside Rust's safety model.
#[no_mangle]
pub unsafe extern "C" fn bioos_envelope_step(
    raw_map_mmhg: f32,
    raw_hr_bpm: f32,
    raw_sbp_mmhg: f32,
    requested_rate_ml_h: f32,
    dt_seconds: f32,
    out_alpha_state: *mut u8,
    out_allowed_rate: *mut f32,
) -> f32 {
    let est = {
        let env_ref = &mut *core::ptr::addr_of_mut!(GLOBAL_ENVELOPE);
        env_ref.evaluate_envelope(
            raw_map_mmhg,
            raw_hr_bpm,
            raw_sbp_mmhg,
            requested_rate_ml_h,
            dt_seconds,
        )
    };

    if !out_alpha_state.is_null() {
        *out_alpha_state = est.alpha_floor_state as u8;
    }
    if !out_allowed_rate.is_null() {
        *out_allowed_rate = est.permissible_rate_ceiling;
    }

    // Update Tri-Plane Cache Line 1 directly
    {
        let tri = &mut *core::ptr::addr_of_mut!(GLOBAL_TRIPLANE);
        tri.plane_c.env_seq_ctr = tri.plane_c.env_seq_ctr.wrapping_add(2);
        tri.plane_c.est_map_x10 = (est.estimated_map_mmhg * 10.0) as u16;
        tri.plane_c.est_hr_x10 = (est.estimated_hr_bpm * 10.0) as u16;
        tri.plane_c.shock_index_x100 = (est.shock_index * 100.0) as u16;
        tri.plane_c.d_map_dt_x100 = (est.d_map_dt * 100.0) as i16;
        tri.plane_c.alpha_floor_state = est.alpha_floor_state as u8;
        tri.plane_c.permissible_rate_x10 = (est.permissible_rate_ceiling * 10.0) as u32;
    }

    est.estimated_map_mmhg
}

/// Executes a 1000 Hz microkernel cycle directly over shared memory
#[no_mangle]
pub extern "C" fn bioos_kernel_step(
    current_time_ns: u64,
    plane_b_heartbeat_ns: u64,
    pressure_mmhg: u32,
    bubble_ul: u32,
    h_index: u16,
    k_mmol_l: f32,
) -> u8 {
    // 1. Evaluate ESE telemetry
    let (sensor_status, quality) =
        EnvironmentalSensorEngine::evaluate_pump_telemetry(pressure_mmhg, bubble_ul);
    let k_result = EnvironmentalSensorEngine::validate_potassium(k_mmol_l, h_index);

    let has_occlusion = sensor_status == SensorStatus::TripOcclusion;
    let has_bubble = sensor_status == SensorStatus::TripAirBubble;
    let is_warning = sensor_status == SensorStatus::SoftWarning;

    // 2. Evaluate WIE watchdog
    // Rust 2024 static_mut_refs: call through a raw pointer derived from
    // addr_of_mut! instead of implicitly taking &mut to the mutable static.
    let trip_report = unsafe {
        (*core::ptr::addr_of_mut!(GLOBAL_WATCHDOG)).evaluate_cycle(
            current_time_ns,
            plane_b_heartbeat_ns,
            has_occlusion,
            has_bubble,
            false,
            is_warning,
        )
    };

    // 3. Update AMSV with atomic Seqlock
    GLOBAL_AMSV.write(|v| {
        // AMSV ABI keeps a 32-bit telemetry timestamp (layout frozen at 64 B).
        // The authoritative timing path is the u64 FFI arguments above; this
        // field is a low-precision display/telemetry stamp only.
        v.t_write_ns = current_time_ns as u32;
        v.occlusion_mmhg = pressure_mmhg;
        v.quality_flags = quality | k_result.quality_flags;
        v.hil_h = h_index;
        v.value_x1000 = if k_result.value_mmol_l.is_nan() {
            -1 // Sentinel for NaN / VOID
        } else {
            (k_result.value_mmol_l * 1000.0) as i32
        };
        v.limit_state = trip_report.current_state as u16;

        if trip_report.current_state == crate::engine4_wie::WatchdogState::HardwareLockout {
            v.rate_actual_x10 = 0; // Motor power cut
            v.alarm_class = crate::amsv::AlarmClass::HardwareTripEmergency as u16;
        }
    });

    trip_report.current_state as u8
}

/// Atomically reads the current 64-byte AMSV into `dest`.
///
/// # Safety
///
/// `dest`, if non-null, must be valid for writes of one
/// `AtomicMemoryStateVector` (64 bytes, 64-byte aligned).
#[no_mangle]
pub unsafe extern "C" fn bioos_amsv_read_atomic(dest: *mut AtomicMemoryStateVector) {
    if !dest.is_null() {
        let snapshot = GLOBAL_AMSV.read();
        *dest = snapshot;
    }
}

/// CLSI C56-A potassium validation across the C boundary.
///
/// # Safety
///
/// `out_void`, if non-null, must be valid for writes of one `u8`.
#[no_mangle]
pub unsafe extern "C" fn bioos_validate_potassium(
    raw_k: f32,
    h_index: u16,
    out_void: *mut u8,
) -> f32 {
    let res = EnvironmentalSensorEngine::validate_potassium(raw_k, h_index);
    if !out_void.is_null() {
        *out_void = if res.status == SensorStatus::HemolysisVoid {
            1
        } else {
            0
        };
    }
    res.value_mmol_l
}

/// 2021 CKD-EPI race-free eGFR C-ABI function
#[no_mangle]
pub extern "C" fn bioos_calculate_ckd_epi(age: f32, scr: f32, is_female: bool) -> f32 {
    let bio = PatientBiometrics {
        age_years: age,
        sex: if is_female { Sex::Female } else { Sex::Male },
        height_cm: 175.0,
        weight_kg: 75.0,
        serum_creatinine_mg_dl: scr,
    };
    BiometricPharmacokineticEngine::calculate_ckd_epi_2021(&bio)
}

/// Metformin NTI verification C-ABI function
#[no_mangle]
pub extern "C" fn bioos_verify_metformin(egfr: f32, requested_dose_mg: f32) -> u8 {
    let report = PharmacologicalVerificationEngine::verify_nti_order(
        DrugIdentifier::Metformin,
        requested_dose_mg,
        egfr,
        egfr, // proxy
        4.2,
    );
    match report.outcome {
        VerificationOutcome::Approved => 0,
        VerificationOutcome::DoseClamped => 1,
        VerificationOutcome::HardLockoutContraindicated => 2,
        VerificationOutcome::RequiresClinicalOverride => 3,
    }
}
