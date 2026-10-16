# BioOS Traceability Matrix — IEC 62304 (starter, aligned-to)

Maps safety requirements → design → implementation → verification. Every row
must carry executable evidence. Gaps are listed, not hidden.

| Req ID | Safety requirement | Design element | Implementation | Verification | Status |
|---|---|---|---|---|---|
| REQ-SAFE-001 | Hemolyzed potassium samples (H > 20 mg/dL) MUST be voided, never dosed | ESE K+ gate returns NaN sentinel | `crates/bioos-kernel/src/engine1_ese.rs` | `test_clsi_c56a_potassium_hemolysis_gate`; `/api/kernel/step` e2e | Verified |
| REQ-SAFE-002 | Line occlusion ≥ 525 mmHg MUST trip actuators ≤ 2 ms (SSR) / ≤ 12 ms (mech) | WIE Mealy automaton, dual relay model | `engine4_wie.rs`, `engine1_ese.rs` | `test_pump_occlusion_and_air_bubble_trips`, `test_wie_watchdog_relay_trip_and_heartbeat_timeout` | Verified |
| REQ-SAFE-003 | Air-in-line ≥ 25 µL MUST trip as H-02 | Same interlock path | `engine1_ese.rs` | same as REQ-SAFE-002 | Verified |
| REQ-SAFE-004 | Loss of Plane B heartbeat > 50 ms MUST lock out; must be wrap-safe; future timestamps fail-safe | u64 monotonic watchdog | `engine4_wie.rs::evaluate_cycle`, `ffi.rs::bioos_kernel_step` (u64 FFI) | `test_wie_watchdog_relay_trip_and_heartbeat_timeout`, `test_wie_watchdog_u64_time_base_wrap_safety` | Verified 2026-10-16 |
| REQ-SAFE-005 | Metformin MUST be absolutely locked out at eGFR < 30 | PVE NTI lockout | `engine3_pve.rs` + FFI `bioos_verify_metformin` | `test_metformin_hard_lockout_at_low_egfr`; FHIR path `test_fhir_medication_request_kernel_lockout` | Verified |
| REQ-SAFE-006 | Tisdale score ≥ 11 MUST hard-lockout QTc-prolonging orders | PVE Tisdale model | `engine3_pve.rs` | `test_tisdale_qtc_risk_lockout` | Verified |
| REQ-SAFE-007 | No Plane B output may actuate hardware | Advisory-only facade; orders stay `draft` | `fhir_facade.py::create_medication_request` | `test_fhir_medication_request_kernel_lockout` asserts `status == "draft"` | Verified (structural) |
| REQ-SAFE-008 | Audit history MUST be tamper-evident | Hash-chained append-only log + Merkle tree | `services/command_center/audit_store.py`, `engine5_coe.py` | `test_audit_chain_tamper_detection`, `test_engine5_coe` | Verified |
| REQ-SAFE-009 | Clinical state MUST be exposed as standards-coded FHIR (LOINC/RxNorm) | FHIR R4 facade | `fhir_facade.py` | `test_fhir_patient_and_observation_mapping` | Verified (starter coding set) |
| REQ-SAFE-010 | HL7 v2 interface messages MUST be receipt-audited, never auto-acted upon | MLLP stub → audit chain | `hl7_mllp.py` + runtime wiring | `test_mllp_tcp_roundtrip`, `test_mllp_receipt_lands_in_audit_chain` | Verified (stub scope) |
| REQ-SAFE-011 | Real-time budgets MUST be measured, not asserted | WCET harness | `services/wcet_benchmark.py` | kernel_step p99 8.1 µs (Win) / 16.9 µs (container) vs 100 µs budget | Verified (host-level) |
| REQ-SAFE-012 | Closed-loop rate changes MUST respect hemodynamic envelope (MAP ≥ 55, slew ≤ 2.5 mL/h/s) | Kalman envelope + alpha-floor | `engine_envelope.rs` | `test_kalman_envelope_and_alpha_floor` | Verified (sim level) |
| REQ-SAFE-013 | Deterioration MUST be scored per RCP NEWS2 (both SpO2 scales, single-param-3 rule) and trended per published trajectory rules (rise ≥ 2, sustained ≥ 3, ≥ 7 emergency) | ews_engine + ews_trend | `services/command_center/ews_engine.py`, `ews_trend.py`, runtime observation endpoint | `test_ews_engine.py` (13 golden vectors), `test_ews_trend.py` (8 trajectory tests); route `/api/clinical/news2/*` | Verified 2026-10-16 |
| REQ-SAFE-014 | Bearer tokens MUST verify against the hospital OIDC provider (RS256/JWKS) with iss/aud/exp/nbf enforcement; dev tokens MUST be isolated when OIDC is enforced | oidc_auth + rbac_auth resolution order | `services/oidc_auth.py`, `rbac_auth.py::authenticate_request` | `test_oidc_auth.py` (mock IdP: E2E, tamper, expiry, foreign-issuer, unknown-kid, audience, role mapping, integration) | Verified 2026-10-16 |

## Known traceability gaps (to close in P2-P5)

- No system-level V&V on real or simulated hardware (HIL rig) — REQ-SAFE-002/003/012 verified at unit level only
- No requirement numbers exist upstream of this matrix (requirements document itself is a gap)
- Usability/alarm requirements (IEC 60601-1-8, 62366-1) not yet represented
- COE stub: REQ-SAFE-007 verified structurally, not against a real model
