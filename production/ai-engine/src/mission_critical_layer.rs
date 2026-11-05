//! Mission-Critical Integration Layer — Vendor-neutral operating layer for gaps 6 & 7
//! Addresses: integrated mission-critical infrastructure + medical-gas resilience
//! Sources: Mission Critical Partners (IP networks/incident management/disaster recovery), WHO 9789240101616, Joint Commission safe-condition, Air Liquide zone-alarm case
//! Scope note preserved: capabilities are as-reported, not clinical superiority.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::types::current_timestamp_ns;

/// Unified event from any vendor/system — robot, gas alarm, lab, telehealth
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum IntegrationSource {
    Robot { vendor: String, system: String }, // Intuitive, Medtronic, CMR, Stryker, Zimmer
    MedicalGas { source: String, zone: String },
    Laboratory { lab_id: String },
    Telehealth { station_id: String },
    EmsDispatch,
    NetworkMonitor,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum McpSeverity { Info, Caution, Warning, Critical, Disaster }

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct McpEvent {
    pub event_id: String,
    pub source: IntegrationSource,
    pub severity: McpSeverity,
    pub message: String,
    pub timestamp_ns: u64,
    pub requires_downtime_procedure: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct WorkflowBinding {
    pub escalation_path: Vec<String>, // e.g., ["bedside nurse", "charge", "code team"]
    pub analytics_sink: String,
    pub downtime_procedure_ref: String,
}

/// Vendor-neutral router: normalizes events, applies continuity rules
pub struct MissionCriticalRouter {
    pub event_log: Vec<McpEvent>,
    pub bindings: HashMap<String, WorkflowBinding>,
    pub is_on_downtime: bool,
}

impl MissionCriticalRouter {
    pub fn new() -> Self {
        let mut bindings = HashMap::new();
        bindings.insert("medical_gas".to_string(), WorkflowBinding {
            escalation_path: vec!["bedside RN".to_string(), "respiratory therapy".to_string(), "facilities + supply".to_string()],
            analytics_sink: "hospital_analytics".to_string(),
            downtime_procedure_ref: "oxygen-failure-downtime-v2".to_string(),
        });
        Self { event_log: Vec::new(), bindings, is_on_downtime: false }
    }

    pub fn ingest(&mut self, source: IntegrationSource, severity: McpSeverity, message: impl Into<String>, needs_downtime: bool) -> McpEvent {
        let ev = McpEvent {
            event_id: format!("mcpevt_{}", current_timestamp_ns()),
            source, severity, message: message.into(), timestamp_ns: current_timestamp_ns(),
            requires_downtime_procedure: needs_downtime,
        };
        if ev.requires_downtime_procedure { self.is_on_downtime = true; }
        self.event_log.push(ev.clone());
        ev
    }

    pub fn recent_by_severity(&self, min: McpSeverity) -> Vec<&McpEvent> {
        self.event_log.iter().filter(|e| e.severity >= min).collect()
    }
}


/// === Gap 7: Medical-Gas IoT Resilience ===
/// Continuous pipeline pressure, predictive leak detection, cylinder inventory, failure simulation
/// Sources: WHO 9789240101616, Joint Commission safe-condition, Air Liquide zone-alarm case

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ZoneAlarmState {
    Normal,
    LowPressure,
    Depleted,
    LeakDetected,
    CrossConnected,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MedicalGasMonitor {
    pub zone_id: String,
    pub gas_type: String,
    pub pipeline_pressure_psi: f32,
    pub target_pressure_psi: f32,
    pub alarm_state: ZoneAlarmState,
    pub leak_risk_score: f32,
    pub cylinder_inventory: u32,
    pub cylinders_reserve: u32,
    pub last_check_ns: u64,
}

impl MedicalGasMonitor {
    pub fn new(zone_id: String, gas_type: String, target_pressure_psi: f32) -> Self {
        Self {
            zone_id,
            gas_type,
            pipeline_pressure_psi: target_pressure_psi,
            target_pressure_psi,
            alarm_state: ZoneAlarmState::Normal,
            leak_risk_score: 0.0,
            cylinder_inventory: 10,
            cylinders_reserve: 2,
            last_check_ns: current_timestamp_ns(),
        }
    }

    pub fn update_pressure(&mut self, pressure_psi: f32, now_ns: u64) {
        self.pipeline_pressure_psi = pressure_psi;
        self.last_check_ns = now_ns;
        let ratio = pressure_psi / self.target_pressure_psi;
        self.alarm_state = if ratio >= 0.9 {
            ZoneAlarmState::Normal
        } else if ratio >= 0.7 {
            ZoneAlarmState::LowPressure
        } else if ratio >= 0.4 {
            ZoneAlarmState::Depleted
        } else {
            ZoneAlarmState::CrossConnected
        };
        let deviation = (pressure_psi - self.target_pressure_psi).abs() / self.target_pressure_psi;
        self.leak_risk_score = (deviation * 2.0).clamp(0.0, 1.0);
    }

    pub fn predict_leak(&self) -> bool {
        self.leak_risk_score > 0.6 || self.alarm_state == ZoneAlarmState::LeakDetected
    }

    pub fn consume_cylinder(&mut self) -> bool {
        if self.cylinders_reserve > 0 {
            self.cylinders_reserve -= 1;
            true
        } else if self.cylinder_inventory > 0 {
            self.cylinder_inventory -= 1;
            true
        } else {
            false
        }
    }

    pub fn simulate_failure(&mut self, failure_type: &str) {
        match failure_type {
            "depletion" => {
                self.pipeline_pressure_psi = 0.0;
                self.alarm_state = ZoneAlarmState::Depleted;
                self.leak_risk_score = 1.0;
            }
            "leak" => {
                self.pipeline_pressure_psi = self.target_pressure_psi * 0.5;
                self.alarm_state = ZoneAlarmState::LeakDetected;
                self.leak_risk_score = 0.9;
            }
            "low_pressure" => {
                self.pipeline_pressure_psi = self.target_pressure_psi * 0.75;
                self.alarm_state = ZoneAlarmState::LowPressure;
                self.leak_risk_score = 0.4;
            }
            _ => {}
        }
    }

    pub fn escalation_recommendation(&self) -> Vec<&str> {
        match self.alarm_state {
            ZoneAlarmState::Normal => vec!["Continue monitoring"],
            ZoneAlarmState::LowPressure => vec!["Check supply", "Prepare reserve cylinders"],
            ZoneAlarmState::Depleted => vec!["Switch to reserve", "Call facilities", "Evacuate zone if needed"],
            ZoneAlarmState::LeakDetected => vec!["Isolate zone", "Call facilities + supply", "Switch to cylinders"],
            ZoneAlarmState::CrossConnected => vec!["EMERGENCY: Stop all gas use", "Call facilities immediately", "Evacuate zone"],
        }
    }
}


#[cfg(test)]
mod gas_tests {
    use super::*;

    #[test]
    fn gas_monitor_creates() {
        let monitor = MedicalGasMonitor::new("OR-3".to_string(), "O2".to_string(), 50.0);
        assert_eq!(monitor.zone_id, "OR-3");
        assert_eq!(monitor.gas_type, "O2");
        assert_eq!(monitor.alarm_state, ZoneAlarmState::Normal);
    }

    #[test]
    fn pressure_update_triggers_alarm() {
        let mut monitor = MedicalGasMonitor::new("OR-3".to_string(), "O2".to_string(), 50.0);
        monitor.update_pressure(45.0, current_timestamp_ns());
        assert_eq!(monitor.alarm_state, ZoneAlarmState::Normal);
        monitor.update_pressure(35.0, current_timestamp_ns());
        assert_eq!(monitor.alarm_state, ZoneAlarmState::LowPressure);
        monitor.update_pressure(20.0, current_timestamp_ns());
        assert_eq!(monitor.alarm_state, ZoneAlarmState::Depleted);
    }

    #[test]
    fn leak_prediction() {
        let mut monitor = MedicalGasMonitor::new("OR-3".to_string(), "O2".to_string(), 50.0);
        monitor.update_pressure(25.0, current_timestamp_ns());
        assert!(monitor.predict_leak());
    }

    #[test]
    fn cylinder_consumption() {
        let mut monitor = MedicalGasMonitor::new("OR-3".to_string(), "O2".to_string(), 50.0);
        assert!(monitor.consume_cylinder());
        assert_eq!(monitor.cylinders_reserve, 1);
        assert!(monitor.consume_cylinder());
        assert_eq!(monitor.cylinders_reserve, 0);
        assert!(monitor.consume_cylinder());
        assert_eq!(monitor.cylinder_inventory, 9);
    }

    #[test]
    fn failure_simulation() {
        let mut monitor = MedicalGasMonitor::new("OR-3".to_string(), "O2".to_string(), 50.0);
        monitor.simulate_failure("depletion");
        assert_eq!(monitor.alarm_state, ZoneAlarmState::Depleted);
        assert!(monitor.predict_leak());
        let recs = monitor.escalation_recommendation();
        assert!(recs.iter().any(|r| r.contains("Switch to reserve")));
    }

    #[test]
    fn cross_connection_emergency() {
        let mut monitor = MedicalGasMonitor::new("OR-3".to_string(), "O2".to_string(), 50.0);
        monitor.update_pressure(10.0, current_timestamp_ns());
        assert_eq!(monitor.alarm_state, ZoneAlarmState::CrossConnected);
        let recs = monitor.escalation_recommendation();
        assert!(recs.iter().any(|r| r.contains("EMERGENCY")));
    }
}
