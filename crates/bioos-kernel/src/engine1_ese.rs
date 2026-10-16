//! Engine 1: Environmental & Sensor Engine (ESE)
//!
//! Standards: CLSI C56-A, ASTM F2761, ISO/IEEE 11073 SDC
//! Hard real-time sensor ingestion, artifact gating, and physical line monitoring.

use crate::amsv::quality_flags;

pub const HEMOLYSIS_THRESHOLD_INDEX: u16 = 20; // 20 mg/dL free hemoglobin
pub const MAX_OCCLUSION_PRESSURE_MMHG: u32 = 525; // 10.2 psi
pub const AIR_BUBBLE_MAX_UL: u32 = 25; // 25 uL bubble limit

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SensorStatus {
    Nominal,
    SoftWarning,
    TripOcclusion,
    TripAirBubble,
    HemolysisVoid,
}

#[derive(Debug, Clone, Copy)]
pub struct PotassiumValidationResult {
    pub value_mmol_l: f32,
    pub quality_flags: u32,
    pub status: SensorStatus,
    pub error_description: Option<&'static str>,
}

pub struct EnvironmentalSensorEngine;

impl EnvironmentalSensorEngine {
    /// Validates serum potassium against CLSI C56-A Hemolysis index.
    /// If H > 20 mg/dL, potassium is strictly VOID (NaN) to prevent fatal pseudohyperkalemic treatment.
    pub fn validate_potassium(
        raw_k_mmol_l: f32,
        hemolysis_index: u16,
    ) -> PotassiumValidationResult {
        if hemolysis_index > HEMOLYSIS_THRESHOLD_INDEX {
            PotassiumValidationResult {
                value_mmol_l: f32::NAN,
                quality_flags: quality_flags::HEMOLYSIS_REJECTED,
                status: SensorStatus::HemolysisVoid,
                error_description: Some("CLSI C56-A: Hemolysis index > 20 mg/dL. Potassium reading void due to pseudohyperkalemia hazard."),
            }
        } else {
            let mut flags = quality_flags::VALID | quality_flags::CALIBRATED;
            if raw_k_mmol_l < 3.5 || raw_k_mmol_l > 5.2 {
                flags |= quality_flags::NOISY_WARNING;
            }
            PotassiumValidationResult {
                value_mmol_l: raw_k_mmol_l,
                quality_flags: flags,
                status: SensorStatus::Nominal,
                error_description: None,
            }
        }
    }

    /// Evaluates infusion pump line telemetry for mechanical trips
    pub fn evaluate_pump_telemetry(pressure_mmhg: u32, bubble_size_ul: u32) -> (SensorStatus, u32) {
        let mut flags = quality_flags::VALID;

        if bubble_size_ul >= AIR_BUBBLE_MAX_UL {
            flags |= quality_flags::AIR_BUBBLE_DETECTED;
            return (SensorStatus::TripAirBubble, flags);
        }

        if pressure_mmhg >= MAX_OCCLUSION_PRESSURE_MMHG {
            flags |= quality_flags::OCCLUSION_DETECTED;
            return (SensorStatus::TripOcclusion, flags);
        }

        if pressure_mmhg > 413 {
            // > 8.0 psi soft warning
            flags |= quality_flags::NOISY_WARNING;
            return (SensorStatus::SoftWarning, flags);
        }

        (SensorStatus::Nominal, flags)
    }

    /// Applies Lower Limit of Quantitation (LLoQ) left-censoring
    pub fn apply_lloq_censoring(value: f32, lloq_threshold: f32) -> (f32, u32) {
        if value < lloq_threshold {
            (0.0, quality_flags::CENSORED_LLOR | quality_flags::VALID)
        } else {
            (value, quality_flags::VALID | quality_flags::CALIBRATED)
        }
    }
}
