//! Engine 2: Biometric & Pharmacokinetic Engine (BPE)
//!
//! Standards: 2021 CKD-EPI Race-Free, Cockcroft-Gault, Child-Pugh, MELD-Na 2016
//! Deterministic physiological organ reserve indices and kinetic clearance modeling.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Sex {
    Male,
    Female,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChildPughClass {
    ClassA, // 5-6 points: Well-compensated
    ClassB, // 7-9 points: Significant functional compromise
    ClassC, // 10-15 points: Decompensated
}

#[derive(Debug, Clone, Copy)]
pub struct PatientBiometrics {
    pub age_years: f32,
    pub sex: Sex,
    pub height_cm: f32,
    pub weight_kg: f32,
    pub serum_creatinine_mg_dl: f32,
}

pub struct BiometricPharmacokineticEngine;

impl BiometricPharmacokineticEngine {
    /// Computes 2021 CKD-EPI Race-Free Estimated Glomerular Filtration Rate (eGFR)
    /// Formula: eGFR = 142 * min(Scr/kappa, 1)^alpha * max(Scr/kappa, 1)^(-1.200) * 0.9938^Age * [1.012 if female]
    pub fn calculate_ckd_epi_2021(bio: &PatientBiometrics) -> f32 {
        let (kappa, alpha, sex_mult) = match bio.sex {
            Sex::Female => (0.7f64, -0.241f64, 1.012f64),
            Sex::Male => (0.9f64, -0.302f64, 1.0f64),
        };

        let scr = bio.serum_creatinine_mg_dl as f64;
        let age = bio.age_years as f64;

        if scr <= 0.0 || age <= 0.0 {
            return 0.0;
        }

        let ratio = scr / kappa;
        let min_part = if ratio < 1.0 { ratio } else { 1.0 };
        let max_part = if ratio > 1.0 { ratio } else { 1.0 };

        let egfr = 142.0
            * libm::pow(min_part, alpha)
            * libm::pow(max_part, -1.200)
            * libm::pow(0.9938, age)
            * sex_mult;

        egfr as f32
    }

    /// Computes Devine Ideal Body Weight (IBW) in kg
    pub fn calculate_devine_ibw(height_cm: f32, sex: Sex) -> f32 {
        let height_inches_over_60 = (height_cm - 152.4) / 2.54;
        let base_kg = match sex {
            Sex::Male => 50.0,
            Sex::Female => 45.5,
        };
        base_kg + 2.3 * height_inches_over_60
    }

    /// Evaluates BMI and selects appropriate dosing weight (TBW, IBW, or ABW)
    pub fn select_dosing_weight(weight_kg: f32, height_cm: f32, sex: Sex) -> (f32, &'static str) {
        let height_m = height_cm / 100.0;
        let bmi = weight_kg / (height_m * height_m);
        let ibw = Self::calculate_devine_ibw(height_cm, sex);

        if bmi < 18.5 {
            (weight_kg, "TBW: Underweight (BMI < 18.5)")
        } else if bmi < 25.0 {
            (ibw, "IBW: Normal weight (18.5 <= BMI < 25)")
        } else {
            let abw = ibw + 0.40 * (weight_kg - ibw);
            (abw, "ABW: Overweight/Obese (BMI >= 25)")
        }
    }

    /// Cockcroft-Gault Creatinine Clearance with automated 3-tier weight selection
    pub fn calculate_cockcroft_gault(bio: &PatientBiometrics) -> f32 {
        if bio.serum_creatinine_mg_dl <= 0.0 {
            return 0.0;
        }
        let (dosing_weight, _) = Self::select_dosing_weight(bio.weight_kg, bio.height_cm, bio.sex);
        let sex_factor = match bio.sex {
            Sex::Male => 1.0,
            Sex::Female => 0.85,
        };

        let crcl = ((140.0 - bio.age_years) * dosing_weight) / (72.0 * bio.serum_creatinine_mg_dl)
            * sex_factor;
        if crcl < 0.0 {
            0.0
        } else {
            crcl
        }
    }

    /// Jelliffe Kinetic Clearance for Acute Kidney Injury with shifting creatinine
    pub fn calculate_kinetic_clearance(
        baseline_cr: f32,
        current_cr: f32,
        delta_hours: f32,
        dosing_weight_kg: f32,
    ) -> f32 {
        if delta_hours <= 0.0 || current_cr <= 0.0 || baseline_cr <= 0.0 {
            return 0.0;
        }
        let volume_distribution = 0.60 * dosing_weight_kg; // Liters
        let cr_prod_rate = 20.0 * dosing_weight_kg; // mg/day estimated baseline production
        let mean_cr = (baseline_cr + current_cr) / 2.0;

        let delta_days = delta_hours / 24.0;
        let cr_accumulation = (current_cr - baseline_cr) * 10.0 * volume_distribution / delta_days;

        let kinetic_clearance_l_day = (cr_prod_rate - cr_accumulation) / (mean_cr * 10.0);
        let kinetic_crcl_ml_min = (kinetic_clearance_l_day * 1000.0) / 1440.0;

        if kinetic_crcl_ml_min < 0.0 {
            0.0
        } else {
            kinetic_crcl_ml_min
        }
    }

    /// Child-Pugh Hepatic Function Classification
    pub fn calculate_child_pugh(
        total_bilirubin_mg_dl: f32,
        serum_albumin_g_dl: f32,
        inr: f32,
        ascites_grade: u8,        // 1=None, 2=Mild/Slight, 3=Moderate/Severe
        encephalopathy_grade: u8, // 1=None, 2=Grade 1-2, 3=Grade 3-4
    ) -> (u8, ChildPughClass) {
        let bili_pts = if total_bilirubin_mg_dl < 2.0 {
            1
        } else if total_bilirubin_mg_dl <= 3.0 {
            2
        } else {
            3
        };

        let alb_pts = if serum_albumin_g_dl > 3.5 {
            1
        } else if serum_albumin_g_dl >= 2.8 {
            2
        } else {
            3
        };

        let inr_pts = if inr < 1.7 {
            1
        } else if inr <= 2.3 {
            2
        } else {
            3
        };

        let ascites_pts = ascites_grade.clamp(1, 3);
        let enceph_pts = encephalopathy_grade.clamp(1, 3);

        let total_score = bili_pts + alb_pts + inr_pts + ascites_pts + enceph_pts;

        let class = if total_score <= 6 {
            ChildPughClass::ClassA
        } else if total_score <= 9 {
            ChildPughClass::ClassB
        } else {
            ChildPughClass::ClassC
        };

        (total_score, class)
    }

    /// Immunocompromise Risk Multiplier (kappa_immuno)
    pub fn calculate_immuno_multiplier(
        anc: f32, // Absolute Neutrophil Count (/uL)
        has_organ_transplant: bool,
        high_dose_steroids: bool,
        albumin_g_dl: f32,
    ) -> f32 {
        let mut kappa = 1.0f32;
        if anc < 500.0 {
            kappa += 0.80; // Severe neutropenia
        }
        if has_organ_transplant {
            kappa += 0.60;
        }
        if high_dose_steroids {
            kappa += 0.40;
        }
        if albumin_g_dl < 2.5 {
            kappa += 0.25; // Severe malnutrition
        }
        kappa
    }
}
