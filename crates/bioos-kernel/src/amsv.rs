//! Atomic Memory State Vector (AMSV) and Seqlock Primitives
//!
//! Standard Compliance: IEC 62304 Class C, ASTM F2761 ICE
//! Memory Layout: 64 Bytes Cache-Line Aligned, Zero-Copy C-ABI compatible.

use core::sync::atomic::{fence, Ordering};

/// Operating regimes for BioOS
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GlobalOperatingMode {
    Routine = 0,
    Surge = 1,
    Disaster = 2,
}

impl From<u8> for GlobalOperatingMode {
    fn from(val: u8) -> Self {
        match val {
            1 => GlobalOperatingMode::Surge,
            2 => GlobalOperatingMode::Disaster,
            _ => GlobalOperatingMode::Routine,
        }
    }
}

/// Device classification enumeration (ASTM F2761)
#[repr(u16)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DeviceClass {
    Unknown = 0,
    InfusionPump = 1,
    MechanicalVentilator = 2,
    Dialyzer = 3,
    PatientMonitor = 4,
    AnesthesiaWorkstation = 5,
}

/// IEC 60601-1-8 Alarm Classification
#[repr(u16)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AlarmClass {
    None = 0,
    LowPriority = 1,
    MediumPriority = 2,
    HighPriority = 3,
    HardwareTripEmergency = 4,
}

/// Sensor signal quality flags bitmask
pub mod quality_flags {
    pub const VALID: u32 = 1 << 0;
    pub const CALIBRATED: u32 = 1 << 1;
    pub const NOISY_WARNING: u32 = 1 << 2;
    pub const DRIFT_WARNING: u32 = 1 << 3;
    pub const HEMOLYSIS_REJECTED: u32 = 1 << 4;
    pub const ICTERUS_FLAGGED: u32 = 1 << 5;
    pub const LIPEMIA_FLAGGED: u32 = 1 << 6;
    pub const CENSORED_LLOR: u32 = 1 << 7;
    pub const AIR_BUBBLE_DETECTED: u32 = 1 << 8;
    pub const OCCLUSION_DETECTED: u32 = 1 << 9;
    pub const WATCHDOG_TIMEOUT: u32 = 1 << 10;
}

/// Exactly 64-byte Atomic Memory State Vector
#[repr(C, align(64))]
#[derive(Debug, Clone, Copy)]
pub struct AtomicMemoryStateVector {
    pub seq_ctr: u64,                // 0x00..0x07: Seqlock sequence counter
    pub t_write_ns: u32,             // 0x08..0x0B: Monotonic nanosecond timestamp
    pub device_class: u16,           // 0x0C..0x0D: Device category enum
    pub metric_code: u16,            // 0x0E..0x0F: Telemetry / biomarker code
    pub value_x1000: i32,            // 0x10..0x13: Fixed point value * 1000
    pub quality_flags: u32,          // 0x14..0x17: Quality bitmask
    pub hil_h: u16,                  // 0x18..0x19: CLSI C56-A Hemolysis index (mg/dL)
    pub hil_i: u16,                  // 0x1A..0x1B: Icterus index
    pub hil_l: u16,                  // 0x1C..0x1D: Lipemia index
    pub limit_state: u16,            // 0x1E..0x1F: Limit boundary (0=Nominal, 1=Soft, 2=Hard)
    pub rate_setpoint_x10: u32,      // 0x20..0x23: Infusion rate target (mL/h * 10)
    pub rate_actual_x10: u32,        // 0x24..0x27: Measured actual rate (mL/h * 10)
    pub occlusion_mmhg: u32,         // 0x28..0x2B: Measured line pressure (mmHg)
    pub alarm_class: u16,            // 0x2C..0x2D: IEC 60601-1-8 alarm level
    pub crc16: u16,                  // 0x2E..0x2F: CRC-16 checksum
    pub global_mode: u8,             // 0x30: Operating regime (0=ROUTINE, 1=SURGE, 2=DISASTER)
    pub active_escalation_tier: u8,  // 0x31: Escalation index tier (0..4)
    pub facility_census_bitmap: u16, // 0x32..0x33: Facility capacity flags
    pub hics_incident_id: u32,       // 0x34..0x37: HICS Incident Command ID
    pub system_checksum: u64,        // 0x38..0x3F: SHA/CRC-64 integrity hash
}

// Compile-time verification of 64-byte size and alignment for Plane A
const _: () = assert!(core::mem::size_of::<AtomicMemoryStateVector>() == 64);
const _: () = assert!(core::mem::align_of::<AtomicMemoryStateVector>() == 64);

/// Cache Line 1 (64 Bytes): Engine 2 Dynamic Envelope & Kalman Observer State
#[repr(C, align(64))]
#[derive(Debug, Clone, Copy)]
pub struct PhysiologicalEnvelopeVector {
    pub env_seq_ctr: u64,                // 0x00..0x07: Seqlock counter for Envelope (8 bytes)
    pub env_checksum: u64,               // 0x08..0x0F: Integrity signature (8 bytes)
    pub permissible_rate_x10: u32,       // 0x10..0x13: Dynamically allowed rate (mL/h * 10) (4 bytes)
    pub kalman_variance_p00_x100: u32,   // 0x14..0x17: Kalman state uncertainty (4 bytes)
    pub kalman_variance_p11_x100: u32,   // 0x18..0x1B: Kalman velocity uncertainty (4 bytes)
    pub est_map_x10: u16,                // 0x1C..0x1D: Estimated MAP (mmHg * 10) (2 bytes)
    pub est_hr_x10: u16,                 // 0x1E..0x1F: Estimated Heart Rate (bpm * 10) (2 bytes)
    pub shock_index_x100: u16,           // 0x20..0x21: Shock Index (HR/SBP * 100) (2 bytes)
    pub d_map_dt_x100: i16,              // 0x22..0x23: Rate of MAP change (mmHg/s * 100) (2 bytes)
    pub dynamic_margin_x100: u16,        // 0x24..0x25: Physiological margin % (2 bytes)
    pub env_crc16: u16,                  // 0x26..0x27: CRC-16 checksum (2 bytes)
    pub alpha_floor_state: u8,           // 0x28: 0=Nominal, 1=SoftClamp, 2=StallEmergency (1 byte)
    pub slew_clamped: u8,                // 0x29: 1 if rate acceleration was clamped (1 byte)
    pub reserved: [u8; 22],              // 0x2A..0x3F: Future expansion buffer (22 bytes)
}

const _: () = assert!(core::mem::size_of::<PhysiologicalEnvelopeVector>() == 64);
const _: () = assert!(core::mem::align_of::<PhysiologicalEnvelopeVector>() == 64);

/// Exactly 128-Byte Tri-Plane Dual-Cache-Line State Vector
#[repr(C, align(64))]
#[derive(Debug, Clone, Copy)]
pub struct TriPlaneAmsv {
    pub plane_a: AtomicMemoryStateVector,     // Cache Line 0 (64 bytes): Engine 1 Actuation & Watchdog
    pub plane_c: PhysiologicalEnvelopeVector, // Cache Line 1 (64 bytes): Engine 2 Dynamic Envelope & Kalman
}

const _: () = assert!(core::mem::size_of::<TriPlaneAmsv>() == 128);
const _: () = assert!(core::mem::align_of::<TriPlaneAmsv>() == 64);

impl Default for PhysiologicalEnvelopeVector {
    fn default() -> Self {
        Self {
            env_seq_ctr: 0,
            env_checksum: 0,
            permissible_rate_x10: 1250, // 125.0 mL/h
            kalman_variance_p00_x100: 100,
            kalman_variance_p11_x100: 100,
            est_map_x10: 800, // 80.0 mmHg
            est_hr_x10: 750,  // 75.0 bpm
            shock_index_x100: 62, // 0.62
            d_map_dt_x100: 0,
            dynamic_margin_x100: 1000,
            env_crc16: 0,
            alpha_floor_state: 0,
            slew_clamped: 0,
            reserved: [0; 22],
        }
    }
}

impl Default for TriPlaneAmsv {
    fn default() -> Self {
        Self {
            plane_a: AtomicMemoryStateVector::default(),
            plane_c: PhysiologicalEnvelopeVector::default(),
        }
    }
}

impl Default for AtomicMemoryStateVector {
    fn default() -> Self {
        Self {
            seq_ctr: 0,
            t_write_ns: 0,
            device_class: DeviceClass::InfusionPump as u16,
            metric_code: 0,
            value_x1000: 0,
            quality_flags: quality_flags::VALID | quality_flags::CALIBRATED,
            hil_h: 0,
            hil_i: 0,
            hil_l: 0,
            limit_state: 0,
            rate_setpoint_x10: 0,
            rate_actual_x10: 0,
            occlusion_mmhg: 0,
            alarm_class: AlarmClass::None as u16,
            crc16: 0,
            global_mode: GlobalOperatingMode::Routine as u8,
            active_escalation_tier: 0,
            facility_census_bitmap: 0,
            hics_incident_id: 0,
            system_checksum: 0,
        }
    }
}

impl AtomicMemoryStateVector {
    /// Computes CRC16-CCITT across bytes 0x08..0x2E
    pub fn compute_crc16(&self) -> u16 {
        let mut crc: u16 = 0xFFFF;
        let bytes: &[u8] = unsafe {
            core::slice::from_raw_parts(
                (self as *const Self as *const u8).add(8),
                0x2E - 8,
            )
        };
        for &byte in bytes {
            crc ^= (byte as u16) << 8;
            for _ in 0..8 {
                if (crc & 0x8000) != 0 {
                    crc = (crc << 1) ^ 0x1021;
                } else {
                    crc <<= 1;
                }
            }
        }
        crc
    }

    /// Validates internal consistency
    pub fn is_valid(&self) -> bool {
        self.crc16 == self.compute_crc16()
    }
}

/// Lockless Seqlock Cell wrapping the AtomicMemoryStateVector
pub struct SeqlockAmsv {
    state: core::cell::UnsafeCell<AtomicMemoryStateVector>,
}

unsafe impl Sync for SeqlockAmsv {}
unsafe impl Send for SeqlockAmsv {}

impl SeqlockAmsv {
    pub const fn new() -> Self {
        Self {
            state: core::cell::UnsafeCell::new(AtomicMemoryStateVector {
                seq_ctr: 0,
                t_write_ns: 0,
                device_class: 0,
                metric_code: 0,
                value_x1000: 0,
                quality_flags: 0,
                hil_h: 0,
                hil_i: 0,
                hil_l: 0,
                limit_state: 0,
                rate_setpoint_x10: 0,
                rate_actual_x10: 0,
                occlusion_mmhg: 0,
                alarm_class: 0,
                crc16: 0,
                global_mode: 0,
                active_escalation_tier: 0,
                facility_census_bitmap: 0,
                hics_incident_id: 0,
                system_checksum: 0,
            }),
        }
    }

    /// Read atomically without locking
    pub fn read(&self) -> AtomicMemoryStateVector {
        loop {
            let ptr = self.state.get();
            let seq0 = unsafe { (*ptr).seq_ctr };
            // If seq is odd, writer is active; spin
            if seq0 & 1 != 0 {
                core::hint::spin_loop();
                continue;
            }
            fence(Ordering::Acquire);
            let val = unsafe { *ptr };
            fence(Ordering::Acquire);
            let seq1 = unsafe { (*ptr).seq_ctr };
            if seq0 == seq1 {
                return val;
            }
            core::hint::spin_loop();
        }
    }

    /// Write atomically, updating sequence counter
    pub fn write<F>(&self, update: F)
    where
        F: FnOnce(&mut AtomicMemoryStateVector),
    {
        let ptr = self.state.get();
        let old_seq = unsafe { (*ptr).seq_ctr };
        // Increment to odd to signal write in progress
        unsafe {
            (*ptr).seq_ctr = old_seq.wrapping_add(1);
        }
        fence(Ordering::Release);

        update(unsafe { &mut *ptr });

        // Update CRC16
        unsafe {
            let crc = (*ptr).compute_crc16();
            (*ptr).crc16 = crc;
        }

        fence(Ordering::Release);
        // Increment to next even number to signal write complete
        unsafe {
            (*ptr).seq_ctr = old_seq.wrapping_add(2);
        }
    }
}
