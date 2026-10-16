# -*- coding: utf-8 -*-
"""
BioOS Cognitive Plane — vLLM/ROCm Backend Contract (P3 pre-GPU skeleton)

Defines the adapter interface the real MI300X inference backend must satisfy.
The deterministic COE (engine5_coe.ClinicalOversightEngine) remains the
reference backend and the CI gate; this module exists so the GPU engineer can
implement against a fixed, tested contract WITHOUT changing the harness,
facade, or runtime.

Contract (identical call signature to the deterministic backend):
    generate_constrained_clinical_recommendation(
        patient_id: str,
        biomarker_summary: dict,
        proposed_action_type: str,
        lookup_ref_enum: str,
    ) -> tuple[dict, bool]

Invariants the GPU backend MUST preserve (enforced by the eval harness):
1. Zero-hallucination: doses come ONLY from the approved NTI lookup table —
   an unknown lookup_ref_enum MUST return (rejected_by_guard order, False).
2. Output is FHIR R4 MedicationRequest JSON with status
   "draft_awaiting_plane_a_kernel_validation" — never an activated order.
3. Every recommendation is appended to the RFC 9162 Merkle audit trail.
4. Same-request determinism is NOT required (LLM sampling allowed), but the
   constrained-decoding grammar must bound the output space to the schema.

Enable with BIOOS_VLLM_ENDPOINT (e.g. http://mi300x:8000/v1) plus
BIOOS_VLLM_MODEL. Until set, create_backend() returns the deterministic COE.
"""

import json
import os
import urllib.request
from typing import Any, Dict, Optional, Tuple


class BackendUnavailable(RuntimeError):
    """Raised when the GPU inference endpoint is configured but unreachable."""


def gpu_backend_configured() -> bool:
    return bool(os.environ.get("BIOOS_VLLM_ENDPOINT"))


def create_backend():
    """Returns the active recommendation backend.

    Priority: vLLM/ROCm (when BIOOS_VLLM_ENDPOINT is set) -> deterministic COE.
    The eval harness accepts either (duck-typed on the call signature)."""
    if gpu_backend_configured():
        return VllmRocmBackend(
            endpoint=os.environ["BIOOS_VLLM_ENDPOINT"],
            model=os.environ.get("BIOOS_VLLM_MODEL", "bioos-clinical-8b"),
        )
    from engine5_coe import ClinicalOversightEngine

    return ClinicalOversightEngine()


class VllmRocmBackend:
    """OpenAI-compatible vLLM client bound to the BioOS constrained-decoding
    grammar. P3 IMPLEMENTATION STATUS: request/response plumbing below is the
    contract; XGrammar grammar compilation and the Llama-Guard second pass
    are wired at P3 execution time on MI300X hardware."""

    def __init__(self, endpoint: str, model: str = "bioos-clinical-8b", timeout: float = 20.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout
        # Reuse the deterministic engine's approved table + Merkle tree so the
        # guard invariants and audit trail are IDENTICAL across backends.
        from engine5_coe import ClinicalOversightEngine

        self._coe = ClinicalOversightEngine()

    @property
    def rocm_device(self) -> str:
        return f"vLLM @ {self.endpoint} ({self.model})"

    def generate_constrained_clinical_recommendation(
        self,
        patient_id: str,
        biomarker_summary: Dict[str, Any],
        proposed_action_type: str,
        lookup_ref_enum: str,
    ) -> Tuple[Dict[str, Any], bool]:
        # Guard FIRST against the approved table (invariant 1): unknown tokens
        # are rejected locally WITHOUT a GPU round-trip.
        if lookup_ref_enum not in self._coe.approved_dosing_enums:
            rejected = {
                "resourceType": "MedicationRequest",
                "status": "rejected_by_guard",
                "reason": (
                    f"GUARD VIOLATION: Unregistered dosing token "
                    f"'{lookup_ref_enum}' rejected."
                ),
            }
            self._coe.merkle_tree.append_record({
                "patient_id": patient_id,
                "biomarkers": biomarker_summary,
                "fhir_order": rejected,
                "guard_passed": False,
            })
            return rejected, False

        ref_spec = self._coe.approved_dosing_enums[lookup_ref_enum]
        completion = self._chat_completion(
            system=(
                "You are BioOS clinical CDS. Respond ONLY with JSON matching the "
                "FHIR R4 MedicationRequest schema for the provided lookup token. "
                "Dose and route MUST equal the token specification verbatim."
            ),
            user=json.dumps({
                "patient_id": patient_id,
                "biomarkers": biomarker_summary,
                "action": proposed_action_type,
                "lookup_ref_enum": lookup_ref_enum,
                "token_spec": ref_spec,
            }),
        )
        order, safe = self._validate_against_token(completion, ref_spec)
        self._coe.merkle_tree.append_record({
            "patient_id": patient_id,
            "biomarkers": biomarker_summary,
            "fhir_order": order,
            "guard_passed": safe,
        })
        return order, safe

    def _chat_completion(self, system: str, user: str) -> str:
        """POST to the vLLM OpenAI-compatible chat endpoint; returns content."""
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,  # clinical determinism preference at P3
        }).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint + "/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def _validate_against_token(
        self, completion: str, ref_spec: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """P3 hook: XGrammar-constrained decoding makes schema violations
        structurally impossible; this validator is the defense-in-depth check
        (dose/route must equal the token spec verbatim)."""
        try:
            order = json.loads(completion)
        except json.JSONDecodeError:
            return ({
                "resourceType": "MedicationRequest",
                "status": "rejected_by_guard",
                "reason": "GUARD VIOLATION: model output was not valid JSON.",
            }, False)

        try:
            dose = order["dosageInstruction"][0]["doseAndRate"][0]["doseQuantity"]["value"]
            route = order["dosageInstruction"][0]["route"]["text"]
        except (KeyError, IndexError, TypeError):
            return ({
                "resourceType": "MedicationRequest",
                "status": "rejected_by_guard",
                "reason": "GUARD VIOLATION: output missing dose/route structure.",
            }, False)

        if dose != ref_spec["dose_mg"] or route != ref_spec["route"]:
            return ({
                "resourceType": "MedicationRequest",
                "status": "rejected_by_guard",
                "reason": (
                    f"GUARD VIOLATION: model proposed {dose} mg via {route}; "
                    f"token specifies {ref_spec['dose_mg']} mg via {ref_spec['route']}."
                ),
            }, False)
        return order, True
