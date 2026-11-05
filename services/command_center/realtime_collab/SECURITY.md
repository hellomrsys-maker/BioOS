# Real‑time Collaboration Security Layer

This package implements three essential security concerns for the collaboration
service:

1. **Policy enforcement** – decision whether a user can perform a given action on
   a document.
2. **Rate‑limiting** – protects the WebSocket channel from abuse (token bucket).
3. **Message integrity** – HMAC‑SHA256 signatures verify that the client really
   generated the operation payload.

## Public façade (`security.py`)

All server code should import the helpers from the façade rather than the
individual modules:

```python
from services.command_center.realtime_collab.security import (
    eval_policy,
    allow_op,
    verify_signature,
)
```

The façade simply re‑exports the concrete implementations and provides a stable
import location.  This makes future refactoring (e.g., swapping the OPA backend) a
non‑breaking change for the rest of the codebase.

### `eval_policy`

*Input*: a ``dict`` containing ``user``, ``doc_id`` and ``action``.

*Behaviour*: attempts to run the **OPA** binary (`opa eval`) against the bundled
`policy.rego`. If the binary is missing or the evaluation fails, it falls back to
the lightweight pure‑Python policy defined in `policy.py`.

### `allow_op`

Rate‑limits CRDT operations per user (default 4 ops/sec with a burst of 40). The
implementation lives in `rate_limiter.py` and can be swapped for a Redis‑backed
solution if needed.

### `verify_signature`

Verifies a base64‑encoded HMAC‑SHA256 signature over the *canonical* JSON
representation (sorted keys, no whitespace). The per‑user key is derived from the
global JWT secret.

---

## Running the real OPA binary (optional)

If you have the OPA executable installed and want to use the full Rego policy,
ensure it is available on ``PATH``. The binary will be invoked automatically – the
fallback is only used when the call fails.

```bash
# Example installation on macOS / Linux
curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static
chmod +x opa
mv opa /usr/local/bin/opa
```

The bundled `policy.rego` mirrors the simple role‑based mapping used by the
fallback Python implementation, so behaviour is identical whether OPA is used or
not.

---

## Testing

The test suite covers:

* Policy success/failure paths (`test_security_helpers.py`).
* Rate‑limit exhaustion and refill.
* HMAC signature generation and verification.
* **OPA fallback** – a dedicated test forces the subprocess call to raise a
  ``FileNotFoundError`` and asserts that the Python policy is used instead.

Run the full suite with:

```bash
pytest -q
```

---

## Extending the policy

To add more granular permissions, edit `policy.rego` and/or `policy.py`. The
fallback Python version should stay in sync with the Rego rules to avoid
inconsistencies.

---

*Generated on `2026‑10‑19` as part of the BioOS security hardening effort.*
