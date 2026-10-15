//! # BioOS Roche cobas / Sysmex Automated Lab Analyzer Driver
//! Standards: CLSI C56-A, ISO 15189
//! Automated specimen validation with Hemolysis (H), Icterus (I), and Lipemia (L) indices.

pub struct LabAnalyzerDriver {
    pub device_id: u32,
    pub potassium_meq_l: f32,
    pub hemolysis_index_mg_dl: u16,
    pub icterus_index_mg_dl: u16,
    pub lipemia_index_mg_dl: u16,
    pub is_specimen_rejected: bool,
}

impl LabAnalyzerDriver {
    pub const fn new(device_id: u32) -> Self {
        Self {
            device_id,
            potassium_meq_l: 4.2,
            hemolysis_index_mg_dl: 8,
            icterus_index_mg_dl: 2,
            lipemia_index_mg_dl: 15,
            is_specimen_rejected: false,
        }
    }

    /// Ingests serum potassium with CLSI C56-A hemolysis interference gate.
    /// If Hemolysis > 20 mg/dL, specimen is marked REJECTED and potassium reading is strictly invalidated.
    pub fn process_potassium_assay(&mut self, k_raw: f32, h_index: u16) -> Option<f32> {
        self.hemolysis_index_mg_dl = h_index;
        if h_index > 20 {
            self.is_specimen_rejected = true;
            None // REJECTED: Pseudohyperkalemia Risk
        } else {
            self.is_specimen_rejected = false;
            self.potassium_meq_l = k_raw;
            Some(k_raw)
        }
    }
}
