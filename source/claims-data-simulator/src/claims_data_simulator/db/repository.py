"""CRUD operations for claims and claim lines.

All database reads and writes for the claims simulator flow through
this module so that persistence logic is isolated from the API and
generator layers.
"""

from sqlmodel import Session, select

from claims_data_simulator.db.models import Claim


def list_all_claims(session: Session) -> list[Claim]:
    """Return every claim with its lines, ordered for stable output.

    Claims are ordered by ``created_at ASC, claim_id ASC``.  Lines
    within each claim are ordered by ``line_number ASC``.

    Args:
        session: Active database session.

    Returns:
        All persisted claims with eagerly loaded lines.
    """
    statement = (
        select(Claim).order_by(Claim.created_at.asc(), Claim.claim_id.asc())  # type: ignore[union-attr]
    )
    claims = list(session.exec(statement).all())
    for claim in claims:
        claim.claim_lines.sort(key=lambda line: line.line_number)
    return claims


def list_eligible_for_update(session: Session, limit: int) -> list[Claim]:
    """Return claims eligible for a lifecycle status advance.

    Eligible claims have status ``submitted`` or ``in_review``.  They
    are ordered by ``last_updated_at ASC`` so the oldest are advanced
    first.  At most ``limit`` claims are returned.

    Args:
        session: Active database session.
        limit: Maximum number of eligible claims to return.

    Returns:
        Up to ``limit`` eligible claims, oldest first.
    """
    statement = (
        select(Claim)
        .where(Claim.status.in_(["submitted", "in_review"]))  # type: ignore[union-attr]
        .order_by(Claim.last_updated_at.asc())  # type: ignore[union-attr]
        .limit(limit)
    )
    return list(session.exec(statement).all())


def insert_claim(session: Session, claim: Claim) -> None:
    """Persist a new claim and its lines to the database.

    The caller is responsible for committing the transaction.

    Args:
        session: Active database session.
        claim: The claim to insert (with ``claim_lines`` populated).
    """
    session.add(claim)


def update_claim(session: Session, claim: Claim) -> None:
    """Merge updated claim state into the session.

    The caller is responsible for committing the transaction.  Typically
    the claim was already loaded within the same session, so this is a
    no-op merge — the dirty attributes are flushed on commit.

    Args:
        session: Active database session.
        claim: The claim with modified attributes.
    """
    session.add(claim)
