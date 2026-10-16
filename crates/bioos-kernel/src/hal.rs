//! # BioOS Hardware Abstraction Layer (HAL)
//! Standards: IEEE 11073-10207 (BICEPS), ISO/IEEE 11073-20702 (MDPWS)
//! Abstraction for medical peripheral buses (CAN, SPI, UART, SDC Ethernet).

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum BusType {
    CanBusMedical = 0,
    SpiSensors = 1,
    UartPocAnalyzer = 2,
    SdcEthernet = 3,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum BusStatus {
    Online = 0,
    Degraded = 1,
    BusOffError = 2,
    Lockout = 3,
}

#[derive(Clone, Copy, Debug)]
pub struct CanFrame {
    pub can_id: u32,
    pub dlc: u8,
    pub data: [u8; 8],
    pub timestamp_us: u32,
}

pub struct MedicalBusController {
    pub bus_type: BusType,
    pub status: BusStatus,
    pub baud_rate: u32,
    pub tx_frames_count: u64,
    pub rx_frames_count: u64,
    pub bus_error_count: u32,
    pub fault_injected: bool,
}

impl MedicalBusController {
    pub const fn new(bus_type: BusType, baud_rate: u32) -> Self {
        Self {
            bus_type,
            status: BusStatus::Online,
            baud_rate,
            tx_frames_count: 0,
            rx_frames_count: 0,
            bus_error_count: 0,
            fault_injected: false,
        }
    }

    // Simulated bus: models transmission outcome only. When a real
    // transceiver HAL is wired, serialize `frame` onto the physical bus here.
    pub fn transmit_frame(&mut self, _frame: &CanFrame) -> bool {
        if self.fault_injected || self.status == BusStatus::BusOffError {
            self.bus_error_count += 1;
            return false;
        }

        self.tx_frames_count += 1;
        true
    }

    pub fn inject_fault(&mut self, enable: bool) {
        self.fault_injected = enable;
        self.status = if enable {
            BusStatus::BusOffError
        } else {
            BusStatus::Online
        };
    }
}
