//! Awareness Engine - knows what product/object/situation it deals with
//! Handles prime-tissue details, disaster surge, product detection, Plan-Exec-Audit-Prepare-Ready
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::types::current_timestamp_ns;
use crate::human_anatomy::TissueType;
use crate::control_system::SignalType;
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum DealingWith { Product(ProductContext), Tissue(TissueContext), Patient(PatientContext), Disaster(DisasterContext), Unknown { raw: String, conf: f32 } }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct ProductContext { pub product_id: String, pub class: ProductClass, pub confidence: f32 }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum ProductClass { Instrument{ t:String }, Drug{ n:String }, Fluid{ t:String, vol_ml:f32 }, Implant{ t:String }, Unknown }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct TissueContext { pub detected_type: TissueType, pub confidence: f32, pub location: crate::operational_rules::Vector3, pub prime_viability: Option<f32>, pub safe_actions: Vec<String>, pub forbidden: Vec<String> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PatientContext { pub patient_id: String, pub acuity: Acuity, pub phase: PatientPhase }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum Acuity { Stable, Guarded, Critical, Emergent, MassCasualty }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum PatientPhase { PreOp, IntraOp{ proc:String }, PostOp{ hrs:f32 }, EmergencyTriage, DisasterVictim{ disaster_id:String, tag:TriageTag } }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum TriageTag { Green, Yellow, Red, Black, Blue }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct DisasterContext { pub disaster_id: String, pub disaster_type: DisasterType, pub scale: DisasterScale, pub affected_pop: u32, pub confirmed: u32, pub estimated: u32, pub water_contam: WaterContam, pub hazards: Vec<String>, pub reference_case: Option<String> }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum DisasterType { Flood, Landslide, Earthquake, Epidemic, Compound, Unknown }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct DisasterScale { pub affected_districts: u32, pub hospitals_overwhelmed: u32, pub load_factor: f32 }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct WaterContam { pub is_contaminated: bool, pub contaminants: Vec<String>, pub risk: f32 }
#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct WorldModel { pub ts_ns: u64, pub dealing_with: Vec<DealingWith>, pub primary: Option<DealingWith>, pub confidence: f32 }
impl WorldModel { pub fn new()->Self{ Self{ ts_ns: current_timestamp_ns(), dealing_with: Vec::new(), primary: None, confidence: 0.0 } } pub fn is_disaster(&self)->bool{ self.dealing_with.iter().any(|d| matches!(d, DealingWith::Disaster(_))) } pub fn load_factor(&self)->f32{ self.dealing_with.iter().filter_map(|d| match d{ DealingWith::Disaster(c)=>Some(c.scale.load_factor), _=>None}).fold(1.0, f32::max) } }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum StrategyMode { Standard, Precise, Surge, MassCasualty }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct DealingStrategy{ pub mode: StrategyMode, pub priority:String, pub prepare_for: Vec<String> }
