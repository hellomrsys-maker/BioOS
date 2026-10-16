# BioOS Compliance Artifacts — Scope & Truthfulness Statement

> **STATUS: ALIGNED TO, NOT CERTIFIED.** These artifacts are *development-stage
> engineering documents* that follow the structure of the named standards. No
> notified body, no FDA submission, and no accredited audit has reviewed them.
> BioOS must not be described as "IEC 62304 compliant", "DO-178C certified", or
> "ISO 14971 compliant" until the corresponding activities are executed under a
> quality management system with independent review.

## Document map

| Artifact | Standard it follows | State |
|---|---|---|
| `ISO_14971_HAZARD_REGISTER.md` | ISO 14971 risk management file (structure) | Starter — 10 hazards, code-linked mitigations, live status |
| `TRACEABILITY_MATRIX.md` | IEC 62304 §5-§9 traceability (structure) | Starter — safety functions req↔design↔code↔test |

## What exists in code today (evidence, not claims)

- Deterministic safety kernel (Rust) with unit tests: CLSI C56-A K+ gate,
  occlusion/air-in-line trips, Dettli ceilings, metformin lockout, Tisdale QTc,
  50 ms watchdog (u64 wrap-safe), 64/128-byte cache-line AMSV ABI.
- Hash-chained append-only audit + RFC 9162 Merkle log (Plane B).
- Kernel-gated FHIR MedicationRequest (advisory-only outputs).

## Missing before ANY clinical claim (Phase 5 gate)

1. QMS (ISO 13485) and design history file
2. Clinical evaluation and intended-use/scope statement (SaMD classification, IMDRF)
3. Independent verification & validation at system level; HIL rig
4. Usability engineering file (IEC 62366-1) and alarm review (IEC 60601-1-8)
5. Security lifecycle file (IEC 81001-5-1) + SBOM + penetration test
6. Post-market surveillance / incident plan
