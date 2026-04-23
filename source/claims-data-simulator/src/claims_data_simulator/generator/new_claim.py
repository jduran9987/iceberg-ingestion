"""Build fresh claims in ``submitted`` status.

Each new claim is generated with realistic field distributions drawn
from the reference pools and weighted heuristics defined in the
healthcare domain knowledge.
"""

import datetime
import random
from decimal import Decimal

from claims_data_simulator.generator.ids import (
    make_line_id,
    next_claim_id,
    pick_group_number,
    pick_member_id,
    pick_npi,
    pick_patient_id,
)
from claims_data_simulator.generator.reference import (
    CLAIM_TYPE_WEIGHTS,
    CPT_CODES,
    CPT_MODIFIERS,
    ICD10_CODES,
    ICD10_SECONDARY_COUNT_WEIGHTS,
    LINE_COUNT_WEIGHTS,
    MODIFIER_1_PROBABILITY,
    MODIFIER_2_PROBABILITY,
    PAYER_PREFIXES,
    PAYERS,
    PLACE_OF_SERVICE_CODES,
    PLAN_TYPES,
)
from claims_data_simulator.generator.types import GeneratedClaim, GeneratedClaimLine


def _weighted_choice(
    options: list[tuple[str | int, float]], rng: random.Random
) -> str | int:
    """Pick a value from a weighted distribution.

    Args:
        options: List of ``(value, weight)`` pairs.
        rng: Random number generator instance.

    Returns:
        The selected value.
    """
    values, weights = zip(*options, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


def _build_line(
    claim_id: str,
    line_number: int,
    service_date: datetime.date,
    rng: random.Random,
) -> GeneratedClaimLine:
    """Construct a single claim line with randomised clinical codes.

    Args:
        claim_id: Parent claim ID for the line ID.
        line_number: 1-indexed position of this line.
        service_date: Date the service was rendered.
        rng: Random number generator instance.

    Returns:
        A populated ``GeneratedClaimLine``.
    """
    cpt_code, cpt_description, charge_min, charge_max = rng.choice(CPT_CODES)
    charge_amount = Decimal(str(rng.uniform(charge_min, charge_max))).quantize(
        Decimal("0.01")
    )

    modifier_1 = (
        rng.choice(CPT_MODIFIERS) if rng.random() < MODIFIER_1_PROBABILITY else None
    )
    modifier_2 = (
        rng.choice(CPT_MODIFIERS) if rng.random() < MODIFIER_2_PROBABILITY else None
    )

    icd10_primary = rng.choice(ICD10_CODES)
    secondary_count = _weighted_choice(ICD10_SECONDARY_COUNT_WEIGHTS, rng)
    remaining_codes = [c for c in ICD10_CODES if c != icd10_primary]
    icd10_secondary = rng.sample(
        remaining_codes, k=min(int(secondary_count), len(remaining_codes))
    )

    return GeneratedClaimLine(
        line_id=make_line_id(claim_id, line_number),
        line_number=line_number,
        cpt_code=cpt_code,
        cpt_description=cpt_description,
        modifier_1=modifier_1,
        modifier_2=modifier_2,
        icd10_primary=icd10_primary,
        icd10_secondary=icd10_secondary,
        units=1,
        charge_amount=charge_amount,
        allowed_amount=None,
        paid_amount=None,
        service_date=service_date,
    )


def build_new_claim(rng: random.Random | None = None) -> GeneratedClaim:
    """Generate a brand-new claim in ``submitted`` status.

    The claim has 1-5 lines with a weighted distribution (40/30/15/10/5),
    realistic clinical codes, and all adjudication fields set to null.
    ``created_at`` and ``last_updated_at`` are both set to the current
    UTC time.

    Args:
        rng: Random number generator instance.  Defaults to a new
            ``random.Random()`` with system entropy if not provided.

    Returns:
        A fully populated ``GeneratedClaim`` ready for persistence.
    """
    if rng is None:
        rng = random.Random()

    claim_id = next_claim_id()
    now = datetime.datetime.now(datetime.UTC)
    today = now.date()

    payer_id, payer_name = rng.choice(PAYERS)
    payer_prefix = PAYER_PREFIXES[payer_id]
    plan_type = rng.choice(PLAN_TYPES)
    claim_type = str(_weighted_choice(CLAIM_TYPE_WEIGHTS, rng))

    service_date_from = today - datetime.timedelta(days=rng.randint(1, 30))
    if rng.random() < 0.95:
        service_date_to = service_date_from
    else:
        service_date_to = service_date_from + datetime.timedelta(days=rng.randint(1, 5))
    submitted_date = service_date_to + datetime.timedelta(days=rng.randint(1, 7))

    line_count = int(_weighted_choice(LINE_COUNT_WEIGHTS, rng))
    lines: list[GeneratedClaimLine] = []
    for i in range(1, line_count + 1):
        service_date = service_date_from + datetime.timedelta(
            days=rng.randint(0, (service_date_to - service_date_from).days)
        )
        lines.append(_build_line(claim_id, i, service_date, rng))

    total_billed = sum(line.charge_amount for line in lines)

    billing_npi = pick_npi(rng)
    rendering_npi = pick_npi(rng)

    return GeneratedClaim(
        claim_id=claim_id,
        patient_id=pick_patient_id(rng),
        payer_id=payer_id,
        payer_name=payer_name,
        plan_type=plan_type,
        member_id=pick_member_id(payer_prefix, rng),
        group_number=pick_group_number(rng),
        claim_type=claim_type,
        place_of_service=rng.choice(PLACE_OF_SERVICE_CODES),
        billing_provider_npi=billing_npi,
        rendering_provider_npi=rendering_npi,
        service_date_from=service_date_from,
        service_date_to=service_date_to,
        submitted_date=submitted_date,
        adjudicated_date=None,
        status="submitted",
        total_billed_amount=total_billed,
        total_allowed_amount=None,
        total_paid_amount=None,
        patient_responsibility=None,
        denial_reason_code=None,
        created_at=now,
        last_updated_at=now,
        lines=lines,
    )
