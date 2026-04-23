"""ID generation for claims, patients, members, providers, and lines.

Maintains pre-generated pools of recurring identifiers so that
downstream analytics can practice joins and dimension modeling with
realistic data repetition.
"""

import datetime
import random
import threading

_claim_sequence_lock = threading.Lock()
_claim_sequence: int = 0

_rng = random.Random()

PATIENT_POOL: list[str] = [f"PAT-{i:07d}" for i in range(1, 501)]
"""Pool of ~500 recurring patient identifiers."""

MEMBER_SUFFIX_POOL: list[str] = [
    f"{_rng.randint(100_000_000, 999_999_999)}" for _ in range(500)
]
"""Pool of ~500 recurring 9-digit member ID suffixes."""

GROUP_NUMBER_POOL: list[str] = [
    f"GRP-{_rng.randint(10_000, 99_999)}" for _ in range(30)
]
"""Pool of ~30 recurring group numbers."""

NPI_POOL: list[str] = [
    f"{_rng.randint(1_000_000_000, 9_999_999_999)}" for _ in range(50)
]
"""Pool of ~50 recurring 10-digit NPI numbers."""


def next_claim_id() -> str:
    """Generate the next globally unique claim ID.

    Format: ``CLM-<YYYY>-<8-digit sequence>``.  Thread-safe via a lock
    on the sequence counter.

    Returns:
        A new claim ID string.
    """
    global _claim_sequence  # noqa: PLW0603
    with _claim_sequence_lock:
        _claim_sequence += 1
        seq = _claim_sequence
    year = datetime.datetime.now(datetime.UTC).year
    return f"CLM-{year}-{seq:08d}"


def pick_patient_id(rng: random.Random) -> str:
    """Select a patient ID from the recurring pool.

    Args:
        rng: Random number generator instance.

    Returns:
        A patient ID string.
    """
    return rng.choice(PATIENT_POOL)


def pick_member_id(payer_prefix: str, rng: random.Random) -> str:
    """Select a member ID from the recurring pool for a given payer.

    Combines the payer's 3-letter prefix with a 9-digit suffix drawn
    from the pool.

    Args:
        payer_prefix: 3-letter payer prefix (e.g. ``UHC``).
        rng: Random number generator instance.

    Returns:
        A member ID string (e.g. ``UHC849201733``).
    """
    suffix = rng.choice(MEMBER_SUFFIX_POOL)
    return f"{payer_prefix}{suffix}"


def pick_group_number(rng: random.Random) -> str:
    """Select a group number from the recurring pool.

    Args:
        rng: Random number generator instance.

    Returns:
        A group number string (e.g. ``GRP-44812``).
    """
    return rng.choice(GROUP_NUMBER_POOL)


def pick_npi(rng: random.Random) -> str:
    """Select an NPI from the recurring provider pool.

    Args:
        rng: Random number generator instance.

    Returns:
        A 10-digit NPI string.
    """
    return rng.choice(NPI_POOL)


def make_line_id(claim_id: str, line_number: int) -> str:
    """Build a line ID from its parent claim ID and line number.

    Args:
        claim_id: The parent claim's ID.
        line_number: 1-indexed line position.

    Returns:
        A line ID string (e.g. ``CLM-2026-00000001-L1``).
    """
    return f"{claim_id}-L{line_number}"
