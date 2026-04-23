"""Response-only data-quality mutations for testing downstream pipelines.

Both injection functions operate on response objects only and never touch
persisted state.  They deep-copy targets before mutating so that
in-memory SQLModel entities remain clean.
"""

import copy
import random
from typing import Any


def inject_duplicate(
    response_claims: list[Any],
    newly_created_ids: set[str],
    rng: random.Random | None = None,
) -> list[Any]:
    """Append a duplicate of one newly created claim to the response.

    If ``newly_created_ids`` is empty the function is a no-op and returns
    the list unchanged.  The duplicate is deep-copied and appended at the
    end of the list so it is easy to spot.

    Args:
        response_claims: The mutable list of response claim objects.
        newly_created_ids: Claim IDs created in the current request.
        rng: Random number generator.  Defaults to a new
            ``random.Random()`` with system entropy if not provided.

    Returns:
        The same ``response_claims`` list (possibly with one appended entry).
    """
    if not newly_created_ids:
        return response_claims

    if rng is None:
        rng = random.Random()

    candidates = [c for c in response_claims if c.claim_id in newly_created_ids]
    if not candidates:
        return response_claims

    target = rng.choice(candidates)
    response_claims.append(copy.deepcopy(target))
    return response_claims


def inject_null_patient_id(
    response_claims: list[Any],
    newly_created_ids: set[str],
    avoid_ids: set[str] | None = None,
    rng: random.Random | None = None,
) -> tuple[list[Any], str | None]:
    """Null the ``patient_id`` of one newly created claim in the response.

    If ``newly_created_ids`` is empty the function is a no-op.  When
    possible, the target is chosen from IDs not present in ``avoid_ids``
    so that duplicate and null-patient injections hit different claims.
    The target is deep-copied before mutation and replaces the original
    in the list.

    Args:
        response_claims: The mutable list of response claim objects.
        newly_created_ids: Claim IDs created in the current request.
        avoid_ids: Claim IDs to avoid when picking a target (best-effort).
        rng: Random number generator.  Defaults to a new
            ``random.Random()`` with system entropy if not provided.

    Returns:
        A tuple of (``response_claims``, modified ``claim_id``).  The
        ``claim_id`` is ``None`` when no mutation occurred.
    """
    if not newly_created_ids:
        return response_claims, None

    if rng is None:
        rng = random.Random()
    if avoid_ids is None:
        avoid_ids = set()

    candidates = [c for c in response_claims if c.claim_id in newly_created_ids]
    if not candidates:
        return response_claims, None

    preferred = [c for c in candidates if c.claim_id not in avoid_ids]
    target = rng.choice(preferred) if preferred else rng.choice(candidates)

    mutated = copy.deepcopy(target)
    mutated.patient_id = None

    idx = next(
        i
        for i, c in enumerate(response_claims)
        if c.claim_id == target.claim_id and c is target
    )
    response_claims[idx] = mutated
    return response_claims, mutated.claim_id
