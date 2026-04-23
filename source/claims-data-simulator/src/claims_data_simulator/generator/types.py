"""Internal dataclasses used by the claims generator.

These types flow between generator functions and are never returned
directly from the API or persisted to the database.  They are converted
to SQLModel entities at the persistence boundary.
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class GeneratedClaimLine:
    """A single service line produced by the generator.

    Attributes:
        line_id: Unique line key (``<claim_id>-L<line_number>``).
        line_number: 1-indexed position within the parent claim.
        cpt_code: 5-character CPT/HCPCS code.
        cpt_description: Human-readable label for the CPT code.
        modifier_1: Optional 2-character CPT modifier.
        modifier_2: Optional 2-character CPT modifier.
        icd10_primary: Primary ICD-10 diagnosis code.
        icd10_secondary: Additional ICD-10 codes (may be empty).
        units: Number of service units.
        charge_amount: Billed charge for this line.
        allowed_amount: Payer-allowed amount (null until adjudicated).
        paid_amount: Payer-paid amount (null until adjudicated).
        service_date: Date the service was rendered.
    """

    line_id: str
    line_number: int
    cpt_code: str
    cpt_description: str
    modifier_1: str | None
    modifier_2: str | None
    icd10_primary: str
    icd10_secondary: list[str]
    units: int
    charge_amount: Decimal
    allowed_amount: Decimal | None
    paid_amount: Decimal | None
    service_date: datetime.date


@dataclass
class GeneratedClaim:
    """A complete claim produced by the generator before persistence.

    Attributes:
        claim_id: Natural key (``CLM-<YYYY>-<8-digit>``).
        patient_id: Patient identifier.
        payer_id: Payer organization identifier.
        payer_name: Human-readable payer name.
        plan_type: Insurance plan type.
        member_id: Payer-assigned member identifier.
        group_number: Employer group number.
        claim_type: ``professional`` or ``institutional``.
        place_of_service: 2-digit CMS place-of-service code.
        billing_provider_npi: 10-digit NPI of the billing provider.
        rendering_provider_npi: 10-digit NPI of the rendering provider.
        service_date_from: First date of service.
        service_date_to: Last date of service.
        submitted_date: Date the claim was submitted.
        adjudicated_date: Adjudication date (null on creation).
        status: Lifecycle status (always ``submitted`` on creation).
        total_billed_amount: Sum of line charge amounts.
        total_allowed_amount: Payer-allowed total (null on creation).
        total_paid_amount: Payer-paid total (null on creation).
        patient_responsibility: Patient owes this amount (null on creation).
        denial_reason_code: CARC code (null on creation).
        created_at: Timestamp of creation.
        last_updated_at: Timestamp of last modification.
        lines: Child line items for this claim.
    """

    claim_id: str
    patient_id: str
    payer_id: str
    payer_name: str
    plan_type: str
    member_id: str
    group_number: str
    claim_type: str
    place_of_service: str
    billing_provider_npi: str
    rendering_provider_npi: str
    service_date_from: datetime.date
    service_date_to: datetime.date
    submitted_date: datetime.date
    adjudicated_date: datetime.date | None
    status: str
    total_billed_amount: Decimal
    total_allowed_amount: Decimal | None
    total_paid_amount: Decimal | None
    patient_responsibility: Decimal | None
    denial_reason_code: str | None
    created_at: datetime.datetime
    last_updated_at: datetime.datetime
    lines: list[GeneratedClaimLine] = field(default_factory=list)


@dataclass
class LifecycleTransition:
    """Describes a single status advance for a claim.

    Attributes:
        new_status: The status after the transition.
        adjudicated_date: Adjudication date (set on terminal transitions).
        total_allowed_amount: Payer-allowed total (set on terminal transitions).
        total_paid_amount: Payer-paid total (set on terminal transitions).
        patient_responsibility: Patient responsibility (set on terminal transitions).
        denial_reason_code: CARC denial code (set only for ``denied``).
    """

    new_status: str
    adjudicated_date: datetime.date | None
    total_allowed_amount: Decimal | None
    total_paid_amount: Decimal | None
    patient_responsibility: Decimal | None
    denial_reason_code: str | None


@dataclass
class AmountAllocation:
    """Per-line monetary distribution when a claim is paid.

    Attributes:
        line_number: The line this allocation applies to.
        allowed_amount: Payer-allowed amount for this line.
        paid_amount: Payer-paid amount for this line.
    """

    line_number: int
    allowed_amount: Decimal
    paid_amount: Decimal
