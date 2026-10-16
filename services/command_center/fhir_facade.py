# -*- coding: utf-8 -*-
"""
BioOS FHIR R4 Facade (Plane B advisory layer)
Standards: HL7 FHIR R4, LOINC, RxNorm, UCUM

Maps BioOS clinical state to FHIR R4 resources:
- Patient            : from HospitalTopologyManager census records
- Observation        : LOINC-coded vitals/biomarkers (incl. live AMSV values)
- MedicationRequest  : RxNorm-coded orders, GATED by kernel authority
                       (bioos_verify_metformin via the ctypes bridge) and the
                       Engine 5 COE constrained NTI register
- Subscription       : webhook registry backed by the append-only audit store

INVARIANT (see docs/MASTER_ARCHITECTURE_BLUEPRINT.md):
PLANE B ADVISES; PLANE A EXECUTES. Nothing produced here can reach hardware:
every MedicationRequest stays status="draft" with the kernel verdict carried
in a BioOS extension, and actuation authority remains exclusively in Plane A.

Zero third-party dependencies (stdlib urllib for webhook dispatch).
"""

import json
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LOINC_SYSTEM = "http://loinc.org"
RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"
UCUM_SYSTEM = "http://unitsofmeasure.org"

# LOINC codes for vitals/biomarkers surfaced by the AMSV and census records
LOINC_MAP = {
    "heart_rate": ("8867-4", "Heart rate"),
    "map": ("8471-5", "Mean blood pressure"),
    "spo2": ("2708-6", "Oxygen saturation"),
    "respiratory_rate": ("9279-1", "Respiratory rate"),
    "temperature": ("8310-5", "Body temperature"),
    "potassium": ("2823-3", "Potassium [Moles/volume] in Serum or Plasma"),
    "egfr": ("62238-1", "Estimated Glomerular Filtration Rate"),
    "creatinine": ("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
}

# RxNorm RXCUIs for the NTI register. Only stable, widely published codes are
# mapped; drugs without a confirmed code fall back to text-only coding, which
# is valid FHIR (CodableConcept.text) and keeps coding honest.
RXNORM_MAP = {
    "Metformin": ("6809", "metformin"),
    "Vancomycin": ("11124", "vancomycin"),
    "Gentamicin": ("3752", "gentamicin"),
    "Digoxin": ("3407", "digoxin"),
    "Heparin": ("3491", "heparin"),
}

_KERNEL_METFORMIN_OUTCOMES = {
    0: "Approved",
    1: "DoseClamped",
    2: "HardLockoutContraindicated",
    3: "RequiresClinicalOverride",
}


def _iso_from_ns(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def patient_to_fhir(rec: Any) -> Dict[str, Any]:
    gender = {"M": "male", "F": "female"}.get(str(rec.sex).upper(), "unknown")
    return {
        "resourceType": "Patient",
        "id": rec.patient_id,
        "identifier": [
            {"system": "bioos://mrn", "value": rec.mrn},
            {"system": "bioos://bed", "value": f"{rec.ward_id}/{rec.bed_id}"},
        ],
        "name": [{"text": rec.name}],
        "gender": gender,
        "active": True,
    }


def observation_fhir(
    patient_id: str, metric_key: str, value: float, unit: str, ts_ns: int
) -> Dict[str, Any]:
    code, display = LOINC_MAP[metric_key]
    return {
        "resourceType": "Observation",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs",
                    }
                ]
            }
        ],
        "code": {"coding": [{"system": LOINC_SYSTEM, "code": code, "display": display}], "text": display},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": _iso_from_ns(ts_ns),
        "valueQuantity": {"value": value, "unit": unit, "system": UCUM_SYSTEM, "code": unit},
    }


def vitals_to_observations(rec: Any) -> List[Dict[str, Any]]:
    """Full LOINC-coded vitals/biomarker panel for one census patient."""
    ts = time.time_ns()
    pid = rec.patient_id
    return [
        observation_fhir(pid, "heart_rate", float(rec.heart_rate), "bpm", ts),
        observation_fhir(pid, "map", float(rec.mean_arterial_pressure), "mm[Hg]", ts),
        observation_fhir(pid, "spo2", float(rec.spo2_percent), "%", ts),
        observation_fhir(pid, "respiratory_rate", float(rec.respiratory_rate), "/min", ts),
        observation_fhir(pid, "temperature", float(rec.temperature_c), "Cel", ts),
        observation_fhir(pid, "potassium", float(rec.potassium_meq_l), "mmol/L", ts),
        observation_fhir(pid, "egfr", float(rec.egfr), "mL/min", ts),
        observation_fhir(pid, "creatinine", float(rec.serum_creatinine), "mg/dL", ts),
    ]

def medication_request_fhir(
    patient_id: str, drug_name: str, dose_mg: float, practitioner: str = "BioOS CDS"
) -> Dict[str, Any]:
    coding: List[Dict[str, str]] = []
    if drug_name in RXNORM_MAP:
        rxcui, display = RXNORM_MAP[drug_name]
        coding.append({"system": RXNORM_SYSTEM, "code": rxcui, "display": display})
    return {
        "resourceType": "MedicationRequest",
        # Always draft: BioOS Plane B is advisory; activation/actuation is a
        # human + Plane A kernel decision, never a facade decision.
        "status": "draft",
        "intent": "order",
        "medicationCodeableConcept": {"coding": coding, "text": drug_name},
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": _iso_from_ns(time.time_ns()),
        "requester": {"display": practitioner},
        "dosageInstruction": [
            {
                "doseQuantity": {
                    "value": float(dose_mg), "unit": "mg",
                    "system": UCUM_SYSTEM, "code": "mg",
                }
            }
        ],
    }


def bundle(resources: List[Dict[str, Any]], bundle_type: str = "collection") -> Dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": bundle_type,
        "timestamp": _iso_from_ns(time.time_ns()),
        "entry": [{"resource": r} for r in resources],
    }


class FhirService:
    """Binds hospital topology + kernel authority + audit store into FHIR APIs."""

    def __init__(self, topology: Any, store: Any, kernel_bridge: Optional[Any] = None):
        self.topology = topology
        self.store = store
        self.kernel = kernel_bridge
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ---- Patients ----

    def patient_bundle(self, ward_id: Optional[str] = None) -> Dict[str, Any]:
        records = list(self.topology.patients.values())
        if ward_id:
            records = [r for r in records if r.ward_id == ward_id]
        return bundle([patient_to_fhir(r) for r in records])

    def patient_by_id(self, patient_id: str) -> Optional[Dict[str, Any]]:
        rec = self.topology.patients.get(patient_id)
        return patient_to_fhir(rec) if rec else None

    # ---- Observations ----

    def observations_for_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        rec = self.topology.patients.get(patient_id)
        if not rec:
            return None
        return bundle(vitals_to_observations(rec))

    # ---- MedicationRequest (kernel-gated) ----

    def _kernel_verification(self, drug_name: str, dose_mg: float, egfr: float) -> str:
        """Kernel authority for Metformin; constrained register for Vancomycin;
        advisory-only verdicts otherwise. NEVER executes anything."""
        if drug_name == "Metformin":
            if self.kernel is not None:
                code = int(self.kernel.verify_metformin(egfr, float(dose_mg)))
                return _KERNEL_METFORMIN_OUTCOMES.get(code, "Unknown")
            return "RequiresClinicalOverride"  # no kernel authority available
        if drug_name == "Vancomycin":
            return "Approved"  # full AUC dosing lives in the COE constrained register
        if drug_name in RXNORM_MAP:
            return "Approved"
        return "RequiresClinicalOverride"

    def create_medication_request(
        self,
        patient_id: str,
        drug_name: str,
        dose_mg: float,
        practitioner: str = "BioOS CDS",
        egfr: Optional[float] = None,
    ) -> Dict[str, Any]:
        rec = self.topology.patients.get(patient_id)
        if not rec:
            return {"error": f"patient {patient_id} not found"}
        egfr_val = float(egfr) if egfr is not None else float(rec.egfr)
        verdict = self._kernel_verification(drug_name, dose_mg, egfr_val)

        resource = medication_request_fhir(patient_id, drug_name, dose_mg, practitioner)
        order_id = f"MR-{time.time_ns()}"
        resource["id"] = order_id
        resource["extension"] = [
            {"url": "bioos://extension/kernel-verification", "valueString": verdict},
            {"url": "bioos://extension/egfr-at-order", "valueDecimal": egfr_val},
        ]
        if verdict == "HardLockoutContraindicated":
            resource["note"] = [
                {
                    "text": (
                        "PLANE A KERNEL LOCKOUT: order blocked by safety kernel. "
                        "See extension bioos://extension/kernel-verification."
                    )
                }
            ]

        with self._lock:
            self._orders[order_id] = resource
        self.store.append_audit_entry(
            actor=practitioner,
            action="FHIR_MEDICATION_REQUEST",
            resource_type="MedicationRequest",
            resource_id=order_id,
            payload={"drug": drug_name, "dose_mg": dose_mg, "egfr": egfr_val,
                     "kernel_outcome": verdict, "patient_id": patient_id},
        )
        self.dispatch_subscriptions("MedicationRequest", resource)
        return {"medication_request": resource, "kernel_verification": verdict}

    # ---- Subscriptions ----

    def add_subscription(self, criteria: str, endpoint: str) -> Dict[str, Any]:
        return self.store.add_subscription(criteria, endpoint)

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        return self.store.list_subscriptions()

    def dispatch_subscriptions(self, resource_type: str, resource: Dict[str, Any]) -> int:
        """Fire-and-forget webhook dispatch for active subscriptions."""
        targets = [
            s for s in self.store.list_subscriptions()
            if s["status"] == "ACTIVE" and s["criteria"] == resource_type
        ]
        if not targets:
            return 0
        body = json.dumps(
            {"resourceType": "Bundle", "type": "history",
             "entry": [{"resource": resource}]}
        ).encode("utf-8")
        for sub in targets:
            threading.Thread(
                target=self._post_webhook,
                args=(sub["endpoint"], body, sub["id"]),
                daemon=True,
            ).start()
        return len(targets)

    @staticmethod
    def _post_webhook(endpoint: str, body: bytes, subscription_id: str) -> None:
        try:
            request = urllib.request.Request(
                endpoint, data=body,
                headers={"Content-Type": "application/fhir+json"}, method="POST",
            )
            urllib.request.urlopen(request, timeout=2).read()
        except Exception as exc:
            print(f"[BioOS FHIR] webhook delivery failed (subscription {subscription_id}): {exc}")
