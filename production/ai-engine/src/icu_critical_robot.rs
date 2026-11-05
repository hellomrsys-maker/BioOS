//! ICU Critical Robot - Beyond OR, 10-bed systematic
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::awareness::{PatientContext, Acuity};
use crate::control_system::{SignalType, RawSignal};
use crate::control_theory::{TransferFunction, StabilityAnalyzer};
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum StaffRole { StaffNurse, HeadNurse, JuniorDoctor, Attending, CriticalRobot }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BedAssignment { pub bed_id: String, pub patient: Option<PatientContext> }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ICU10Room { pub room_id: String, pub beds: Vec<BedAssignment> }
impl ICU10Room { pub fn new(id:String)->Self{ let beds=(1..=10).map(|i| BedAssignment{bed_id:format!("bed_{}",i), patient:None}).collect(); Self{ room_id:id, beds } } pub fn load_factor(&self)->f32{ self.beds.iter().filter_map(|b| b.patient.as_ref()).map(|p| match p.acuity{ Acuity::Stable=>1.0, Acuity::Guarded=>2.0, Acuity::Critical=>4.0, _=>5.0}).sum::<f32>()/2.0 } }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ConditionalTrigger { pub name:String, pub signal:SignalType, pub threshold:f32 }
impl ConditionalTrigger { pub fn evaluate(&self, vitals: &HashMap<SignalType,f32>)->bool{ vitals.get(&self.signal).map(|&v| v < self.threshold).unwrap_or(false) } }
pub fn base_icu_triggers()->Vec<ConditionalTrigger>{ vec![ConditionalTrigger{name:"hypotension".to_string(), signal:SignalType::ArterialPressure, threshold:65.0}, ConditionalTrigger{name:"hypoxia".to_string(), signal:SignalType::SpO2, threshold:90.0}] }
pub struct CriticalRobot { pub id:String }
impl CriticalRobot { pub fn new(id:String)->Self{ Self{id} } pub fn analyse_and_call(&self, bed:&str, vitals: &HashMap<SignalType,f32>)->Option<String>{ for t in base_icu_triggers(){ if t.evaluate(vitals){ let tf=TransferFunction::first_order(1.0,0.5); if !StabilityAnalyzer::is_stable_den(&tf.den){ continue; } return Some(format!("CALL {} {}", bed, t.name)); } } None } }
