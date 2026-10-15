//! # BioOS BD Alaris / B. Braun Space Infusion Pump Driver
//! Standards: ASTM F2761 ICE, IEC 60601-2-24
//! Enforces Dose Error Reduction Systems (DERS) hard limits.

pub struct InfusionPumpDriver {
    pub device_id: u32,
    pub active_rate_ml_h: f32,
    pub hard_max_rate_ml_h: f32,
    pub line_pressure_mmhg: u16,
    pub occlusion_threshold_mmhg: u16,
    pub is_occluded: bool,
    pub air_bubble_detected: bool,
    pub total_volume_infused_ml: f32,
}

impl InfusionPumpDriver {
    pub const fn new(device_id: u32, hard_max_rate: f32, occlusion_threshold: u16) -> Self {
        Self {
            device_id,
            active_rate_ml_h: 0.0,
            hard_max_rate_ml_h: hard_max_rate,
            line_pressure_mmhg: 120,
            occlusion_threshold_mmhg: occlusion_threshold,
            is_occluded: false,
            air_bubble_detected: false,
            total_volume_infused_ml: 0.0,
        }
    }

    /// Sets flow rate with mandatory DERS hard limit clamp.
    pub fn set_rate(&mut self, requested_rate: f32) -> Result<f32, &'static str> {
        if self.is_occluded || self.air_bubble_detected {
            self.active_rate_ml_h = 0.0;
            return Err("HARDWARE_LOCKOUT_ACTIVE");
        }

        if requested_rate > self.hard_max_rate_ml_h {
            self.active_rate_ml_h = self.hard_max_rate_ml_h;
            Ok(self.hard_max_rate_ml_h)
        } else {
            self.active_rate_ml_h = requested_rate.max(0.0);
            Ok(self.active_rate_ml_h)
        }
    }

    /// Updates line pressure and triggers emergency stop on occlusion.
    pub fn update_telemetry(&mut self, pressure: u16, bubble_detected: bool) -> bool {
        self.line_pressure_mmhg = pressure;
        self.air_bubble_detected = bubble_detected;

        if pressure >= self.occlusion_threshold_mmhg || bubble_detected {
            self.is_occluded = true;
            self.active_rate_ml_h = 0.0; // Emergency Actuator Cutoff
            false
        } else {
            self.is_occluded = false;
            true
        }
    }
}
