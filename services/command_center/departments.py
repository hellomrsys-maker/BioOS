"""BioOS Hospital Departments Data Model.

Based on the extracted PDF text of "Hospital Departments and Clinical Reasoning".

This module defines typed dataclasses representing the hospital departments described in the research.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class DepartmentType(Enum):
    INPATIENT = "Inpatient"
    OUTPATIENT = "Outpatient"
    SPECIALTY = "Specialty"
    DIAGNOSTIC = "Diagnostic"
    SUPPORT = "Support"
    ADMINISTRATION = "Administration"

@dataclass(frozen=True)
class Equipment:
    name: str

@dataclass(frozen=True)
class StaffRole:
    name: str
    count: int

@dataclass(frozen=True)
class Department:
    name: str
    description: str
    type: DepartmentType
    staff_roles: List[StaffRole]
    bed_capacity: Optional[int] = None
    active_beds: Optional[int] = None
    equipment: List[Equipment] = None
    policies: List[str] = None

DEPARTMENTS: List[Department] = [
    Department(
        name="Cardiology",
        description="Inpatient & outpatient care of ischemic, valvular, congenital, arrhythmic heart disease.",
        type=DepartmentType.SPECIALTY,
        staff_roles=[StaffRole("Cardiologist", 10), StaffRole("Nurse", 25)],
        bed_capacity=45,
        active_beds=38,
        equipment=[Equipment("Echocardiography console"), Equipment("Catheterization lab")],
        policies=["D2B < 90 min", "D2N < 30 min"]
    ),
    Department(
        name="L&D",
        description="Maternal delivery; obstetrics, neonatal care, colposcopy.",
        type=DepartmentType.SPECIALTY,
        staff_roles=[StaffRole("OB-GYN", 6), StaffRole("Midwife", 12), StaffRole("Neonatologist", 3)],
        bed_capacity=30,
        active_beds=27,
        equipment=[Equipment("Cardiotocography monitor"), Equipment("Neonatal radiant warmer")],
        policies=[]
    ),
    Department(
        name="Emergency Department",
        description="24-hour acute trauma, medical emergencies, chest pain.",
        type=DepartmentType.INPATIENT,
        staff_roles=[StaffRole("Emergency physician", 12), StaffRole("RN", 35)],
        bed_capacity=20,
        active_beds=20,
        equipment=[Equipment("CT scanner"), Equipment("Helicopter pad")],
        policies=["D2N < 30 min", "ED boarding < 24 hrs"]
    ),
    Department(
        name="Intensive Care Unit",
        description="Critical care for ACS, sepsis, organ failure, resuscitation.",
        type=DepartmentType.INPATIENT,
        staff_roles=[StaffRole("Intensivist", 6), StaffRole("ICU RN", 20)],
        bed_capacity=18,
        active_beds=18,
        equipment=[Equipment("Ventilator"), Equipment("CRRT machine")],
        policies=[]
    ),
    Department(
        name="Radiology – Diagnostic",
        description="X-ray, CT, MRI, ultrasound imaging services.",
        type=DepartmentType.DIAGNOSTIC,
        staff_roles=[StaffRole("Radiologist", 8), StaffRole("Tech", 20)],
        equipment=[Equipment("Digital X-ray"), Equipment("CT scanner"), Equipment("MRI scanner")],
        policies=["D2N < 30 min for STEMI"]
    ),
    Department(
        name="Pathology & Lab",
        description="Clinical chemistry, microbiology, histology, blood bank.",
        type=DepartmentType.SUPPORT,
        staff_roles=[StaffRole("Pathologist", 7), StaffRole("Tech", 30)],
        equipment=[Equipment("Automated analyzer"), Equipment("Incubator")],
        policies=["Result turnaround < 4 h for cultures"]
    ),
    Department(
        name="Pharmacy",
        description="Formulary, compounding, dispensing, medication safety.",
        type=DepartmentType.SUPPORT,
        staff_roles=[StaffRole("Pharmacist", 5), StaffRole("Tech", 10)],
        equipment=[Equipment("Dispensing cabinet"), Equipment("Compounding station")],
        policies=["Closed‑loop communication for orders"]
    ),
]

