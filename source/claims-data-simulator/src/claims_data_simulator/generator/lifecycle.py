"""Claim lifecycle transitions and adjudication amount computation.

Advances claims through the lifecycle (``submitted`` -> ``in_review``
-> ``paid``/``denied``) and populates monetary fields according to the
domain rules.
"""

import datetime
import random
from decimal import Decimal

from claims_data_simulator.db.models import Claim
from claims_data_simulator.generator.reference import (
    ALLOWED_AMOUNT_RANGE,
    CARC_DENIAL_CODES,
    PAID_AMOUNT_RANGE,
    PAID_PROBABILITY,
)
from claims_data_simulator.generator.types import AmountAllocation, LifecycleTransition


def _compute_paid_transition(claim: Claim, rng: random.Random) -> LifecycleTransition:
    """Compute amounts for a claim transitioning to ``paid``.

    Args:
        claim: The claim being adjudicated.
        rng: Random number generator instance.

    Returns:
        A ``LifecycleTransition`` with populated monetary fields.
    """
    today = datetime.datetime.now(datetime.UTC).date()
    billed = claim.total_billed_amount

    allowed_frac = Decimal(
        str(rng.uniform(float(ALLOWED_AMOUNT_RANGE[0]), float(ALLOWED_AMOUNT_RANGE[1])))
    )
    total_allowed = (billed * allowed_frac).quantize(Decimal("0.01"))

    paid_frac = Decimal(
        str(rng.uniform(float(PAID_AMOUNT_RANGE[0]), float(PAID_AMOUNT_RANGE[1])))
    )
    total_paid = (total_allowed * paid_frac).quantize(Decimal("0.01"))
    patient_resp = total_allowed - total_paid

    return LifecycleTransition(
        new_status="paid",
        adjudicated_date=today,
        total_allowed_amount=total_allowed,
        total_paid_amount=total_paid,
        patient_responsibility=patient_resp,
        denial_reason_code=None,
    )


def _compute_denied_transition(claim: Claim, rng: random.Random) -> LifecycleTransition:
    """Compute amounts for a claim transitioning to ``denied``.

    Args:
        claim: The claim being denied.
        rng: Random number generator instance.

    Returns:
        A ``LifecycleTransition`` with zeroed amounts and a CARC code.
    """
    today = datetime.datetime.now(datetime.UTC).date()
    return LifecycleTransition(
        new_status="denied",
        adjudicated_date=today,
        total_allowed_amount=Decimal("0.00"),
        total_paid_amount=Decimal("0.00"),
        patient_responsibility=claim.total_billed_amount,
        denial_reason_code=rng.choice(CARC_DENIAL_CODES),
    )


def _allocate_line_amounts(
    claim: Claim, transition: LifecycleTransition
) -> list[AmountAllocation]:
    """Distribute claim-level amounts across lines proportionally.

    Each line receives a share of ``total_allowed_amount`` and
    ``total_paid_amount`` proportional to its ``charge_amount`` relative
    to the claim's ``total_billed_amount``.  Rounding residuals are
    assigned to the last line to preserve exact totals.

    Args:
        claim: The claim whose lines will receive allocations.
        transition: The computed transition with claim-level totals.

    Returns:
        One ``AmountAllocation`` per line, ordered by ``line_number``.
    """
    lines = sorted(claim.claim_lines, key=lambda ln: ln.line_number)
    total_billed = claim.total_billed_amount
    total_allowed = transition.total_allowed_amount or Decimal("0.00")
    total_paid = transition.total_paid_amount or Decimal("0.00")

    allocations: list[AmountAllocation] = []
    running_allowed = Decimal("0.00")
    running_paid = Decimal("0.00")

    for i, line in enumerate(lines):
        is_last = i == len(lines) - 1
        if is_last:
            line_allowed = total_allowed - running_allowed
            line_paid = total_paid - running_paid
        else:
            share = line.charge_amount / total_billed if total_billed else Decimal("0")
            line_allowed = (total_allowed * share).quantize(Decimal("0.01"))
            line_paid = (total_paid * share).quantize(Decimal("0.01"))
            running_allowed += line_allowed
            running_paid += line_paid

        allocations.append(
            AmountAllocation(
                line_number=line.line_number,
                allowed_amount=line_allowed,
                paid_amount=line_paid,
            )
        )

    return allocations


def advance_status(claim: Claim, rng: random.Random | None = None) -> None:
    """Move a claim one step through the lifecycle, mutating it in place.

    Transition rules:

    - ``submitted`` -> ``in_review``: bumps ``last_updated_at`` only.
    - ``in_review`` -> ``paid`` (70%) or ``denied`` (30%): populates
      adjudication fields and distributes amounts to lines.

    Terminal claims (``paid``, ``denied``) raise ``ValueError``.

    Args:
        claim: The SQLModel ``Claim`` to advance.  Modified in place.
        rng: Random number generator instance.  Defaults to a new
            ``random.Random()`` with system entropy if not provided.

    Raises:
        ValueError: If the claim is already in a terminal status.
    """
    if rng is None:
        rng = random.Random()

    now = datetime.datetime.now(datetime.UTC)

    if claim.status == "submitted":
        claim.status = "in_review"
        claim.last_updated_at = now
        return

    if claim.status == "in_review":
        if rng.random() < PAID_PROBABILITY:
            transition = _compute_paid_transition(claim, rng)
        else:
            transition = _compute_denied_transition(claim, rng)

        claim.status = transition.new_status
        claim.adjudicated_date = transition.adjudicated_date
        claim.total_allowed_amount = transition.total_allowed_amount
        claim.total_paid_amount = transition.total_paid_amount
        claim.patient_responsibility = transition.patient_responsibility
        claim.denial_reason_code = transition.denial_reason_code
        claim.last_updated_at = now

        allocations = _allocate_line_amounts(claim, transition)
        lines_by_number = {ln.line_number: ln for ln in claim.claim_lines}
        for alloc in allocations:
            line = lines_by_number[alloc.line_number]
            line.allowed_amount = alloc.allowed_amount
            line.paid_amount = alloc.paid_amount

        return

    raise ValueError(
        f"Cannot advance claim {claim.claim_id}: status '{claim.status}' is terminal."
    )
