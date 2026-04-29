"""Pydantic models for validating simulated healthcare claims payloads.

Defines the external request/response schemas for medical claims and their
nested claim lines, including:

- Reusable annotated string types for domain identifiers (claim IDs, NPIs,
  CPT codes, etc.).
- Enumerations for plan types, claim types, and claim statuses.
- ``ClaimLine`` and ``Claim`` Pydantic models with strict validation,
  cross-field invariants, and lifecycle-aware nullability rules.

Both models accept and retain unknown fields (``extra="allow"``) so that
upstream schema drift can be detected and logged downstream rather than
silently dropped.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

# Type Aliases
ClaimId = Annotated[str, Field(pattern=r"^CLM-\d{4}-\d{8}$")]
PatientId = Annotated[str, Field(pattern=r"^PAT-\d{7}$")]
GroupNumber = Annotated[str, Field(pattern=r"^GRP-\d{5}$")]
CMSPosCode = Annotated[str, Field(pattern=r"^\d{2}$")]
NPINumber = Annotated[str, Field(pattern=r"^\d{10}$")]
LineId = Annotated[str, Field(pattern=r"^CLM-\d{4}-\d{8}-L\d+$")]
CPTCode = Annotated[str, Field(pattern=r"^\d{5}$")]
Currency = Annotated[Decimal, Field(max_digits=12, decimal_places=2, ge=0)]
StrNotBlank = Annotated[str, Field(min_length=1)]


class PlanType(StrEnum):
    """Insurance plan type the patient is enrolled in.

    Attributes:
        HMO: Health Maintenance Organization.
        PPO: Preferred Provider Organization.
        EPO: Exclusive Provider Organization.
        POS: Point of Service plan.
        HDHP: High-Deductible Health Plan.
    """

    HMO = "HMO"
    PPO = "PPO"
    EPO = "EPO"
    POS = "POS"
    HDHP = "HDHP"


class ClaimType(StrEnum):
    """High-level category of the claim.

    Attributes:
        PROFESSIONAL: Claim for services rendered by an individual clinician
            (CMS-1500 / 837P equivalent).
        INSTITUTIONAL: Claim for services rendered by a facility such as a
            hospital (UB-04 / 837I equivalent).
    """

    PROFESSIONAL = "professional"
    INSTITUTIONAL = "institutional"


class ClaimStatus(StrEnum):
    """Adjudication lifecycle state of a claim.

    A claim starts at ``SUBMITTED`` and advances one step per update through
    ``IN_REVIEW`` to a terminal state of ``PAID`` or ``DENIED``. Terminal
    states are never updated again.

    Attributes:
        SUBMITTED: Provider has transmitted the claim; payer has not begun
            adjudication.
        IN_REVIEW: Payer is actively evaluating the claim.
        PAID: Payer has approved payment; monetary fields are populated.
        DENIED: Payer has rejected the claim; a denial reason code is
            recorded.
    """

    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    PAID = "paid"
    DENIED = "denied"


class ClaimLine(BaseModel):
    """A single billable service line within a claim.

    Each line represents one CPT-coded service, its diagnoses, units, and
    monetary fields. Adjudication-dependent fields (``allowed_amount`` and
    ``paid_amount``) are nullable until the parent claim reaches a terminal
    status.

    Attributes:
        line_id: Globally unique line identifier in
            ``CLM-<YYYY>-<8-digit>-L<line_number>`` format.
        line_number: 1-indexed position of this line within the parent claim.
        cpt_code: 5-character CPT/HCPCS procedure code.
        cpt_description: Human-readable description of the CPT code.
        modifier_1: Optional 2-character CPT modifier.
        modifier_2: Optional second 2-character CPT modifier.
        icd10_primary: Primary ICD-10-CM diagnosis code for this line.
        icd10_secondary: Additional ICD-10-CM diagnosis codes; may be empty.
        units: Number of service units billed; must be positive.
        charge_amount: Amount billed for this line in USD.
        allowed_amount: Amount the payer allowed for this line; populated
            on ``PAID``/``DENIED``, otherwise null.
        paid_amount: Amount the payer paid for this line; populated on
            ``PAID``/``DENIED``, otherwise null.
        service_date: Date the service represented by this line was rendered.
    """

    model_config = ConfigDict(strict=True, extra="allow")

    line_id: LineId
    line_number: PositiveInt
    cpt_code: CPTCode
    cpt_description: StrNotBlank
    modifier_1: StrNotBlank | None
    modifier_2: StrNotBlank | None
    icd10_primary: StrNotBlank
    icd10_secondary: list[StrNotBlank]
    units: PositiveInt
    charge_amount: Currency
    allowed_amount: Currency | None
    paid_amount: Currency | None
    service_date: date


class Claim(BaseModel):
    """A medical claim with its nested service lines.

    Represents a billing record submitted by a provider to a payer. Mutates
    over time as the payer adjudicates it: monetary totals and the
    ``adjudicated_date`` populate when the claim reaches a terminal state.
    Cross-field invariants (date ordering, status-driven nullability,
    line-level service date containment, total-vs-charge equality) are
    enforced via model validators.

    Attributes:
        claim_id: Globally unique claim identifier in
            ``CLM-<YYYY>-<8-digit>`` format. Natural key.
        patient_id: Patient identifier in ``PAT-<7-digit>`` format.
        payer_id: Stable identifier for the insurance payer.
        payer_name: Human-readable payer name.
        plan_type: Patient's insurance plan type.
        member_id: Patient's member ID on the insurance plan.
        group_number: Employer/group identifier in ``GRP-<5-digit>`` format.
        claim_type: Whether the claim is professional or institutional.
        place_of_service: 2-digit CMS Place of Service code.
        billing_provider_npi: 10-digit NPI of the billing entity.
        rendering_provider_npi: 10-digit NPI of the rendering clinician.
        service_date_from: Inclusive start date of service.
        service_date_to: Inclusive end date of service; must be on or after
            ``service_date_from``.
        submitted_date: Date the provider transmitted the claim; must be on
            or after ``service_date_to``.
        adjudicated_date: Date the payer adjudicated the claim; populated
            only on terminal statuses.
        status: Current lifecycle state of the claim.
        total_billed_amount: Total amount billed; must equal the sum of
            line ``charge_amount`` values.
        total_allowed_amount: Total amount the payer allowed; populated on
            terminal statuses.
        total_paid_amount: Total amount the payer paid; populated on
            terminal statuses.
        patient_responsibility: Total amount the patient owes; populated on
            terminal statuses.
        denial_reason_code: CARC denial code; required only when status is
            ``DENIED``, otherwise must be null.
        claim_lines: Nested service lines belonging to this claim.
        created_at: Timestamp when the claim was first created. Immutable.
        last_updated_at: Timestamp of the most recent mutation.
    """

    model_config = ConfigDict(strict=True, extra="allow")

    claim_id: ClaimId
    patient_id: PatientId
    payer_id: StrNotBlank
    payer_name: StrNotBlank
    plan_type: PlanType
    member_id: StrNotBlank
    group_number: GroupNumber
    claim_type: ClaimType
    place_of_service: CMSPosCode
    billing_provider_npi: NPINumber
    rendering_provider_npi: NPINumber
    service_date_from: date
    service_date_to: date
    submitted_date: date
    adjudicated_date: date | None
    status: ClaimStatus
    total_billed_amount: Currency
    total_allowed_amount: Currency | None
    total_paid_amount: Currency | None
    patient_responsibility: Currency | None
    denial_reason_code: StrNotBlank | None = None
    claim_lines: list[ClaimLine]
    created_at: datetime
    last_updated_at: datetime

    @model_validator(mode="after")
    def check_order_of_dates(self) -> Self:
        """Validate temporal ordering of all date fields on the claim.

        Enforces the following invariants and accumulates every violation
        into a single ``ValueError`` so callers see all issues for a claim
        at once:

        - ``service_date_to`` must be on or after ``service_date_from``.
        - ``submitted_date`` must be on or after ``service_date_to``.
        - ``adjudicated_date``, when not null, must be on or after
          ``submitted_date``.
        - Each line's ``service_date`` must fall within the claim's
          ``[service_date_from, service_date_to]`` range.

        Returns:
            The validated ``Claim`` instance unchanged.

        Raises:
            ValueError: If any of the date-ordering invariants are
                violated. The message includes the ``claim_id``, the
                validator name, and a semicolon-separated list of every
                violation found.
        """
        error_msgs = []

        if self.service_date_to < self.service_date_from:
            error_msgs.append("service_date_to must be after service_date_from")
        if self.submitted_date < self.service_date_to:
            error_msgs.append("submitted_date must be after service_date_to")
        if (
            self.adjudicated_date is not None
            and self.adjudicated_date < self.submitted_date
        ):
            error_msgs.append(
                "adjudicated_date must be after submitted_date when not null"
            )

        for line in self.claim_lines:
            if (
                self.service_date_from > line.service_date
                or self.service_date_to < line.service_date
            ):
                error_msgs.append(
                    f"line item service_date_{line.line_id} must be between "
                    "claim level service_date_to and service_date_from"
                )

        if error_msgs:
            raise ValueError(
                f"claim id: {self.claim_id} "
                "model validator: check_order_of_dates "
                f"validation errors: {'; '.join(error_msgs)}"
            )

        return self

    @model_validator(mode="after")
    def check_claim_status(self) -> Self:
        """Validate field nullability and values against the claim status.

        Applies status-specific rules at both the claim level and the line
        level, accumulating every violation into a single ``ValueError``:

        For ``SUBMITTED`` and ``IN_REVIEW`` (non-terminal) statuses, all of
        ``adjudicated_date``, ``total_allowed_amount``, ``total_paid_amount``,
        ``patient_responsibility``, and ``denial_reason_code`` must be
        null at the claim level, and ``allowed_amount`` and ``paid_amount``
        must be null on every line.

        For ``PAID``, ``adjudicated_date`` and the three monetary totals
        must be non-null at the claim level, ``denial_reason_code`` must be
        null, and ``allowed_amount`` and ``paid_amount`` must be non-null
        on every line.

        For ``DENIED``, ``adjudicated_date``, ``patient_responsibility``,
        and ``denial_reason_code`` must be non-null;
        ``total_allowed_amount`` and ``total_paid_amount`` must equal
        ``Decimal("0.00")``; ``patient_responsibility`` must equal
        ``total_billed_amount``; and ``allowed_amount`` and ``paid_amount``
        must be non-null on every line.

        Returns:
            The validated ``Claim`` instance unchanged.

        Raises:
            ValueError: If any of the status-driven invariants are
                violated. The message includes the ``claim_id``, the
                validator name, and a semicolon-separated list of every
                violation found across both claim-level and line-level
                fields.
        """
        error_msgs_top_level = []
        error_msgs_line_item = []

        if self.status in {ClaimStatus.SUBMITTED, ClaimStatus.IN_REVIEW}:
            forbidden_fields = {
                "adjudicated_date": self.adjudicated_date,
                "total_allowed_amount": self.total_allowed_amount,
                "total_paid_amount": self.total_paid_amount,
                "patient_responsibility": self.patient_responsibility,
                "denial_reason_code": self.denial_reason_code,
            }

            error_msgs_top_level.extend([
                f"field: {field} must be null when status is {self.status}"
                for field, value in forbidden_fields.items()
                if value is not None
            ])

            for line in self.claim_lines:
                line_forbidden_fields = {
                    f"claim_lines.allowed_amount_{line.line_id}": line.allowed_amount,
                    f"claim_lines.paid_amount_{line.line_id}": line.paid_amount,
                }
                error_msgs_line_item.extend([
                    f"field: {field} must be null when status is {self.status}"
                    for field, value in line_forbidden_fields.items()
                    if value is not None
                ])

        if self.status == ClaimStatus.PAID:
            required_fields = {
                "adjudicated_date": self.adjudicated_date,
                "total_allowed_amount": self.total_allowed_amount,
                "total_paid_amount": self.total_paid_amount,
                "patient_responsibility": self.patient_responsibility,
            }

            error_msgs_top_level.extend([
                f"field: {field} must not be null when status is paid"
                for field, value in required_fields.items()
                if value is None
            ])

            if self.denial_reason_code is not None:
                error_msgs_top_level.extend([
                    "denial_reason_code must be null when status is paid"
                ])

            for line in self.claim_lines:
                line_required_fields = {
                    f"allowed_amount_{line.line_id}": line.allowed_amount,
                    f"paid_amount_{line.line_id}": line.paid_amount,
                }

                error_msgs_line_item.extend([
                    f"field: {field} must not be null when status is paid"
                    for field, value in line_required_fields.items()
                    if value is None
                ])

        if self.status == ClaimStatus.DENIED:
            required_fields = {
                "adjudicated_date": self.adjudicated_date,
                "patient_responsibility": self.patient_responsibility,
                "denial_reason_code": self.denial_reason_code,
            }

            error_msgs_top_level.extend([
                f"field: {field} must not be null when status is denied"
                for field, value in required_fields.items()
                if value is None
            ])

            if self.total_allowed_amount != Decimal("0.00"):
                error_msgs_top_level.extend([
                    "total_allowed_amount must be 0.00 when status is denied"
                ])
            if self.total_paid_amount != Decimal("0.00"):
                error_msgs_top_level.extend([
                    "total_paid_amount must be 0.00 when status is denied"
                ])
            if self.patient_responsibility != self.total_billed_amount:
                error_msgs_top_level.extend([
                    "patient_responsibility must equal total_billed_amount "
                    "when status is denied"
                ])

            for line in self.claim_lines:
                line_required_fields = {
                    f"allowed_amount_{line.line_id}": line.allowed_amount,
                    f"paid_amount_{line.line_id}": line.paid_amount,
                }

                error_msgs_line_item.extend([
                    f"field: {field} must not be null when status is denied"
                    for field, value in line_required_fields.items()
                    if value is None
                ])

        error_msgs = error_msgs_top_level + error_msgs_line_item

        if error_msgs:
            raise ValueError(
                f"claim id: {self.claim_id} "
                "model validator: check_claim_status "
                f"validation errors: {'; '.join(error_msgs)}"
            )

        return self

    @model_validator(mode="after")
    def check_total_billed_eq_charge_amount(self) -> Self:
        """Validate the claim total equals the sum of line charges.

        Enforces that ``total_billed_amount`` exactly equals the sum of
        ``charge_amount`` across every claim line. This invariant must hold
        in every status, since both fields are populated at claim creation.

        Returns:
            The validated ``Claim`` instance unchanged.

        Raises:
            ValueError: If ``total_billed_amount`` does not equal the sum
                of ``charge_amount`` across ``claim_lines``. The message
                includes the ``claim_id`` and the validator name.
        """
        total_charge_amount = sum(line.charge_amount for line in self.claim_lines)

        if self.total_billed_amount != total_charge_amount:
            raise ValueError(
                f"claim id: {self.claim_id} "
                "model validator: check_total_billed_eq_charge_amount "
                "validation errors: claim level total_billed_amount must "
                "equal the total charge_amount across all lines"
            )

        return self
