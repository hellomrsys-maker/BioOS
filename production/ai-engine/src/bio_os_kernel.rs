//! BioOS Kernel - War OS
use crate::awareness::{WorldModel, DealingWith};
use crate::awareness_engine::AwarenessEngine;
use crate::control_theory::{TransferFunction, StabilityAnalyzer};
use crate::communication_fabric::CommunicationFabric;
use crate::orchestrator::Orchestrator;
use crate::surge_engine::{SurgeProtocol, ResourcePool};
use crate::post_care::{PostCareEngine, PostCarePlan};
use crate::awareness::PatientContext;
use serde::{Deserialize, Serialize};
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KernelTick { pub ts_ns: u64, pub load_factor: f32, pub surge_active: bool, pub ready: bool }
impl KernelTick { pub fn is_war_mode(&self)->bool{ self.surge_active && self.load_factor>5.0 } }
pub struct BioOSKernel { pub awareness: AwarenessEngine, pub orchestrator: Option<Orchestrator>, pub comms: CommunicationFabric, pub surge: Option<SurgeProtocol>, pub tick_count: u64 }
impl BioOSKernel {
    pub fn new()->Self{ Self{ awareness: AwarenessEngine::new(), orchestrator: None, comms: CommunicationFabric::new(), surge: None, tick_count: 0 } }
    pub fn tick(&mut self, vision: Option<String>, manual: Option<String>)->KernelTick{
        let world=self.awareness.detect(vision, manual); let load=world.load_factor();
        let tf=TransferFunction::first_order(1.0, 0.5); assert!(StabilityAnalyzer::is_stable_den(&tf.den));
        let mut orch=Orchestrator::new(world.clone()); orch.run_cycle(); let ready=orch.is_ongo_ready();
        self.orchestrator=Some(orch);
        if load>3.0{ let pool=ResourcePool{ staff_available:4, staff_total:20, beds_available:2, beds_total:20, fluids_l:12.0, power_pct:30.0 }; self.surge=Some(SurgeProtocol::nepal_protocol(pool)); }
        self.tick_count+=1; KernelTick{ ts_ns: crate::types::current_timestamp_ns(), load_factor:load, surge_active:self.surge.is_some(), ready }
    }
    pub fn surge_activate_nepal(&mut self){ let pool=ResourcePool{ staff_available:4, staff_total:20, beds_available:2, beds_total:20, fluids_l:12.0, power_pct:30.0 }; self.surge=Some(SurgeProtocol::nepal_protocol(pool)); }
    pub fn post_care_plan(&self, patient: &PatientContext)->PostCarePlan{ PostCareEngine::plan_for(patient) }
}
