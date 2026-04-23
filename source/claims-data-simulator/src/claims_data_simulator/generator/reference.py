"""Reference value pools for realistic claims data generation.

All pools are defined as module-level constants drawn from the
healthcare-domain-knowledge skill.  They provide the candidate values
that the generator draws from when building claims and claim lines.
"""

from decimal import Decimal

PAYERS: list[tuple[str, str]] = [
    ("PAYER-UHC-001", "UnitedHealthcare"),
    ("PAYER-AET-002", "Aetna"),
    ("PAYER-CIG-003", "Cigna"),
    ("PAYER-BCB-004", "Blue Cross Blue Shield"),
    ("PAYER-HUM-005", "Humana"),
    ("PAYER-MED-006", "Medicare"),
    ("PAYER-MCD-007", "Medicaid"),
]
"""Each entry is ``(payer_id, payer_name)``."""

PAYER_PREFIXES: dict[str, str] = {
    "PAYER-UHC-001": "UHC",
    "PAYER-AET-002": "AET",
    "PAYER-CIG-003": "CIG",
    "PAYER-BCB-004": "BCB",
    "PAYER-HUM-005": "HUM",
    "PAYER-MED-006": "MED",
    "PAYER-MCD-007": "MCD",
}
"""Maps ``payer_id`` to the 3-letter prefix used in ``member_id``."""

PLAN_TYPES: list[str] = ["HMO", "PPO", "EPO", "POS", "HDHP"]
"""Insurance plan types."""

PLACE_OF_SERVICE_CODES: list[str] = ["11", "21", "22", "23", "81"]
"""CMS place-of-service codes (Office, Inpatient, Outpatient, ER, Lab)."""

CPT_CODES: list[tuple[str, str, int, int]] = [
    ("99213", "Office visit, established patient, 20-29 min", 100, 250),
    ("99214", "Office visit, established patient, 30-39 min", 150, 350),
    ("99203", "Office visit, new patient, 30-44 min", 175, 400),
    ("85025", "Complete blood count with differential", 25, 60),
    ("80053", "Comprehensive metabolic panel", 40, 230),
    ("80061", "Lipid panel", 35, 120),
    ("93000", "Electrocardiogram, complete", 50, 175),
    ("71046", "Chest X-ray, 2 views", 100, 350),
    ("73721", "MRI lower extremity joint without contrast", 900, 2500),
    ("45378", "Colonoscopy, diagnostic", 1200, 2500),
    ("36415", "Routine venipuncture", 15, 40),
    ("90471", "Immunization administration", 25, 90),
]
"""Each entry is ``(code, description, charge_min, charge_max)``."""

ICD10_CODES: list[str] = [
    "E11.9",
    "I10",
    "E78.5",
    "J06.9",
    "M25.561",
    "M54.50",
    "Z12.11",
    "Z00.00",
    "F41.9",
    "K21.9",
]
"""ICD-10 diagnosis codes used for primary and secondary diagnoses."""

CPT_MODIFIERS: list[str] = ["25", "59", "33", "LT", "RT"]
"""CPT modifier codes."""

CARC_DENIAL_CODES: list[str] = [
    "CO-197",
    "CO-16",
    "CO-45",
    "CO-29",
    "PR-1",
    "PR-204",
]
"""Claim Adjustment Reason Codes used for denied claims."""

LINE_COUNT_WEIGHTS: list[tuple[int, float]] = [
    (1, 0.40),
    (2, 0.30),
    (3, 0.15),
    (4, 0.10),
    (5, 0.05),
]
"""Weighted distribution for the number of lines per claim."""

CLAIM_TYPE_WEIGHTS: list[tuple[str, float]] = [
    ("professional", 0.90),
    ("institutional", 0.10),
]
"""Weighted distribution for claim type."""

ICD10_SECONDARY_COUNT_WEIGHTS: list[tuple[int, float]] = [
    (0, 0.50),
    (1, 0.30),
    (2, 0.15),
    (3, 0.05),
]
"""Weighted distribution for the number of secondary ICD-10 codes per line."""

MODIFIER_1_PROBABILITY: float = 0.15
"""Probability that a line has ``modifier_1`` populated."""

MODIFIER_2_PROBABILITY: float = 0.03
"""Probability that a line has ``modifier_2`` populated."""

PAID_PROBABILITY: float = 0.70
"""Probability that a claim leaving ``in_review`` is paid (vs denied)."""

ALLOWED_AMOUNT_RANGE: tuple[Decimal, Decimal] = (Decimal("0.60"), Decimal("0.80"))
"""``total_allowed_amount`` as a fraction of ``total_billed_amount``."""

PAID_AMOUNT_RANGE: tuple[Decimal, Decimal] = (Decimal("0.75"), Decimal("0.95"))
"""``total_paid_amount`` as a fraction of ``total_allowed_amount``."""
