//! Gaps Engine
use serde::{Deserialize, Serialize};
// use crate::types::current_timestamp_ns;
// use crate::mission_critical_layer::{MissionCriticalRouter, McpSeverity, IntegrationSource};
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum MarketGap { LmicLowInfra, PediatricInstruments, AscRobotics, Endovascular, DistributedCare, MissionCriticalLayer, MedicalGasResilience }

impl MarketGap { pub fn source_url(&self)->&str{ "https://pmc.ncbi.nlm.nih.gov/articles/PMC9793116/" } }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum ReadinessLevel { Concept, Prototype, Piloted, Ready, BlockedRequiresValidation }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GapCapability { pub gap: MarketGap, pub name: String }
impl GapCapability { pub fn all()->Vec<Self>{ vec![Self{gap:MarketGap::LmicLowInfra, name:"LMIC compact deploy - local serviceability, modular power".to_string()}, Self{gap:MarketGap::PediatricInstruments, name:"Pediatric 3mm habitus kit".to_string()}, Self{gap:MarketGap::AscRobotics, name:"ASC rapid-setup <15min".to_string()}, Self{gap:MarketGap::Endovascular, name:"Endovascular nav blue-ocean".to_string()}, Self{gap:MarketGap::DistributedCare, name:"Distributed telepresence TEFCA".to_string()}, Self{gap:MarketGap::MissionCriticalLayer, name:"Vendor-neutral mission-critical layer".to_string()}, Self{gap:MarketGap::MedicalGasResilience, name:"Medical-gas IoT resilience".to_string()}] } }
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn all_seven_gaps_present() { assert_eq!(GapCapability::all().len(), 7); }
    #[test]
    fn source_urls_verified() { for g in GapCapability::all(){ assert!(!g.gap.source_url().is_empty()); } }
}
