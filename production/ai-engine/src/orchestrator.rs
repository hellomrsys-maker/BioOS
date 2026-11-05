//! Orchestrator - ONE Artificial with 5 Sub-Agents PEAP-Ready
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use crate::types::current_timestamp_ns;
use crate::awareness::{WorldModel, StrategyMode};
use crate::control_system::initialize_standard_safety_boundaries;
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum SubAgentRole { Doctor, Researcher, Engineer, Nurse, Biologist }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct SubAgentTask { pub id: String, pub role: SubAgentRole, pub instruction: String }
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum PEAPPhase { Plan, Exec, Audit, Prepare, Ready }
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PEAPCycle { pub phase: PEAPPhase, pub world: WorldModel }
impl PEAPCycle { pub fn new(w:WorldModel)->Self{ Self{ phase:PEAPPhase::Plan, world:w } } }
pub struct Orchestrator { pub cycle: PEAPCycle }
impl Orchestrator { pub fn new(w:WorldModel)->Self{ Self{ cycle:PEAPCycle::new(w) } } pub fn run_cycle(&mut self){ self.cycle.phase=PEAPPhase::Exec; } }
