//! Engine 2: Dynamic Physiological Envelope & Kalman Observer (Plane C)
//!
//! Standards: Aerospace DO-178C Level A / IEC 62304 Class C
//! Analogy: Airbus "Alpha Floor Protection" / Boeing "Flight Envelope Limiter"
//! Prevents hemodynamic stall, rapid MAP collapse, and dynamic drug acceleration spikes.

#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AlphaFloorState {
    Nominal = 0,
    SoftEnvelopeClamped = 1,
    HemodynamicStallEmergency = 2,
}

#[derive(Debug, Clone, Copy)]
pub struct KalmanStateEstimate {
    pub estimated_map_mmhg: f32,       // Estimated true Mean Arterial Pressure
    pub estimated_hr_bpm: f32,         // Estimated true Heart Rate
    pub shock_index: f32,              // HR / SBP
    pub d_map_dt: f32,                 // Rate of MAP change (mmHg/s)
    pub alpha_floor_state: AlphaFloorState,
    pub permissible_rate_ceiling: f32, // Maximum dynamically allowable infusion rate (mL/h)
}

/// 1D Extended Kalman Filter for real-time continuous physiological state estimation
#[derive(Debug, Clone, Copy)]
pub struct PhysiologicalKalmanFilter {
    // State estimate [x: value, v: velocity/rate of change]
    pub x: f32,
    pub v: f32,
    // Covariance matrix elements
    pub p00: f32,
    pub p01: f32,
    pub p10: f32,
    pub p11: f32,
    // Process and measurement noise
    pub q: f32,
    pub r: f32,
}

impl Default for PhysiologicalKalmanFilter {
    fn default() -> Self {
        Self {
            x: 80.0, // Default MAP 80 mmHg
            v: 0.0,
            p00: 1.0,
            p01: 0.0,
            p10: 0.0,
            p11: 1.0,
            q: 0.05, // Process noise
            r: 2.0,  // Measurement sensor noise
        }
    }
}

impl PhysiologicalKalmanFilter {
    pub const fn new(initial_value: f32, process_noise: f32, measurement_noise: f32) -> Self {
        Self {
            x: initial_value,
            v: 0.0,
            p00: 1.0,
            p01: 0.0,
            p10: 0.0,
            p11: 1.0,
            q: process_noise,
            r: measurement_noise,
        }
    }

    /// Step the Kalman filter with a new noisy sensor observation and elapsed time dt (seconds)
    pub fn update(&mut self, measurement: f32, dt: f32) -> (f32, f32) {
        if dt <= 0.0 {
            return (self.x, self.v);
        }

        // 1. Predict state: x_new = x + v*dt
        let x_pred = self.x + self.v * dt;
        let v_pred = self.v;

        // Predict covariance: P_pred = F * P * F^T + Q
        let p00_pred = self.p00 + dt * (self.p10 + self.p01) + dt * dt * self.p11 + self.q;
        let p01_pred = self.p01 + dt * self.p11;
        let p10_pred = self.p10 + dt * self.p11;
        let p11_pred = self.p11 + self.q;

        // 2. Innovation: y = measurement - x_pred
        let y = measurement - x_pred;
        let s = p00_pred + self.r;

        // 3. Kalman gain: K = P_pred * H^T * (1/S)
        let k0 = p00_pred / s;
        let k1 = p10_pred / s;

        // 4. Update state estimate
        self.x = x_pred + k0 * y;
        self.v = v_pred + k1 * y;

        // 5. Update covariance: P = (I - K*H) * P_pred
        self.p00 = p00_pred * (1.0 - k0);
        self.p01 = p01_pred * (1.0 - k0);
        self.p10 = -k1 * p00_pred + p10_pred;
        self.p11 = -k1 * p01_pred + p11_pred;

        (self.x, self.v)
    }
}

/// Dynamic Physiological Envelope & Stall Protection Engine
pub struct PhysiologicalEnvelopeEngine {
    map_filter: PhysiologicalKalmanFilter,
    hr_filter: PhysiologicalKalmanFilter,
    last_rate_setpoint: f32,
}

impl Default for PhysiologicalEnvelopeEngine {
    fn default() -> Self {
        Self {
            map_filter: PhysiologicalKalmanFilter::new(80.0, 0.05, 1.5),
            hr_filter: PhysiologicalKalmanFilter::new(75.0, 0.05, 1.0),
            last_rate_setpoint: 125.0,
        }
    }
}

impl PhysiologicalEnvelopeEngine {
    pub const fn new() -> Self {
        Self {
            map_filter: PhysiologicalKalmanFilter::new(80.0, 0.05, 1.5),
            hr_filter: PhysiologicalKalmanFilter::new(75.0, 0.05, 1.0),
            last_rate_setpoint: 125.0,
        }
    }

    /// Evaluates physiological envelope and applies Alpha-Floor stall protection
    /// Max acceleration: clamp d(Rate)/dt <= 2.5 mL/h/sec
    pub fn evaluate_envelope(
        &mut self,
        raw_map_mmhg: f32,
        raw_hr_bpm: f32,
        raw_sbp_mmhg: f32,
        requested_rate_ml_h: f32,
        dt_seconds: f32,
    ) -> KalmanStateEstimate {
        // Step Kalman filters
        let (est_map, d_map_dt) = self.map_filter.update(raw_map_mmhg, dt_seconds);
        let (est_hr, _) = self.hr_filter.update(raw_hr_bpm, dt_seconds);

        let sbp = if raw_sbp_mmhg > 10.0 { raw_sbp_mmhg } else { est_map * 1.35 };
        let shock_index = est_hr / sbp;

        // Alpha-Floor Stall Check:
        // 1. Critical Stall: MAP < 55 mmHg or rapid crash (d_map_dt < -2.0 mmHg/s)
        // 2. Soft Warning: MAP < 65 mmHg or Shock Index >= 1.0
        let (alpha_floor_state, mut allowed_rate) = if est_map < 55.0 || d_map_dt < -2.0 {
            (AlphaFloorState::HemodynamicStallEmergency, 0.0) // Clamp to zero or emergency trigger
        } else if est_map < 65.0 || shock_index >= 1.0 {
            (AlphaFloorState::SoftEnvelopeClamped, requested_rate_ml_h * 0.50) // Clamp by 50%
        } else {
            (AlphaFloorState::Nominal, requested_rate_ml_h)
        };

        // Slew-rate limiter (Envelope Protection): clamp rate acceleration to <= 2.5 mL/h/sec
        // In emergency stall, bypass slew-rate ramp and cut immediately to 0.0
        if alpha_floor_state != AlphaFloorState::HemodynamicStallEmergency && dt_seconds > 0.0 {
            let max_delta = 2.5 * dt_seconds;
            let current_delta = allowed_rate - self.last_rate_setpoint;
            if current_delta > max_delta {
                allowed_rate = self.last_rate_setpoint + max_delta;
            } else if current_delta < -max_delta {
                allowed_rate = self.last_rate_setpoint - max_delta;
            }
        }
        self.last_rate_setpoint = allowed_rate;

        KalmanStateEstimate {
            estimated_map_mmhg: est_map,
            estimated_hr_bpm: est_hr,
            shock_index,
            d_map_dt,
            alpha_floor_state,
            permissible_rate_ceiling: allowed_rate,
        }
    }
}
