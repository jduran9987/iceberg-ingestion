"""GET /claims route handler.

Implements the full request flow: generate new claims, apply lifecycle
updates, read all claims, inject data-quality issues, and return the
response envelope.
"""

import datetime
import random

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from claims_data_simulator.api.schemas import (
    ClaimLineResponse,
    ClaimResponse,
    ClaimsEnvelopeResponse,
)
from claims_data_simulator.db.models import Claim, ClaimLine
from claims_data_simulator.db.repository import (
    insert_claim,
    list_all_claims,
    list_eligible_for_update,
    update_claim,
)
from claims_data_simulator.db.session import get_session
from claims_data_simulator.generator.lifecycle import advance_status
from claims_data_simulator.generator.new_claim import build_new_claim
from claims_data_simulator.generator.types import GeneratedClaim
from claims_data_simulator.quality.inject import (
    inject_duplicate,
    inject_null_patient_id,
)

router = APIRouter()


def _generated_to_model(generated: GeneratedClaim) -> Claim:
    """Convert a generator dataclass into a SQLModel entity for persistence.

    Args:
        generated: The in-memory claim produced by the generator.

    Returns:
        A ``Claim`` SQLModel instance with attached ``ClaimLine`` children.
    """
    lines = [
        ClaimLine(
            line_id=gl.line_id,
            claim_id=generated.claim_id,
            line_number=gl.line_number,
            cpt_code=gl.cpt_code,
            cpt_description=gl.cpt_description,
            modifier_1=gl.modifier_1,
            modifier_2=gl.modifier_2,
            icd10_primary=gl.icd10_primary,
            icd10_secondary=gl.icd10_secondary,
            units=gl.units,
            charge_amount=gl.charge_amount,
            allowed_amount=gl.allowed_amount,
            paid_amount=gl.paid_amount,
            service_date=gl.service_date,
        )
        for gl in generated.lines
    ]
    return Claim(
        claim_id=generated.claim_id,
        patient_id=generated.patient_id,
        payer_id=generated.payer_id,
        payer_name=generated.payer_name,
        plan_type=generated.plan_type,
        member_id=generated.member_id,
        group_number=generated.group_number,
        claim_type=generated.claim_type,
        place_of_service=generated.place_of_service,
        billing_provider_npi=generated.billing_provider_npi,
        rendering_provider_npi=generated.rendering_provider_npi,
        service_date_from=generated.service_date_from,
        service_date_to=generated.service_date_to,
        submitted_date=generated.submitted_date,
        adjudicated_date=generated.adjudicated_date,
        status=generated.status,
        total_billed_amount=generated.total_billed_amount,
        total_allowed_amount=generated.total_allowed_amount,
        total_paid_amount=generated.total_paid_amount,
        patient_responsibility=generated.patient_responsibility,
        denial_reason_code=generated.denial_reason_code,
        created_at=generated.created_at,
        last_updated_at=generated.last_updated_at,
        claim_lines=lines,
    )


def _model_to_response(claim: Claim) -> ClaimResponse:
    """Convert a SQLModel claim into a Pydantic response model.

    Args:
        claim: The persisted claim with eagerly loaded lines.

    Returns:
        A ``ClaimResponse`` suitable for serialization.
    """
    lines = sorted(claim.claim_lines, key=lambda ln: ln.line_number)
    return ClaimResponse(
        claim_id=claim.claim_id,
        patient_id=claim.patient_id,
        payer_id=claim.payer_id,
        payer_name=claim.payer_name,
        plan_type=claim.plan_type,
        member_id=claim.member_id,
        group_number=claim.group_number,
        claim_type=claim.claim_type,
        place_of_service=claim.place_of_service,
        billing_provider_npi=claim.billing_provider_npi,
        rendering_provider_npi=claim.rendering_provider_npi,
        service_date_from=claim.service_date_from,
        service_date_to=claim.service_date_to,
        submitted_date=claim.submitted_date,
        adjudicated_date=claim.adjudicated_date,
        status=claim.status,
        total_billed_amount=claim.total_billed_amount,
        total_allowed_amount=claim.total_allowed_amount,
        total_paid_amount=claim.total_paid_amount,
        patient_responsibility=claim.patient_responsibility,
        denial_reason_code=claim.denial_reason_code,
        claim_lines=[
            ClaimLineResponse(
                line_id=ln.line_id,
                line_number=ln.line_number,
                cpt_code=ln.cpt_code,
                cpt_description=ln.cpt_description,
                modifier_1=ln.modifier_1,
                modifier_2=ln.modifier_2,
                icd10_primary=ln.icd10_primary,
                icd10_secondary=list(ln.icd10_secondary),
                units=ln.units,
                charge_amount=ln.charge_amount,
                allowed_amount=ln.allowed_amount,
                paid_amount=ln.paid_amount,
                service_date=ln.service_date,
            )
            for ln in lines
        ],
        created_at=claim.created_at,
        last_updated_at=claim.last_updated_at,
    )


@router.get("/claims", response_model=ClaimsEnvelopeResponse)
def get_claims(
    new: int = Query(default=0, ge=0),
    updates: int = Query(default=0, ge=0),
    duplicates: bool = Query(default=False),
    null_patient_id: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> ClaimsEnvelopeResponse:
    """Generate, update, and return all claims.

    Executes the full request flow:

    1. Generate and persist ``new`` claims in ``submitted`` status.
    2. Advance up to ``updates`` eligible claims one lifecycle step.
    3. Read all claims from the database.
    4. Translate to response models.
    5. Inject data-quality issues (duplicates, null patient IDs).
    6. Return the envelope.

    Args:
        new: Number of new claims to generate.
        updates: Number of existing claims to advance.
        duplicates: If true, duplicate one new claim in the response.
        null_patient_id: If true, null one new claim's patient_id
            in the response.
        session: Database session (injected).

    Returns:
        An envelope containing all claims and metadata.
    """
    rng = random.Random()
    newly_created_ids: set[str] = set()

    # Step 1: Generate and persist new claims.
    for _ in range(new):
        generated = build_new_claim(rng)
        model = _generated_to_model(generated)
        insert_claim(session, model)
        newly_created_ids.add(generated.claim_id)

    # Step 2: Apply lifecycle updates.
    if updates > 0:
        eligible = list_eligible_for_update(session, updates)
        for claim in eligible:
            advance_status(claim, rng)
            update_claim(session, claim)

    # Commit all writes.
    session.commit()

    # Step 3: Read all claims.
    all_claims = list_all_claims(session)

    # Step 4: Translate to response models.
    response_claims = [_model_to_response(c) for c in all_claims]

    # Step 5: Inject data-quality issues.
    duplicate_target_id: str | None = None
    if duplicates and newly_created_ids:
        pre_count = len(response_claims)
        response_claims = inject_duplicate(response_claims, newly_created_ids, rng)
        if len(response_claims) > pre_count:
            duplicate_target_id = response_claims[-1].claim_id

    avoid_ids: set[str] = set()
    if duplicate_target_id is not None:
        avoid_ids.add(duplicate_target_id)

    if null_patient_id:
        response_claims, _ = inject_null_patient_id(
            response_claims, newly_created_ids, avoid_ids, rng
        )

    # Step 6: Return envelope.
    now = datetime.datetime.now(datetime.UTC)
    return ClaimsEnvelopeResponse(
        generated_at=now,
        record_count=len(response_claims),
        claims=response_claims,
    )
