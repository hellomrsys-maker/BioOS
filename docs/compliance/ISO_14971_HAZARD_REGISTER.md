# BioOS Hazard Register — ISO 14971 (starter, aligned-to)

**Scope:** software hazards of the BioOS tri-plane architecture as implemented in this repository.
**Method:** qualitative severity (S 1-5, 5 = death) × probability (P 1-5, 5 = frequent). Acceptability gate: no hazard with S≥4 may retain P≥2 without an implemented, tested mitigation.
**Rule:** every mitigation row MUST link to code and a passing test. "Implemented" without a test link = not accepted.

| ID | Hazard (effect) | Cause | S | P | Mitigation (code → test) | Status |
|---|---|---|---|---|---|---|
| H-01 | Pseudohyperkalemic cardiac arrest from hemolyzed K+ sample treated as real | Hemolysis index H > 20 mg/dL not gated | 5 | 2 | CLSI C56-A gate voids K+ to NaN (`engine1_ese.rs::validate_potassium` → `test_clsi_c56a_potassium_hemolysis_gate`) | Mitigated (kernel-tested) |
| H-02 | Undetected infusion line occlusion → pressure injury / no-flow | Downstream pressure ≥ 525 mmHg ignored | 4 | 2 | Hard trip + relay action (`engine1_ese.rs`, `engine4_wie.rs` → `test_pump_occlusion_and_air_bubble_trips`) | Mitigated (kernel-tested) |
| H-03 | Air embolism from air-in-line ≥ 25 µL | Ultrasonic sensor reading not interlocked | 5 | 1 | Hard trip at ≥ 25 µL (same path as H-02 → same test) | Mitigated (kernel-tested) |
| H-04 | Actuator runaway when Plane B (AI) hangs or hallucinates | Missing supervision deadline | 5 | 2 | 50 ms heartbeat watchdog + hardware lockout, u64 wrap-safe (`engine4_wie.rs` → `test_wie_watchdog_relay_trip_and_heartbeat_timeout`, `test_wie_watchdog_u64_time_base_wrap_safety`) | Mitigated (kernel-tested) |
| H-05 | Fatal lactic acidosis: metformin at eGFR < 30 | NTI order not interlocked at kernel level | 5 | 2 | Absolute lockout in kernel (`engine3_pve.rs` → `test_metformin_hard_lockout_at_low_egfr`); FHIR orders gated via `bioos_verify_metformin` (`fhir_facade.py` → `test_fhir_medication_request_kernel_lockout`) | Mitigated (kernel-tested) |
| H-06 | Torsades de pointes from QTc-prolonging co-administration | Tisdale score not evaluated | 4 | 2 | Tisdale score ≥ 11 hard lockout (`engine3_pve.rs` → `test_tisdale_qtc_risk_lockout`) | Mitigated (kernel-tested) |
| H-07 | Hallucinated drug/dose reaches clinical use | LLM free-text output treated as order | 5 | 3 | Constrained NTI lookup rejects unknown refs (`engine5_coe.py` → `test_engine5_coe`); FHIR orders always `status=draft` + kernel verdict extension (`fhir_facade.py` → lockout test) | Partially mitigated — real model wiring still a stub (P3) |
| H-08 | Silent tampering with clinical audit history | Mutable log storage | 3 | 3 | Hash-chained append-only log + RFC 9162 Merkle tree (`audit_store.py` → `test_audit_chain_tamper_detection`) | Mitigated (tested) |
| H-09 | Watchdog mis-times heartbeat across clock wrap (missed OR spurious lockout) | u32 ns base wraps every 4.29 s; `saturating_sub` made future stamps look fresh (fail-unsafe) | 4 | 3 | u64 monotonic base + `wrapping_sub`; future stamps trip lockout (`engine4_wie.rs`, `ffi.rs` → `test_wie_watchdog_u64_time_base_wrap_safety`) | **Fixed 2026-10-16** (tested) |
| H-10 | Critical alarm missed due to alarm fatigue | Nuisance-alarm flood | 4 | 3 | Nuisance-alarm suppression + clinician cognitive-load engine (`wellbeing_engine.py` → `test_wellbeing_engine`) | Partial — human-factors validation outstanding (IEC 62366-1) |
| H-11 | Deterioration under-scored: hypoxemic/obtunded patient scored as room-air/Alert | Census record lacks O2-supplement and ACVPU fields; convenience scoring defaults them | 4 | 3 | Observation endpoint REQUIRES explicit overrides, flags every defaulted field for audit (`bioos_runtime.py::clinical_news2_observation` → `defaults_used` response field); hazard documented at the scoring function itself (`ews_engine.py::news2_from_patient`) | Mitigated at API level (2026-10-16); usability validation outstanding |
| H-12 | NEWS2 misimplementation drives wrong escalation (e.g., wrong SpO2 scale, missed single-param-3 rule) | Hand-rolled scoring drift from published chart | 4 | 2 | Scoring implemented strictly from the published RCP chart + 13 hand-computed golden boundary vectors independent of the implementation (`ews_engine.py` → `test_ews_engine.py`) | Mitigated (golden-vector tested) |
| H-13 | Deterioration missed between scheduled observations (static point-in-time scoring) | No trajectory analysis; a slow rise never crosses any single-observation threshold | 4 | 3 | Trend monitor implements published trajectory rules: rise ≥ 2 → urgent review, sustained ≥ 3 → escalation review, ≥ 7 → emergency (`ews_trend.py` → `test_ews_trend.py`); trajectory alerts → audit chain via observation endpoint | Mitigated (tested) |
| H-14 | Unauthorized clinical API access with forged identity | Weak bearer-token validation | 4 | 2 | OIDC RS256 verification against hospital IdP JWKS (RFC 8017, pure stdlib) + claims enforcement + least-privilege role mapping; dev HS256 path provably isolated when OIDC enforced (`oidc_auth.py`, `rbac_auth.py` → `test_oidc_auth.py` incl. tamper/expiry/foreign-issuer/unknown-kid) | Mitigated (tested against local mock IdP); production IdP integration P5 |

## Residual-risk statement (starter)

Residual risk is NOT yet acceptable for clinical deployment: H-07 requires the
real inference plane (P3); H-10 requires formal usability engineering (P5); the
kernel is not yet on a certified RTOS target (P2). Re-evaluate after each phase.
