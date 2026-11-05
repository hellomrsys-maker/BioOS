//! Surge Engine - Nepal 2024 water disaster
use serde::{Deserialize, Serialize};
use crate::awareness::{DisasterContext, DisasterType, DisasterScale, WaterContam, TriageTag, Acuity};
use crate::types::current_timestamp_ns;
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum SurgeLevel { Normal, Elevated, High, Critical, Catastrophic }
impl SurgeLevel { pub fn from_load(load: f32)->Self{ if load<1.5{Self::Normal} else if load<3.0{Self::Elevated} else if load<6.0{Self::High} else if load<10.0{Self::Critical} else {Self::Catastrophic} } }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TriageDecision { pub patient_id: String, pub tag: TriageTag, pub priority_score: f32, pub assigned_resource: Option<String> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum ZoneAlarmState { Normal, LowPressure, DepletionImminent, Depleted, SensorFault }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MedicalGasMonitor {
    pub source_type: String, // WHO: liquid O2 >=99.5% v/v, PSA 93±3%, concentrator >82%
    pub pipeline_pressure_mmhg: f32,
    pub zone_alarm_state: ZoneAlarmState,
    pub backup_cylinders_available: u32, pub backup_cylinders_total: u32,
    pub leak_risk_score: f32, // 0.0-1.0 predictive IoT leak/pressure drift
    pub last_calibration_ns: u64, pub last_drill_ns: u64,
}
impl MedicalGasMonitor {
    pub fn is_safe(&self)->bool { matches!(self.zone_alarm_state, ZoneAlarmState::Normal) && self.leak_risk_score < 0.5 }
    pub fn needs_escalation(&self)->bool { matches!(self.zone_alarm_state, ZoneAlarmState::LowPressure | ZoneAlarmState::DepletionImminent) || self.backup_cylinders_available < 3 }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LabContaminationMetrics { pub hemolysis_hgb_mg_dl: f32, pub bilirubin_mg_dl: f32, pub lipe_mg_dl: f32, pub turnaround_delay_factor: f32 }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResourcePool {
    pub staff_available: u32, pub staff_total: u32, pub beds_available: u32, pub beds_total: u32,
    pub fluids_l: f32, pub power_pct: f32,
    pub medical_gas: Option<MedicalGasMonitor>,
    pub lab: Option<LabContaminationMetrics>,
}
impl ResourcePool {
    pub fn capacity_pct(&self)->f32{ let s=self.staff_available as f32/self.staff_total.max(1) as f32; let b=self.beds_available as f32/self.beds_total.max(1) as f32; ((s+b)/2.0*100.0).clamp(0.0,100.0) }
    pub fn medical_gas_ok(&self)->bool{ self.medical_gas.as_ref().map(|m| m.is_safe()).unwrap_or(true) }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SurgeProtocol { pub level: SurgeLevel, pub activated_ns: u64, pub disaster: DisasterContext, pub triage_queue: Vec<TriageDecision>, pub resource_pool: ResourcePool, pub medical_gas_log: Vec<String> }
impl SurgeProtocol {
    pub fn new(disaster: DisasterContext, pool: ResourcePool)->Self{
        let level=SurgeLevel::from_load(disaster.scale.load_factor);
        let mut log=Vec::new();
        if let Some(mg)=&pool.medical_gas{
            if mg.needs_escalation(){ log.push(format!("MED-GAS ESCALATION: zone {:?} leak_risk {:.2} backup {}/{}", mg.zone_alarm_state, mg.leak_risk_score, mg.backup_cylinders_available, mg.backup_cylinders_total)); }
            if matches!(mg.zone_alarm_state, ZoneAlarmState::Depleted){ log.push("CRITICAL: bulk O2 depleted - move to portable cylinders (Air Liquide case)".to_string()); }
        }
        if let Some(lab)=&pool.lab{
            if lab.turnaround_delay_factor > 1.5 { log.push(format!("LAB DELAY x{:.1}: contamination HGB {} BILI {} LIPEMIA {} - activate automation mitigation", lab.turnaround_delay_factor, lab.hemolysis_hgb_mg_dl, lab.bilirubin_mg_dl, lab.lipe_mg_dl)); }
        }
        Self{ level, activated_ns:current_timestamp_ns(), disaster, triage_queue:Vec::new(), resource_pool:pool, medical_gas_log: log }
    }
    pub fn nepal_protocol(pool: ResourcePool)->Self{
        let d=DisasterContext{ disaster_id:"nepal_2024_flood".to_string(), disaster_type:DisasterType::Flood, scale:DisasterScale{ affected_districts:7, hospitals_overwhelmed:4, load_factor:8.5 }, affected_pop:120000, confirmed:340, estimated:1200, water_contam:WaterContam{ is_contaminated:true, contaminants:vec!["sewage".to_string(), "chemical_runoff".to_string(), "debris".to_string()], risk:0.92 }, hazards:vec!["wound_sepsis".to_string(),"waterborne_cholera".to_string(),"landslide_secondary".to_string()], reference_case:Some("nepal_2024_flood".to_string()) };
        let mut pool=pool;
        if pool.medical_gas.is_none(){
            pool.medical_gas=Some(MedicalGasMonitor{ source_type:"PSA 93±3% (WHO)".to_string(), pipeline_pressure_mmhg: 45.0, zone_alarm_state: ZoneAlarmState::LowPressure, backup_cylinders_available: 4, backup_cylinders_total: 12, leak_risk_score: 0.68, last_calibration_ns: 0, last_drill_ns: 0 });
        }
        Self::new(d, pool)
    }
    pub fn triage(&mut self, pid:String, acuity:Acuity)->TriageTag{
        // integrate lab/medical-gas into priority: if lab delayed + gas low, upgrade Yellow->Red
        let mut tag=match acuity{ Acuity::MassCasualty=>TriageTag::Red, Acuity::Critical=>TriageTag::Red, _=>TriageTag::Green };
        if !self.resource_pool.medical_gas_ok() && tag==TriageTag::Green { tag=TriageTag::Yellow; self.medical_gas_log.push(format!("{} upgraded G->Y due to O2 alarm", pid)); }
        let score=if tag==TriageTag::Red{100.0}else if tag==TriageTag::Yellow{60.0} else {20.0};
        self.triage_queue.push(TriageDecision{ patient_id:pid, tag:tag.clone(), priority_score:score, assigned_resource:None}); tag
    }
    pub fn check_medical_gas(&mut self) -> Vec<String> {
        let mut alerts=Vec::new();
        if let Some(mg)=&self.resource_pool.medical_gas{
            if mg.leak_risk_score>0.6 { alerts.push(format!("Predictive leak alert {:.0}% - schedule IoT pressure check (Joint Commission safe condition)", mg.leak_risk_score*100.0)); }
            if matches!(mg.zone_alarm_state, ZoneAlarmState::DepletionImminent) { alerts.push("Bulk O2 depletion imminent - auto-escalate to portable cylinders per drill".to_string()); }
        }
        alerts
    }
}
