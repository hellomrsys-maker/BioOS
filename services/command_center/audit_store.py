# -*- coding: utf-8 -*-
"""
BioOS Persistence & Append-Only Audit Store
Standards: RFC 9162-style hash chaining, IEC 62304 Class C traceability

SQLite-backed (WAL mode) store for:
1. Telemetry time-series streamed from the Plane A AMSV (append-only)
2. Tamper-evident hash-chained audit log (complements the Engine 5 RFC 9162
   Merkle tree: the chain gives per-entry tamper detection, the Merkle tree
   gives external notarization of the cognitive plane)
3. FHIR R4 Subscription registry (webhook endpoints)

Zero third-party dependencies (stdlib sqlite3).
"""

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_GENESIS_HASH = "0" * 64

_TELEMETRY_KEYS = (
    "ts_ns", "device_class", "metric_code", "value_x1000",
    "quality_flags", "limit_state", "alarm_class",
)
_AUDIT_KEYS = (
    "id", "ts_ns", "actor", "action", "resource_type",
    "resource_id", "payload_hash", "prev_entry_hash", "entry_hash",
)


class BioOsPersistenceStore:
    """Thread-safe SQLite persistence for telemetry, audit chain, subscriptions."""

    def __init__(self, db_path: str = "data/bioos_runtime.db"):
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_ns INTEGER NOT NULL,
                    device_class INTEGER NOT NULL,
                    metric_code INTEGER NOT NULL,
                    value_x1000 INTEGER NOT NULL,
                    quality_flags INTEGER NOT NULL,
                    limit_state INTEGER NOT NULL,
                    alarm_class INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry (ts_ns, metric_code)"
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_ns INTEGER NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    prev_entry_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL UNIQUE
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fhir_subscriptions (
                    id TEXT PRIMARY KEY,
                    criteria TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_ts_ns INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clinical_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_ns INTEGER NOT NULL,
                    patient_id TEXT NOT NULL,
                    total_score INTEGER NOT NULL,
                    band TEXT NOT NULL,
                    on_supplemental_oxygen INTEGER NOT NULL,
                    spo2_scale INTEGER NOT NULL,
                    is_alert INTEGER NOT NULL,
                    defaults_used TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_clinical_obs ON clinical_observations (patient_id, ts_ns)"
            )

    # ---------------- telemetry time-series ----------------

    def append_telemetry(
        self,
        ts_ns: int,
        device_class: int,
        metric_code: int,
        value_x1000: int,
        quality_flags: int,
        limit_state: int,
        alarm_class: int,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO telemetry (ts_ns, device_class, metric_code, value_x1000,"
                " quality_flags, limit_state, alarm_class) VALUES (?,?,?,?,?,?,?)",
                (int(ts_ns), int(device_class), int(metric_code), int(value_x1000),
                 int(quality_flags), int(limit_state), int(alarm_class)),
            )

    def query_telemetry(
        self,
        since_ns: int = 0,
        until_ns: Optional[int] = None,
        metric_code: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT ts_ns, device_class, metric_code, value_x1000, quality_flags,"
            " limit_state, alarm_class FROM telemetry WHERE ts_ns >= ?"
        )
        params: List[Any] = [int(since_ns)]
        if until_ns is not None:
            sql += " AND ts_ns <= ?"
            params.append(int(until_ns))
        if metric_code is not None:
            sql += " AND metric_code = ?"
            params.append(int(metric_code))
        sql += " ORDER BY ts_ns ASC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(zip(_TELEMETRY_KEYS, r)) for r in rows]

    def telemetry_count(self) -> int:
        with self._lock:
            (count,) = self._conn.execute("SELECT COUNT(*) FROM telemetry").fetchone()
        return int(count)

    # ---------------- hash-chained append-only audit ----------------

    @staticmethod
    def _payload_sha256(payload: Any) -> str:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _entry_hash(
        prev_hash: str, ts_ns: int, actor: str, action: str,
        resource_type: str, resource_id: str, payload_hash: str,
    ) -> str:
        block = "|".join([
            prev_hash, str(ts_ns), actor, action, resource_type, resource_id, payload_hash,
        ])
        return hashlib.sha256(block.encode("utf-8")).hexdigest()

    def append_audit_entry(
        self,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Appends a tamper-evident entry: entry_hash covers the previous
        entry hash, so any mutation of history breaks the chain."""
        with self._lock:
            row = self._conn.execute(
                "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = row[0] if row else _GENESIS_HASH
        ts_ns = time.time_ns()
        payload_hash = self._payload_sha256(payload if payload is not None else {})
        entry_hash = self._entry_hash(
            prev_hash, ts_ns, actor, action, resource_type, resource_id, payload_hash,
        )
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO audit_log (ts_ns, actor, action, resource_type, resource_id,"
                " payload_hash, prev_entry_hash, entry_hash) VALUES (?,?,?,?,?,?,?,?)",
                (ts_ns, actor, action, resource_type, resource_id,
                 payload_hash, prev_hash, entry_hash),
            )
            entry_id = cur.lastrowid
        return {
            "id": entry_id,
            "ts_ns": ts_ns,
            "prev_entry_hash": prev_hash,
            "entry_hash": entry_hash,
        }

    def verify_audit_chain(self) -> Dict[str, Any]:
        """Recomputes the whole chain; returns validity plus the first broken id."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts_ns, actor, action, resource_type, resource_id,"
                " payload_hash, prev_entry_hash, entry_hash FROM audit_log ORDER BY id ASC"
            ).fetchall()
        prev = _GENESIS_HASH
        for row in rows:
            entry_id, ts_ns, actor, action, rtype, rid, payload_hash, prev_entry, entry_hash = row
            if prev_entry != prev:
                return {"valid": False, "entries": len(rows), "first_bad_id": entry_id,
                        "reason": "broken_prev_link"}
            expected = self._entry_hash(prev_entry, ts_ns, actor, action, rtype, rid, payload_hash)
            if expected != entry_hash:
                return {"valid": False, "entries": len(rows), "first_bad_id": entry_id,
                        "reason": "hash_mismatch"}
            prev = entry_hash
        return {"valid": True, "entries": len(rows), "first_bad_id": None, "reason": None}

    def recent_audit(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts_ns, actor, action, resource_type, resource_id,"
                " payload_hash, prev_entry_hash, entry_hash FROM audit_log"
                " ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(zip(_AUDIT_KEYS, r)) for r in rows]

    def audit_count(self) -> int:
        with self._lock:
            (count,) = self._conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        return int(count)

    # ---------------- FHIR Subscription registry ----------------

    def add_subscription(self, criteria: str, endpoint: str, status: str = "ACTIVE") -> Dict[str, Any]:
        sub_id = uuid.uuid4().hex[:16]
        created = time.time_ns()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO fhir_subscriptions (id, criteria, endpoint, status, created_ts_ns)"
                " VALUES (?,?,?,?,?)",
                (sub_id, criteria, endpoint, status, created),
            )
        return {"id": sub_id, "criteria": criteria, "endpoint": endpoint,
                "status": status, "created_ts_ns": created}

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, criteria, endpoint, status, created_ts_ns FROM fhir_subscriptions"
            ).fetchall()
        return [
            {"id": r[0], "criteria": r[1], "endpoint": r[2], "status": r[3], "created_ts_ns": r[4]}
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------- Clinical observations (NEWS2 time-series) ----------------

    def append_clinical_observation(
        self,
        ts_ns: int,
        patient_id: str,
        total_score: int,
        band: str,
        on_supplemental_oxygen: bool,
        spo2_scale: int,
        is_alert: bool,
        defaults_used: Dict[str, Any],
    ) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO clinical_observations (ts_ns, patient_id, total_score, band,"
                " on_supplemental_oxygen, spo2_scale, is_alert, defaults_used)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (int(ts_ns), patient_id, int(total_score), band,
                 int(bool(on_supplemental_oxygen)), int(spo2_scale),
                 int(bool(is_alert)), json.dumps(defaults_used)),
            )
            return cur.lastrowid

    def query_clinical_observations(
        self, patient_id: Optional[str] = None, limit: int = 500
    ) -> List[Dict[str, Any]]:
        base = ("SELECT id, ts_ns, patient_id, total_score, band, on_supplemental_oxygen,"
                " spo2_scale, is_alert, defaults_used FROM clinical_observations")
        if patient_id is not None:
            rows = self._conn.execute(
                base + " WHERE patient_id = ? ORDER BY ts_ns ASC LIMIT ?",
                (patient_id, int(limit)),
            ).fetchall()
        else:
            rows = self._conn.execute(
                base + " ORDER BY ts_ns ASC LIMIT ?", (int(limit),)
            ).fetchall()
        result = []
        for r in rows:
            entry = dict(zip(
                ("id", "ts_ns", "patient_id", "total_score", "band",
                 "on_supplemental_oxygen", "spo2_scale", "is_alert", "defaults_used"),
                r,
            ))
            try:
                entry["defaults_used"] = json.loads(entry["defaults_used"])
            except Exception:
                entry["defaults_used"] = {}
            result.append(entry)
        return result
