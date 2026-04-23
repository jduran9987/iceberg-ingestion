"""SQLModel table definitions for claims and claim lines.

Maps the ``claim`` and ``claim_line`` tables described in the domain schema
to SQLModel ORM classes backed by Postgres.
"""

import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


class ClaimLine(SQLModel, table=True):
    """A single service line within a medical claim.

    Attributes:
        line_id: Natural key in the format ``<claim_id>-L<line_number>``.
        claim_id: Foreign key referencing the parent claim.
        line_number: 1-indexed position of this line within the claim.
        cpt_code: 5-character CPT/HCPCS procedure code.
        cpt_description: Human-readable label for the CPT code.
        modifier_1: Optional 2-character CPT modifier.
        modifier_2: Optional 2-character CPT modifier.
        icd10_primary: Primary ICD-10 diagnosis code.
        icd10_secondary: Additional ICD-10 codes (may be empty).
        units: Number of service units (>= 1).
        charge_amount: Billed charge for this line.
        allowed_amount: Payer-allowed amount (populated on adjudication).
        paid_amount: Payer-paid amount (populated on adjudication).
        service_date: Date the service was rendered.
    """

    __tablename__ = "claim_line"
    __table_args__ = (sa.Index("ix_claim_line_claim_id", "claim_id"),)

    line_id: str = Field(primary_key=True)
    claim_id: str = Field(
        sa_column=sa.Column(
            sa.String,
            sa.ForeignKey("claim.claim_id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    line_number: int
    cpt_code: str
    cpt_description: str
    modifier_1: str | None = None
    modifier_2: str | None = None
    icd10_primary: str
    icd10_secondary: list[str] = Field(
        sa_column=sa.Column(sa.ARRAY(sa.String), nullable=False, default=[])
    )
    units: int
    charge_amount: Decimal = Field(
        sa_column=sa.Column(sa.Numeric(12, 2), nullable=False)
    )
    allowed_amount: Decimal | None = Field(
        default=None, sa_column=sa.Column(sa.Numeric(12, 2), nullable=True)
    )
    paid_amount: Decimal | None = Field(
        default=None, sa_column=sa.Column(sa.Numeric(12, 2), nullable=True)
    )
    service_date: datetime.date

    claim: "Claim" = Relationship(back_populates="claim_lines")


class Claim(SQLModel, table=True):
    """A medical claim submitted by a provider to a payer.

    Attributes:
        claim_id: Natural key in the format ``CLM-<YYYY>-<8-digit>``.
        patient_id: Patient identifier (NOT NULL at DB level).
        payer_id: Payer organization identifier.
        payer_name: Human-readable payer name.
        plan_type: Insurance plan type (HMO, PPO, EPO, POS, HDHP).
        member_id: Payer-assigned member identifier.
        group_number: Employer group number.
        claim_type: ``professional`` or ``institutional``.
        place_of_service: 2-digit CMS place-of-service code.
        billing_provider_npi: 10-digit NPI of the billing provider.
        rendering_provider_npi: 10-digit NPI of the rendering provider.
        service_date_from: First date of service.
        service_date_to: Last date of service.
        submitted_date: Date the claim was submitted.
        adjudicated_date: Date the claim was adjudicated (nullable).
        status: Lifecycle status of the claim.
        total_billed_amount: Sum of line charge amounts.
        total_allowed_amount: Payer-allowed total (nullable).
        total_paid_amount: Payer-paid total (nullable).
        patient_responsibility: Patient owes this amount (nullable).
        denial_reason_code: CARC code when denied (nullable).
        created_at: Row creation timestamp (immutable).
        last_updated_at: Last modification timestamp.
        claim_lines: Child line items for this claim.
    """

    __tablename__ = "claim"
    __table_args__ = (
        sa.Index("ix_claim_status", "status"),
        sa.Index("ix_claim_last_updated_at", "last_updated_at"),
    )

    claim_id: str = Field(primary_key=True)
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
    adjudicated_date: datetime.date | None = None
    status: str
    total_billed_amount: Decimal = Field(
        sa_column=sa.Column(sa.Numeric(12, 2), nullable=False)
    )
    total_allowed_amount: Decimal | None = Field(
        default=None, sa_column=sa.Column(sa.Numeric(12, 2), nullable=True)
    )
    total_paid_amount: Decimal | None = Field(
        default=None, sa_column=sa.Column(sa.Numeric(12, 2), nullable=True)
    )
    patient_responsibility: Decimal | None = Field(
        default=None, sa_column=sa.Column(sa.Numeric(12, 2), nullable=True)
    )
    denial_reason_code: str | None = None
    created_at: datetime.datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
        )
    )
    last_updated_at: datetime.datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
        )
    )

    claim_lines: list[ClaimLine] = Relationship(
        back_populates="claim",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
