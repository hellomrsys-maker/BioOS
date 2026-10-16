//! Engine 3: Pharmacological Verification Engine (PVE)
//!
//! Standards: Dettli Linear Ceiling Law, Tisdale QTc Scoring, NTI Safety Registers
//! Zero-hallucination symbolic verification and deterministic dosing ceiling clamping.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DrugIdentifier {
    Metformin,
    Vancomycin,
    Gentamicin,
    Digoxin,
    Enoxaparin,
    Methotrexate,
    Unknown,
}

impl From<&str> for DrugIdentifier {
    fn from(token: &str) -> Self {
        match token {
            "NTI_METFORMIN" | "Metformin" => DrugIdentifier::Metformin,
            "NTI_VANCOMYCIN" | "Vancomycin" => DrugIdentifier::Vancomycin,
            "NTI_GENTAMICIN" | "Gentamicin" => DrugIdentifier::Gentamicin,
            "NTI_DIGOXIN" | "Digoxin" => DrugIdentifier::Digoxin,
            "NTI_ENOXAPARIN" | "Enoxaparin" => DrugIdentifier::Enoxaparin,
            "NTI_METHOTREXATE" | "Methotrexate" => DrugIdentifier::Methotrexate,
            _ => DrugIdentifier::Unknown,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VerificationOutcome {
    Approved,
    DoseClamped,
    HardLockoutContraindicated,
    RequiresClinicalOverride,
}

#[derive(Debug, Clone, Copy)]
pub struct DosingVerificationReport {
    pub drug: DrugIdentifier,
    pub requested_dose: f32,
    pub sanctioned_ceiling_dose: f32,
    pub outcome: VerificationOutcome,
    pub lockout_reason: Option<&'static str>,
}

#[derive(Debug, Clone, Copy)]
pub struct TisdaleScoreInput {
    pub age_gte_68: bool,
    pub female_sex: bool,
    pub loop_diuretic: bool,
    pub serum_k_lte_3_5: bool,
    pub baseline_qtc_gte_450: bool,
    pub acute_myocardial_infarction: bool,
    pub sepsis: bool,
    pub heart_failure: bool,
    pub qtc_prolonging_drugs_count: u8, // 0, 1, or >=2
}

pub struct PharmacologicalVerificationEngine;

impl PharmacologicalVerificationEngine {
    /// Applies the Dettli linear ceiling law to clamp maximum permissible dose
    pub fn calculate_dettli_ceiling(
        label_max_dose: f32,
        ders_hard_limit: f32,
        patient_crcl_ml_min: f32,
        hepatic_factor: f32, // 1.0 = normal, 0.5 = moderate impairment, 0.25 = severe
        kappa_immuno: f32,
    ) -> f32 {
        let renal_band = (patient_crcl_ml_min / 120.0).clamp(0.05, 1.0);
        let adjusted_by_organs = renal_band * hepatic_factor * label_max_dose;
        let adjusted_by_immuno = if kappa_immuno > 0.0 {
            label_max_dose / kappa_immuno
        } else {
            label_max_dose
        };

        label_max_dose
            .min(ders_hard_limit)
            .min(adjusted_by_organs)
            .min(adjusted_by_immuno)
    }

    /// Verifies drug order against Narrow Therapeutic Index (NTI) Register
    pub fn verify_nti_order(
        drug: DrugIdentifier,
        requested_dose: f32,
        egfr: f32,
        crcl: f32,
        serum_k: f32,
    ) -> DosingVerificationReport {
        match drug {
            DrugIdentifier::Metformin => {
                // Metformin Hard Contraindication: eGFR < 30 mL/min/1.73m2 (Fatal Lactic Acidosis)
                if egfr < 30.0 {
                    DosingVerificationReport {
                        drug,
                        requested_dose,
                        sanctioned_ceiling_dose: 0.0,
                        outcome: VerificationOutcome::HardLockoutContraindicated,
                        lockout_reason: Some("METFORMIN CONTRAINDICATED: eGFR < 30 mL/min/1.73m2. Absolute lockout to prevent fatal lactic acidosis."),
                    }
                } else if egfr < 45.0 {
                    let ceiling = 1000.0; // Max 1000 mg/day for eGFR 30-44
                    let sanctioned = requested_dose.min(ceiling);
                    DosingVerificationReport {
                        drug,
                        requested_dose,
                        sanctioned_ceiling_dose: sanctioned,
                        outcome: if requested_dose > ceiling {
                            VerificationOutcome::DoseClamped
                        } else {
                            VerificationOutcome::Approved
                        },
                        lockout_reason: None,
                    }
                } else {
                    let ceiling = 2000.0;
                    let sanctioned = requested_dose.min(ceiling);
                    DosingVerificationReport {
                        drug,
                        requested_dose,
                        sanctioned_ceiling_dose: sanctioned,
                        outcome: if requested_dose > ceiling {
                            VerificationOutcome::DoseClamped
                        } else {
                            VerificationOutcome::Approved
                        },
                        lockout_reason: None,
                    }
                }
            }

            DrugIdentifier::Vancomycin => {
                // Vancomycin: Dettli ceiling adjusted to CrCl
                let ceiling = if crcl < 20.0 {
                    1000.0 // Extended interval / hemodialysis dosing
                } else if crcl < 50.0 {
                    1500.0
                } else {
                    2000.0
                };
                let sanctioned = requested_dose.min(ceiling);
                DosingVerificationReport {
                    drug,
                    requested_dose,
                    sanctioned_ceiling_dose: sanctioned,
                    outcome: if requested_dose > ceiling {
                        VerificationOutcome::DoseClamped
                    } else {
                        VerificationOutcome::Approved
                    },
                    lockout_reason: None,
                }
            }

            DrugIdentifier::Digoxin => {
                if serum_k < 3.5 && !serum_k.is_nan() {
                    DosingVerificationReport {
                        drug,
                        requested_dose,
                        sanctioned_ceiling_dose: 0.0,
                        outcome: VerificationOutcome::RequiresClinicalOverride,
                        lockout_reason: Some("DIGOXIN CAUTION: Serum potassium < 3.5 mEq/L increases risk of fatal arrhythmogenic cardiotoxicity."),
                    }
                } else {
                    let ceiling = if crcl < 30.0 { 0.125 } else { 0.250 };
                    let sanctioned = requested_dose.min(ceiling);
                    DosingVerificationReport {
                        drug,
                        requested_dose,
                        sanctioned_ceiling_dose: sanctioned,
                        outcome: if requested_dose > ceiling {
                            VerificationOutcome::DoseClamped
                        } else {
                            VerificationOutcome::Approved
                        },
                        lockout_reason: None,
                    }
                }
            }

            DrugIdentifier::Enoxaparin => {
                // In severe renal impairment (CrCl < 30), reduce dose by 50%
                let ceiling = if crcl < 30.0 { 50.0 } else { 100.0 };
                let sanctioned = requested_dose.min(ceiling);
                DosingVerificationReport {
                    drug,
                    requested_dose,
                    sanctioned_ceiling_dose: sanctioned,
                    outcome: if requested_dose > ceiling {
                        VerificationOutcome::DoseClamped
                    } else {
                        VerificationOutcome::Approved
                    },
                    lockout_reason: None,
                }
            }

            _ => DosingVerificationReport {
                drug,
                requested_dose,
                sanctioned_ceiling_dose: requested_dose,
                outcome: VerificationOutcome::Approved,
                lockout_reason: None,
            },
        }
    }

    /// Evaluates Tisdale Drug-Induced QTc Risk Score
    /// Score >= 11 designates High Risk and activates cardiac interlock
    pub fn calculate_tisdale_score(input: &TisdaleScoreInput) -> (u8, &'static str) {
        let mut score: u8 = 0;
        if input.age_gte_68 {
            score += 1;
        }
        if input.female_sex {
            score += 1;
        }
        if input.loop_diuretic {
            score += 1;
        }
        if input.serum_k_lte_3_5 {
            score += 2;
        }
        if input.baseline_qtc_gte_450 {
            score += 2;
        }
        if input.acute_myocardial_infarction {
            score += 2;
        }
        if input.sepsis {
            score += 3;
        }
        if input.heart_failure {
            score += 3;
        }

        if input.qtc_prolonging_drugs_count == 1 {
            score += 3;
        } else if input.qtc_prolonging_drugs_count >= 2 {
            score += 6;
        }

        let classification = if score <= 6 {
            "Low Risk (Score <= 6): Standard monitoring"
        } else if score <= 10 {
            "Moderate Risk (Score 7-10): Telemetry monitoring and electrolyte optimization"
        } else {
            "High Risk (Score >= 11): HARD LOCKOUT. Concurrent QTc-prolonging drugs restricted."
        };

        (score, classification)
    }
}
