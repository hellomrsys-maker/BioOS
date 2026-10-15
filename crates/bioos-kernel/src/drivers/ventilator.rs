//! # BioOS Hamilton G5 / Maquet Servo-u Mechanical Ventilator Driver
//! Standards: ISO 80601-2-12, ASTM F2761 ICE
//! Monitors Peak Inspiratory Pressure (PIP), PEEP, FiO2, and Minute Volume.

pub struct MechanicalVentilatorDriver {
    pub device_id: u32,
    pub pip_cmh2o: f32,
    pub peep_cmh2o: f32,
    pub fio2_percent: f32,
    pub tidal_volume_ml: u16,
    pub respiratory_rate_bpm: u8,
    pub high_pressure_alarm: bool,
    pub apnea_alarm: bool,
}

impl MechanicalVentilatorDriver {
    pub const fn new(device_id: u32) -> Self {
        Self {
            device_id,
            pip_cmh2o: 18.0,
            peep_cmh2o: 5.0,
            fio2_percent: 21.0,
            tidal_volume_ml: 450,
            respiratory_rate_bpm: 14,
            high_pressure_alarm: false,
            apnea_alarm: false,
        }
    }

    pub fn update_vitals(&mut self, pip: f32, peep: f32, fio2: f32, rr: u8) -> bool {
        self.pip_cmh2o = pip;
        self.peep_cmh2o = peep;
        self.fio2_percent = fio2;
        self.respiratory_rate_bpm = rr;

        // Barotrauma guard: PIP >= 40 cmH2O trips high pressure alarm
        if pip >= 40.0 {
            self.high_pressure_alarm = true;
            false
        } else {
            self.high_pressure_alarm = false;
            true
        }
    }
}
