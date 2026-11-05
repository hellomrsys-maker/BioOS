//! AI Engine - Plane B: AI Surgical Intelligence

pub mod types;
pub mod inference;
pub mod vision;
pub mod planning;
pub mod validation;

// New safety-critical modules
pub mod screening_types;
pub mod validators;
pub mod llama_guard_validator;
pub mod constrained_validator;
pub mod math_validator;
pub mod cross_validator;
pub mod uncertainty_quantifier;
pub mod screening_engine;
pub mod workflow_optimizer;
pub mod criticality_types;
pub mod operational_rules;
pub mod operational_rules_engine;
pub mod procedure_definitions;
pub mod emergency_protocols;
pub mod human_anatomy;
pub mod clinical_data;
pub mod clinical_data_comprehensive;
pub mod control_system;
pub mod awareness;
pub mod awareness_engine;
pub mod orchestrator;
pub mod surge_engine;
pub mod post_care;
pub mod control_theory;
pub mod communication_fabric;
pub mod bio_os_kernel;
pub mod icu_critical_robot;
pub mod mission_critical_layer;
pub mod gaps_engine;
pub mod consistency_control;
pub mod hal;
pub mod real_time_data;
pub mod real_time_writer;
pub mod telemetry;

pub use inference::*;
pub use vision::*;
pub use planning::*;
pub use validation::*;

// Re-export new modules
pub use screening_engine::*;
pub use workflow_optimizer::*;
pub use operational_rules::*;
pub use operational_rules_engine::*;
pub use procedure_definitions::*;
pub use emergency_protocols::*;
pub use human_anatomy::*;
pub use clinical_data::*;
pub use clinical_data_comprehensive::*;
pub use control_system::*;
pub use awareness::*;
pub use awareness_engine::*;
pub use orchestrator::*;
pub use surge_engine::*;
pub use post_care::*;
pub use control_theory::*;
pub use communication_fabric::*;
pub use bio_os_kernel::*;
pub use icu_critical_robot::*;
pub use mission_critical_layer::*;
pub use gaps_engine::*;
pub use consistency_control::*;
pub use hal::*;