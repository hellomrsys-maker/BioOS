//! AwarenessEngine - detect what we deal with and choose strategy
use crate::awareness::{WorldModel, DealingWith, DisasterContext, DisasterType, DisasterScale, WaterContam, TissueContext};
use crate::human_anatomy::TissueType;
use crate::types::current_timestamp_ns;
#[derive(Default)]
pub struct AwarenessEngine { pub world: WorldModel }
impl AwarenessEngine {
    pub fn new()->Self{ Self{ world: WorldModel::new() } }
    pub fn detect(&mut self, vision_hint: Option<String>, manual_hint: Option<String>) -> WorldModel {
        self.world.ts_ns = current_timestamp_ns();
        if let Some(h)=manual_hint{ let l=h.to_lowercase(); if l.contains("flood")||l.contains("nepal")||l.contains("water disaster")||l.contains("surge"){
            let d=DisasterContext{ disaster_id:format!("detected_{}", current_timestamp_ns()), disaster_type:DisasterType::Flood,
                scale:DisasterScale{ affected_districts:6, hospitals_overwhelmed:3, load_factor:8.0 },
                affected_pop:50000, confirmed:200, estimated:800,
                water_contam: WaterContam{ is_contaminated:true, contaminants:vec!["sewage".to_string(),"debris".to_string()], risk:0.85 },
                hazards:vec!["landslide".to_string(),"waterborne_disease".to_string()], reference_case:Some("nepal_2024_flood".to_string())};
            self.world.dealing_with.push(DealingWith::Disaster(d)); } }
        if let Some(v)=vision_hint{ if v.contains("tissue")||v.contains("liver"){
            self.world.dealing_with.push(DealingWith::Tissue(TissueContext{ detected_type:TissueType::Liver, confidence:0.8,
                location: crate::operational_rules::Vector3{ x:0.0,y:0.0,z:0.0 }, prime_viability:Some(0.9),
                safe_actions:vec!["suction".to_string()], forbidden:vec!["high_energy".to_string()] })); } }
        self.world.primary = self.world.dealing_with.first().cloned();
        self.world.confidence = if self.world.dealing_with.is_empty(){0.2}else{0.75};
        self.world.clone()
    }
    pub fn dealing_strategy(&self) -> crate::awareness::DealingStrategy {
        use crate::awareness::{DealingStrategy, StrategyMode};
        if self.world.is_disaster(){ DealingStrategy{ mode:StrategyMode::Surge, priority:"triage_and_stabilize".to_string(), prepare_for:vec!["waterborne_disease".to_string()] } }
        else { DealingStrategy{ mode:StrategyMode::Standard, priority:"safety".to_string(), prepare_for:vec![] } }
    }
}