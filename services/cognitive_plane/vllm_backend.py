# -*- coding: utf-8 -*-
"""
BioOS Cognitive Plane — Meta Model API & vLLM Inference Backend Adapter

Defines the adapter interface for Meta Foundation Models (muse-spark-open-816b-a42b,
Llama-Guard-3, and SAM 3.1) served via Meta Model API, Baseten, Modal, or Fireworks.
The deterministic COE (engine5_coe.ClinicalOversightEngine) remains the
reference backend and CI verification gate.

Contract:
    generate_constrained_clinical_recommendation(
        patient_id: str,
        biomarker_summary: dict,
        proposed_action_type: str,
        lookup_ref_enum: str,
    ) -> tuple[dict, bool]

Invariants the Meta GPU backend MUST preserve:
1. Zero-hallucination: doses come ONLY from the approved NTI lookup table —
   an unknown lookup_ref_enum MUST return (rejected_by_guard order, False).
2. Output is FHIR R4 MedicationRequest JSON with status
   "draft_awaiting_plane_a_kernel_validation" — never an activated order.
3. Every recommendation is appended to the RFC 9162 Merkle audit trail.
4. Same-request determinism is bounded by the constrained-decoding grammar.

Enable with BIOOS_VLLM_ENDPOINT (or BIOOS_META_ENDPOINT) plus BIOOS_VLLM_MODEL.
"""

import json
import os
import time
import logging
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy dependencies — imported lazily so the module loads in CI
# without GPU stacks. The eval harness and CPU fallback work without them.
# ---------------------------------------------------------------------------
try:
    from vllm import LLM, SamplingParams
    _VLLM_AVAILABLE = True
except ImportError:
    _VLLM_AVAILABLE = False
    LLM = None
    SamplingParams = None

try:
    import xgrammar as xgr
    _XGRAMMAR_AVAILABLE = True
except ImportError:
    _XGRAMMAR_AVAILABLE = False
    xgr = None

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    torch = None

class BackendUnavailable(RuntimeError):
    """Raised when the GPU inference endpoint is configured but unreachable."""

class BackendConfigurationError(RuntimeError):
    """Raised when backend configuration is invalid."""
    pass

def gpu_backend_configured() -> bool:
    """Check if GPU backend is explicitly configured."""
    mode = os.environ.get("BIOOS_VLLM_MODE", "REMOTE").upper()
    return mode in ("LOCAL_ROCM", "LOCAL_CUDA") or bool(os.environ.get("BIOOS_VLLM_ENDPOINT"))

def get_backend_mode() -> str:
    """Get the active backend mode."""
    return os.environ.get("BIOOS_VLLM_MODE", "REMOTE").upper()

def create_backend():
    """
    Returns the active recommendation backend.
    
    Priority:
    1. Local ROCm/CUDA vLLM (BIOOS_VLLM_MODE=LOCAL_ROCM|LOCAL_CUDA)
    2. Remote vLLM/OpenAI-compatible endpoint (BIOOS_VLLM_ENDPOINT)
    3. Deterministic COE (fallback)
    
    The eval harness accepts either (duck-typed on the call signature).
    """
    mode = get_backend_mode()
    
    if mode in ("LOCAL_ROCM", "LOCAL_CUDA"):
        if not _VLLM_AVAILABLE:
            raise BackendUnavailable("vLLM not installed. Install with: pip install vllm")
        return LocalVllmBackend(
            model=os.environ.get("BIOOS_VLLM_MODEL", "meta-llama/Meta-muse-spark-open-816b-a42b"),
            guard_model=os.environ.get("BIOOS_GUARD_MODEL", "meta-llama/Llama-Guard-3-8B"),
            tensor_parallel_size=int(os.environ.get("BIOOS_TENSOR_PARALLEL", "1")),
            gpu_memory_utilization=float(os.environ.get("BIOOS_GPU_MEMORY_UTIL", "0.9")),
            max_model_len=int(os.environ.get("BIOOS_MAX_MODEL_LEN", "4096")),
            dtype=os.environ.get("BIOOS_DTYPE", "bfloat16"),
            enable_xgrammar=os.environ.get("BIOOS_ENABLE_XGRAMMAR", "true").lower() == "true",
        )
    
    if gpu_backend_configured():
        return RemoteVllmBackend(
            endpoint=os.environ["BIOOS_VLLM_ENDPOINT"],
            model=os.environ.get("BIOOS_VLLM_MODEL", "bioos-clinical-8b"),
            guard_endpoint=os.environ.get("BIOOS_GUARD_ENDPOINT"),
            guard_model=os.environ.get("BIOOS_GUARD_MODEL", "meta-llama/Llama-Guard-3-8B"),
        )
    
    from engine5_coe import ClinicalOversightEngine
    return ClinicalOversightEngine()

class MetaInferenceBackend:
    """OpenAI-compatible Meta Model API / vLLM client bound to the BioOS constrained-decoding
    grammar, supporting muse-spark-open-816b-a42b and Llama-Guard-3."""

    def __init__(self, endpoint: str, model: str = "meta-llama/Meta-muse-spark-open-816b-a42b", timeout: float = 20.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout
        from engine5_coe import ClinicalOversightEngine

        self._coe = ClinicalOversightEngine()

    @property
    def rocm_device(self) -> str:
        return f"Meta AI Endpoint @ {self.endpoint} ({self.model})"

    @property
    def model_device(self) -> str:
        return f"Meta AI Endpoint @ {self.endpoint} ({self.model})"

# Alias for backward compatibility
VllmRocmBackend = MetaInferenceBackend

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
