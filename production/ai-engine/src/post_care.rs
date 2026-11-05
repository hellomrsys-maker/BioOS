//! Post-Care Engine - Aftermost treatment according to condition
use serde::{Deserialize, Serialize};
use crate::types::current_timestamp_ns;
use crate::awareness::{PatientContext, Acuity, PatientPhase};
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum PostCarePathway { Routine{ p:String }, Enhanced{ reason:String }, DisasterAftercare{ protocol:String } }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PostCarePlan { pub patient_id:String, pub pathway:PostCarePathway, pub orders:Vec<CareOrder>, pub red_flags:Vec<String> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CareOrder { pub order:String, pub rationale:String }
impl PostCarePlan { pub fn red_flag(&self, s:&str)->bool{ self.red_flags.iter().any(|r| s.contains(r)) } }
pub struct PostCareEngine;
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LabAutomationOrder { pub test: String, pub automation_note: String, pub mitigation: String }
impl PostCareEngine {
    pub fn plan_for(patient: &PatientContext)->PostCarePlan{
        let pathway=match &patient.phase{ PatientPhase::DisasterVictim{..}=>PostCarePathway::DisasterAftercare{ protocol:"disaster_water_wound".to_string()}, (_, Acuity::Critical)=>PostCarePathway::Enhanced{ reason:"critical".to_string()}, _=>PostCarePathway::Routine{ p:"standard".to_string()}};
        let mut orders=vec![]; let mut red=vec![];
        if matches!(pathway, PostCarePathway::DisasterAftercare{..}){
            orders.push(CareOrder{ order:"clean water wound irrigation q8h (boiled, not tap - flood contaminated)".to_string(), rationale:"WHO waterborne risk 0.92: prevent cholera/leptospira wound sepsis (Nepal case)".to_string()});
            orders.push(CareOrder{ order:"wound swab + lab HIL check before antibiotics".to_string(), rationale:"LCL 25M-tests model: hemolysis >150 or bilirubin >10 triggers redraw, avoid false sepsis label".to_string()});
            red.push("fever >38.5 + water exposure".to_string());
            red.push("expanding erythema + sewage contact".to_string());
        }
        PostCarePlan{ patient_id:patient.patient_id.clone(), pathway, orders, red_flags:red }
    }
    pub fn lab_mitigation(hgb: f32, bili: f32, lipe: f32) -> Vec<LabAutomationOrder> {
        let mut v=Vec::new();
        if hgb > 150.0 { v.push(LabAutomationOrder{ test:"CBC".to_string(), automation_note:"Hemolysis HGB >150 triggers auto-redraw (Roche automation logic)".to_string(), mitigation:"Shift staff from manual pipetting to verification per LCL pandemic model".to_string() }); }
        if bili > 10.0 { v.push(LabAutomationOrder{ test:"LFT".to_string(), automation_note:"Icterus >10 blocks photometry".to_string(), mitigation:"Dilution + high-value review".to_string() }); }
        if lipe > 500.0 { v.push(LabAutomationOrder{ test:"Lipids".to_string(), automation_note:"Lipemia >500".to_string(), mitigation:"Ultracentrifuge + comment".to_string() }); }
        v
    }
}
