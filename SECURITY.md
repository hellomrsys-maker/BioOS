# Security Overview for BIO.OS Real‑time Collaboration Service

This document describes the security mechanisms that protect the WebSocket
collaboration layer.

## Authentication
* **JWT** – Clients must include a Bearer token when connecting. The token is
  verified using the secret defined by the environment variable `COLLAB_JWT_SECRET`.
* The JWT subject (`sub`) is used as the canonical user identifier throughout
  the service.

## Authorization (OPA ACL)
* A lightweight policy (`policy.py`) maps users to roles (`admin`, `editor`,
  `viewer`).
* The helper `opa_client.eval_policy` is called for each incoming operation
  with `{user, doc_id, action}`.  Write actions are denied for `viewer` role.
* In production you would replace the shim with a real OPA server and a richer
  policy file (`policy.rego`).

## Integrity – HMAC signing
* Every `OperationMessage` can contain a Base64‑encoded HMAC‑SHA256 `signature`
  over the canonical JSON representation of the message (all keys sorted, no
  whitespace).
* The server derives a per‑user HMAC key from the JWT secret (`SHA256(JWT_SECRET
  + user_id)`) and verifies the signature before applying the operation.

## Transport Encryption (TLS)
* The server can run with TLS by passing `--ssl` together with `--cert` and
  `--key` paths.  For local development the supplied script
  `scripts/generate_selfsigned_cert.py` creates a self‑signed certificate stored in
  `certs/`.
* Production deployments should terminate TLS at the edge (Ingress, API‑gateway)
  and provide a proper certificate chain.

## Rate Limiting
* A token‑bucket limiter caps each user to **30 operations per second** and a burst
  up to 30.
* Exceeding the limit results in a `429 Too Many Requests` error.

## Running with TLS (dev)
```bash
python scripts/generate_selfsigned_cert.py  # create dev certs
python -m services.command_center.realtime_collab.server --ssl --cert certs/dev_cert.pem --key certs/dev_key.pem
```

## Auditing & Metrics
* Prometheus counters/ histograms expose connection counts, operation totals,
  and latency (`/metrics` endpoint).

---
Refer to `README.md` for deployment instructions and to the code for exact
implementation details.