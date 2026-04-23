"""Pydantic response models for the claims API.

These models define the serialization contract for the ``GET /claims``
endpoint.  SQLModel entities are translated into these models at the API
boundary before being returned to the caller.
"""

import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, model_serializer


class ClaimLineResponse(BaseModel):
    """Serialized representation of a single claim line.

    Attributes:
        line_id: Unique line key.
        line_number: 1-indexed position within the parent claim.
        cpt_code: 5-character CPT/HCPCS code.
        cpt_description: Human-readable label for the CPT code.
        modifier_1: Optional CPT modifier.
        modifier_2: Optional CPT modifier.
        icd10_primary: Primary ICD-10 diagnosis code.
        icd10_secondary: Additional ICD-10 codes.
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


class ClaimResponse(BaseModel):
    """Serialized representation of a medical claim.

    ``denial_reason_code`` is omitted from the JSON output when it is
    ``None``.  All other nullable fields serialize as explicit ``null``.

    Attributes:
        claim_id: Natural key.
        patient_id: Patient identifier (nullable only via quality injection).
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
        adjudicated_date: Adjudication date.
        status: Lifecycle status.
        total_billed_amount: Sum of line charge amounts.
        total_allowed_amount: Payer-allowed total.
        total_paid_amount: Payer-paid total.
        patient_responsibility: Patient owes this amount.
        denial_reason_code: CARC code (omitted from output when None).
        claim_lines: Child line items.
        created_at: Row creation timestamp.
        last_updated_at: Last modification timestamp.
    """

    claim_id: str
    patient_id: str | None
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
    denial_reason_code: str | None = None
    claim_lines: list[ClaimLineResponse]
    created_at: datetime.datetime
    last_updated_at: datetime.datetime

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """Serialize the claim, omitting ``denial_reason_code`` when None.

        All other nullable fields are kept as explicit ``null`` in the
        output.

        Returns:
            A dict suitable for JSON serialization.
        """
        data: dict[str, Any] = {}
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            if field_name == "denial_reason_code" and value is None:
                continue
            if field_name == "claim_lines":
                data[field_name] = [line.model_dump(mode="json") for line in value]
            else:
                data[field_name] = value
        return data


class ClaimsEnvelopeResponse(BaseModel):
    """Top-level response envelope for the ``GET /claims`` endpoint.

    Attributes:
        generated_at: ISO-8601 UTC timestamp of when the response was built.
        record_count: Number of claims in the response (post-injection).
        claims: The list of claim objects.
    """

    generated_at: datetime.datetime
    record_count: int
    claims: list[ClaimResponse]
