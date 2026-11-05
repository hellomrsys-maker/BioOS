"""Thin wrapper that mimics an OPA evaluation call.

The real BioOS platform would ship an OPA binary and evaluate a Rego policy.
For this code‑base we delegate to the pure‑Python ``policy`` module above, which
behaves like an OPA decision point.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict

# Fallback pure‑Python implementation (used when OPA binary is unavailable)
from .policy import allow as _policy_allow

# Path to a minimal Rego policy bundled with the repository.  If this file is
# missing the client will automatically fall back to the pure‑Python helper.
_OPA_POLICY_PATH = Path(__file__).with_name("policy.rego")


def _run_opa_eval(input_data: Dict) -> bool:
    """Run ``opa eval`` with the bundled Rego policy.

    Returns ``True`` if the policy allows the operation, ``False`` otherwise.
    If the ``opa`` executable is not found or the evaluation fails, a
    ``RuntimeError`` is raised so the caller can decide on a fallback.
    """
    if not _OPA_POLICY_PATH.is_file():
        raise RuntimeError("OPA policy file not found")

    # Build the subprocess command. ``-i -`` reads JSON from stdin.
    cmd = [
        "opa",
        "eval",
        "-i",
        "-",
        "-d",
        str(_OPA_POLICY_PATH),
        "data.realtime_collab.allow",
    ]
    try:
        completed = subprocess.run(
            cmd,
            input=json.dumps(input_data).encode(),
            capture_output=True,
            check=True,
            timeout=5,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("OPA binary not found") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"OPA evaluation failed: {exc.stderr.decode()}") from exc

    # ``opa eval`` prints a JSON result like {"result": [{"expressions": [{"value": true}]}]}
    try:
        out_json = json.loads(completed.stdout)
        return bool(out_json["result"][0]["expressions"][0]["value"])
    except Exception as exc:
        raise RuntimeError("Unexpected OPA output format") from exc


def eval_policy(input_data: Dict) -> bool:
    """Evaluate the ACL policy.

    ``input_data`` must contain the keys ``user``, ``doc_id`` and ``action``.
    The function first attempts to use the OPA binary with the bundled Rego
    policy.  If OPA is unavailable or the policy file is missing, it falls back
    to the pure-Python implementation defined in ``policy.py``.
    """
    required = {"user", "doc_id", "action"}
    if not required.issubset(input_data):
        raise ValueError(
            f"Missing required fields for policy evaluation: {required - set(input_data)}"
        )

    try:
        return _run_opa_eval(input_data)
    except RuntimeError:
        # Fallback to the lightweight Python implementation.
        return _policy_allow(
            input_data["user"], input_data["doc_id"], input_data["action"]
        )