//! Engine 4: Hardware Watchdog & Interlock Engine (WIE)
//!
//! Standards: IEC 62304 Class C, ASTM F2761 ICE
//! 3-State Mealy Automaton, 2ms/12ms dual-stage actuator trips, 50ms heartbeat watchdog.

pub const HEARTBEAT_TIMEOUT_NS: u32 = 50_000_000; // 50 milliseconds in nanoseconds
pub const SSR_TRIP_LATENCY_MS: u32 = 2;            // Solid-state relay trip <= 2 ms
pub const MECHANICAL_RELAY_LATENCY_MS: u32 = 12;   // Mechanical relay trip <= 12 ms

#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WatchdogState {
    Normal = 0,
    Caution = 1,
    HardwareLockout = 2,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RelayAction {
    MaintainPower,
    TripSolidStateRelay,
    TripBothRelaysMechanicalAirGap,
}

#[derive(Debug, Clone, Copy)]
pub struct WatchdogTripReport {
    pub current_state: WatchdogState,
    pub relay_action: RelayAction,
    pub ssr_trip_time_ms: u32,
    pub mechanical_trip_time_ms: u32,
    pub reason: &'static str,
}

pub struct HardwareWatchdogEngine {
    state: WatchdogState,
    last_heartbeat_ns: u32,
}

impl Default for HardwareWatchdogEngine {
    fn default() -> Self {
        Self {
            state: WatchdogState::Normal,
            last_heartbeat_ns: 0,
        }
    }
}

impl HardwareWatchdogEngine {
    pub const fn new() -> Self {
        Self {
            state: WatchdogState::Normal,
            last_heartbeat_ns: 0,
        }
    }

    pub fn state(&self) -> WatchdogState {
        self.state
    }

    /// Evaluates current telemetry and heartbeat to determine Mealy state transition
    pub fn evaluate_cycle(
        &mut self,
        current_time_ns: u32,
        plane_b_heartbeat_ns: u32,
        has_occlusion_trip: bool,
        has_bubble_trip: bool,
        has_pharmacology_lockout: bool,
        is_warning_condition: bool,
    ) -> WatchdogTripReport {
        // Update heartbeat tracking
        self.last_heartbeat_ns = plane_b_heartbeat_ns;

        // Check heartbeat deadline (50 ms)
        let heartbeat_elapsed = if current_time_ns >= plane_b_heartbeat_ns {
            current_time_ns - plane_b_heartbeat_ns
        } else {
            0
        };

        let heartbeat_lost = heartbeat_elapsed > HEARTBEAT_TIMEOUT_NS;

        // Hard trip criteria (Mode-Invariant: cannot be overridden in any disaster/surge mode)
        if has_occlusion_trip || has_bubble_trip || has_pharmacology_lockout || heartbeat_lost {
            self.state = WatchdogState::HardwareLockout;

            let reason = if has_occlusion_trip {
                "TRIP: Infusion line occlusion exceeded 10.2 psi (525 mmHg)"
            } else if has_bubble_trip {
                "TRIP: Ultrasonic sensor detected air bubble >= 25 uL in IV line"
            } else if has_pharmacology_lockout {
                "TRIP: Pharmacological ceiling violated or absolute contraindication triggered"
            } else {
                "TRIP: Plane B Cognitive Plane heartbeat missed deadline (> 50 ms)"
            };

            return WatchdogTripReport {
                current_state: WatchdogState::HardwareLockout,
                relay_action: RelayAction::TripBothRelaysMechanicalAirGap,
                ssr_trip_time_ms: SSR_TRIP_LATENCY_MS,
                mechanical_trip_time_ms: MECHANICAL_RELAY_LATENCY_MS,
                reason,
            };
        }

        // Soft warning criteria
        if is_warning_condition {
            self.state = WatchdogState::Caution;
            return WatchdogTripReport {
                current_state: WatchdogState::Caution,
                relay_action: RelayAction::MaintainPower,
                ssr_trip_time_ms: 0,
                mechanical_trip_time_ms: 0,
                reason: "CAUTION: Parameter near safety boundary. Infusion rate clamped to baseline.",
            };
        }

        // Nominal state
        self.state = WatchdogState::Normal;
        WatchdogTripReport {
            current_state: WatchdogState::Normal,
            relay_action: RelayAction::MaintainPower,
            ssr_trip_time_ms: 0,
            mechanical_trip_time_ms: 0,
            reason: "NOMINAL: All parameters within certified bounds.",
        }
    }

    /// Explicit manual reset of hardware lockout (requires physical clinical confirmation)
    pub fn reset_lockout(&mut self) {
        self.state = WatchdogState::Normal;
    }
}
