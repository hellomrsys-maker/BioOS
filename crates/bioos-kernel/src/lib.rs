//! BioOS Real-Time Medical Safety Kernel (Plane A)
//!
//! Standards Compliance:
//! - IEC 62304 Class C (Medical Device Software - Death or Serious Injury Prevention)
//! - ASTM F2761 Integrated Clinical Environment (ICE)
//! - ISO/IEEE 11073 Service-Oriented Device Connectivity (SDC)
//! - CLSI C56-A Hemolysis, Icterus, and Lipemia Interference
//!
//! Architecture: Dual-Plane Asymmetric Isolation (Plane A Hard Safety Kernel)

#![cfg_attr(not(feature = "std"), no_std)]

pub mod amsv;
pub mod engine1_ese;
pub mod engine2_bpe;
pub mod engine3_pve;
pub mod engine4_wie;
pub mod engine_envelope;
pub mod ffi;
pub mod scheduler;
pub mod ipc;
pub mod mm;
pub mod hal;
pub mod drivers;

pub use amsv::{
    quality_flags, AlarmClass, AtomicMemoryStateVector, DeviceClass, GlobalOperatingMode,
    PhysiologicalEnvelopeVector, SeqlockAmsv, TriPlaneAmsv,
};
pub use engine1_ese::{
    EnvironmentalSensorEngine, PotassiumValidationResult, SensorStatus, AIR_BUBBLE_MAX_UL,
    HEMOLYSIS_THRESHOLD_INDEX, MAX_OCCLUSION_PRESSURE_MMHG,
};
pub use engine2_bpe::{
    BiometricPharmacokineticEngine, ChildPughClass, PatientBiometrics, Sex,
};
pub use engine3_pve::{
    DosingVerificationReport, DrugIdentifier, PharmacologicalVerificationEngine,
    TisdaleScoreInput, VerificationOutcome,
};
pub use engine4_wie::{
    HardwareWatchdogEngine, RelayAction, WatchdogState, WatchdogTripReport,
    HEARTBEAT_TIMEOUT_NS, MECHANICAL_RELAY_LATENCY_MS, SSR_TRIP_LATENCY_MS,
};
pub use engine_envelope::{
    AlphaFloorState, KalmanStateEstimate, PhysiologicalEnvelopeEngine, PhysiologicalKalmanFilter,
};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_amsv_struct_layout_and_size() {
        assert_eq!(core::mem::size_of::<AtomicMemoryStateVector>(), 64);
        assert_eq!(core::mem::align_of::<AtomicMemoryStateVector>(), 64);

        let seqlock = SeqlockAmsv::new();
        seqlock.write(|v| {
            v.rate_setpoint_x10 = 1250; // 125.0 mL/h
            v.occlusion_mmhg = 180;
            v.global_mode = GlobalOperatingMode::Surge as u8;
        });

        let snapshot = seqlock.read();
        assert_eq!(snapshot.rate_setpoint_x10, 1250);
        assert_eq!(snapshot.occlusion_mmhg, 180);
        assert_eq!(snapshot.global_mode, GlobalOperatingMode::Surge as u8);
        assert!(snapshot.is_valid());
    }

    #[test]
    fn test_clsi_c56a_potassium_hemolysis_gate() {
        // Valid potassium reading (H index <= 20)
        let valid = EnvironmentalSensorEngine::validate_potassium(4.2, 12);
        assert_eq!(valid.status, SensorStatus::Nominal);
        assert!(!valid.value_mmol_l.is_nan());
        assert_eq!(valid.value_mmol_l, 4.2);

        // Hemolyzed sample (H index > 20) MUST be VOID to prevent fatal pseudohyperkalemic cardiac arrest
        let hemolyzed = EnvironmentalSensorEngine::validate_potassium(6.8, 28);
        assert_eq!(hemolyzed.status, SensorStatus::HemolysisVoid);
        assert!(hemolyzed.value_mmol_l.is_nan());
        assert_eq!(
            hemolyzed.quality_flags & quality_flags::HEMOLYSIS_REJECTED,
            quality_flags::HEMOLYSIS_REJECTED
        );
    }

    #[test]
    fn test_pump_occlusion_and_air_bubble_trips() {
        // Occlusion pressure above 10.2 psi (525 mmHg)
        let (status_occ, flags_occ) = EnvironmentalSensorEngine::evaluate_pump_telemetry(530, 5);
        assert_eq!(status_occ, SensorStatus::TripOcclusion);
        assert_eq!(flags_occ & quality_flags::OCCLUSION_DETECTED, quality_flags::OCCLUSION_DETECTED);

        // Bubble >= 25 uL
        let (status_bubble, flags_bubble) = EnvironmentalSensorEngine::evaluate_pump_telemetry(120, 26);
        assert_eq!(status_bubble, SensorStatus::TripAirBubble);
        assert_eq!(flags_bubble & quality_flags::AIR_BUBBLE_DETECTED, quality_flags::AIR_BUBBLE_DETECTED);
    }

    #[test]
    fn test_ckd_epi_and_cockcroft_gault() {
        let bio = PatientBiometrics {
            age_years: 65.0,
            sex: Sex::Male,
            height_cm: 175.0,
            weight_kg: 85.0, // Overweight, should select ABW
            serum_creatinine_mg_dl: 1.2,
        };

        let egfr = BiometricPharmacokineticEngine::calculate_ckd_epi_2021(&bio);
        assert!(egfr > 55.0 && egfr < 75.0, "eGFR out of expected range: {}", egfr);

        let crcl = BiometricPharmacokineticEngine::calculate_cockcroft_gault(&bio);
        assert!(crcl > 50.0 && crcl < 80.0, "CrCl out of expected range: {}", crcl);
    }

    #[test]
    fn test_metformin_hard_lockout_at_low_egfr() {
        // eGFR < 30 mL/min/1.73m2 -> Absolute contraindication
        let report = PharmacologicalVerificationEngine::verify_nti_order(
            DrugIdentifier::Metformin,
            1000.0,
            24.5, // eGFR < 30
            28.0,
            4.0,
        );

        assert_eq!(report.outcome, VerificationOutcome::HardLockoutContraindicated);
        assert_eq!(report.sanctioned_ceiling_dose, 0.0);
        assert!(report.lockout_reason.is_some());
    }

    #[test]
    fn test_tisdale_qtc_risk_lockout() {
        let input = TisdaleScoreInput {
            age_gte_68: true,                     // 1 pt
            female_sex: true,                     // 1 pt
            loop_diuretic: true,                  // 1 pt
            serum_k_lte_3_5: true,                // 2 pts
            baseline_qtc_gte_450: true,           // 2 pts
            acute_myocardial_infarction: false,
            sepsis: true,                         // 3 pts
            heart_failure: false,
            qtc_prolonging_drugs_count: 2,        // 6 pts -> Total = 16 points (> 11)
        };

        let (score, text) = PharmacologicalVerificationEngine::calculate_tisdale_score(&input);
        assert_eq!(score, 16);
        assert!(text.contains("HARD LOCKOUT"));
    }

    #[test]
    fn test_wie_watchdog_relay_trip_and_heartbeat_timeout() {
        let mut wie = HardwareWatchdogEngine::new();

        // Nominal cycle
        let nominal = wie.evaluate_cycle(10_000_000, 10_000_000, false, false, false, false);
        assert_eq!(nominal.current_state, WatchdogState::Normal);
        assert_eq!(nominal.relay_action, RelayAction::MaintainPower);

        // Heartbeat timeout (> 50 ms elapsed)
        let timeout_report = wie.evaluate_cycle(75_000_000, 10_000_000, false, false, false, false);
        assert_eq!(timeout_report.current_state, WatchdogState::HardwareLockout);
        assert_eq!(timeout_report.relay_action, RelayAction::TripBothRelaysMechanicalAirGap);
        assert_eq!(timeout_report.ssr_trip_time_ms, SSR_TRIP_LATENCY_MS);
        assert_eq!(timeout_report.mechanical_trip_time_ms, MECHANICAL_RELAY_LATENCY_MS);
    }

    #[test]
    fn test_triplane_dual_cacheline_layout() {
        assert_eq!(core::mem::size_of::<TriPlaneAmsv>(), 128);
        assert_eq!(core::mem::align_of::<TriPlaneAmsv>(), 64);
        assert_eq!(core::mem::size_of::<PhysiologicalEnvelopeVector>(), 64);
        assert_eq!(core::mem::align_of::<PhysiologicalEnvelopeVector>(), 64);
    }

    #[test]
    fn test_kalman_envelope_and_alpha_floor() {
        let mut envelope = PhysiologicalEnvelopeEngine::new();

        // 1. Nominal step (MAP = 80 mmHg)
        let nominal = envelope.evaluate_envelope(80.0, 75.0, 115.0, 125.0, 0.1);
        assert_eq!(nominal.alpha_floor_state, AlphaFloorState::Nominal);
        assert!(nominal.estimated_map_mmhg > 70.0);

        // 2. Hemodynamic crash (MAP plunges to 45 mmHg)
        let stall = envelope.evaluate_envelope(45.0, 130.0, 60.0, 125.0, 0.1);
        assert_eq!(stall.alpha_floor_state, AlphaFloorState::HemodynamicStallEmergency);
        assert_eq!(stall.permissible_rate_ceiling, 0.0); // Hard clamp to 0
    }

    #[test]
    fn test_realtime_scheduler_edf_dispatch() {
        use crate::scheduler::{RealTimeScheduler, TaskPriority};
        let mut sched = RealTimeScheduler::new();

        // Register 1000 Hz critical actuator task
        assert!(sched.register_task(0, 1, "ACTUATOR_1KHZ", TaskPriority::Critical1000Hz, 1_000_000, 1_000_000));
        // Register 100 Hz Kalman envelope task
        assert!(sched.register_task(1, 2, "ENVELOPE_100HZ", TaskPriority::Envelope100Hz, 10_000_000, 10_000_000));

        // Initial cycle at t = 1_000_000 ns -> Highest priority task (ACTUATOR_1KHZ) must dispatch
        let next = sched.schedule_next(1_000_000);
        assert_eq!(next, Some(1));

        // Second cycle -> Envelope task dispatches
        let next2 = sched.schedule_next(10_000_000);
        assert_eq!(next2, Some(1)); // Actuator 1000Hz is due again and higher priority
    }

    #[test]
    fn test_spsc_ring_buffer_wait_free_ipc() {
        use crate::ipc::{SpscRingBuffer, IpcMessage};
        let mut ring = SpscRingBuffer::new();
        assert!(ring.is_empty());

        let msg = IpcMessage {
            msg_type: 0x01,
            source_engine: 1,
            target_engine: 2,
            payload_u64: 0xDEADBEEF,
            timestamp_ns: 123456789,
        };

        assert!(ring.push(msg));
        assert_eq!(ring.len(), 1);

        let popped = ring.pop().expect("Should dequeue valid msg");
        assert_eq!(popped.payload_u64, 0xDEADBEEF);
        assert!(ring.is_empty());
    }

    #[test]
    fn test_static_slab_pool_o1_alloc_free() {
        use crate::mm::StaticSlabPool;
        let mut pool = StaticSlabPool::new();
        assert_eq!(pool.allocated_count, 0);

        let b1 = pool.alloc().expect("Block 1 allocation");
        let b2 = pool.alloc().expect("Block 2 allocation");
        assert_eq!(pool.allocated_count, 2);

        // Free b1 and re-allocate
        assert!(pool.free(b1));
        assert_eq!(pool.allocated_count, 1);
        let b3 = pool.alloc().expect("Block 3 allocation");
        assert_eq!(b3, b1); // Reuses freed slot 0
    }

    #[test]
    fn test_hal_medical_bus_and_fault_injection() {
        use crate::hal::{MedicalBusController, BusType, BusStatus, CanFrame};
        let mut bus = MedicalBusController::new(BusType::CanBusMedical, 500_000);
        assert_eq!(bus.status, BusStatus::Online);

        let frame = CanFrame { can_id: 0x120, dlc: 8, data: [0; 8], timestamp_us: 100 };
        assert!(bus.transmit_frame(&frame));
        assert_eq!(bus.tx_frames_count, 1);

        // Inject hardware bus fault
        bus.inject_fault(true);
        assert_eq!(bus.status, BusStatus::BusOffError);
        assert!(!bus.transmit_frame(&frame)); // Fails
        assert_eq!(bus.bus_error_count, 1);

        bus.inject_fault(false);
        assert_eq!(bus.status, BusStatus::Online);
        assert!(bus.transmit_frame(&frame)); // Recovers
    }

    #[test]
    fn test_medical_device_drivers_ders_and_alarms() {
        use crate::drivers::infusion_pump::InfusionPumpDriver;
        use crate::drivers::ventilator::MechanicalVentilatorDriver;
        use crate::drivers::patient_monitor::PatientMonitorDriver;
        use crate::drivers::analyzer::LabAnalyzerDriver;

        // 1. Infusion Pump DERS Hard Clamp
        let mut pump = InfusionPumpDriver::new(101, 200.0, 300);
        let rate = pump.set_rate(999.0).expect("Clamp expected");
        assert_eq!(rate, 200.0); // Hard limit enforced
        assert!(!pump.update_telemetry(350, false)); // Over-pressure trip
        assert_eq!(pump.active_rate_ml_h, 0.0);

        // 2. Mechanical Ventilator Barotrauma Alarm
        let mut vent = MechanicalVentilatorDriver::new(201);
        assert!(vent.update_vitals(22.0, 5.0, 21.0, 14));
        assert!(!vent.update_vitals(45.0, 5.0, 21.0, 14)); // Barotrauma alarm >= 40
        assert!(vent.high_pressure_alarm);

        // 3. Patient Monitor MAP Formula
        let mut monitor = PatientMonitorDriver::new(301);
        monitor.update_hemodynamics(80, 120, 80, 99.0);
        assert_eq!(monitor.mean_arterial_pressure_mmhg, 93);

        // 4. Lab Analyzer CLSI C56-A Hemolysis Gate
        let mut analyzer = LabAnalyzerDriver::new(401);
        let valid_k = analyzer.process_potassium_assay(4.5, 12);
        assert_eq!(valid_k, Some(4.5));
        let rejected_k = analyzer.process_potassium_assay(6.8, 45); // H > 20
        assert_eq!(rejected_k, None); // Invalidated
        assert!(analyzer.is_specimen_rejected);
    }
}

