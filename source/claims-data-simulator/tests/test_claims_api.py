"""Integration tests for the GET /claims endpoint.

Each test exercises a behavior from the api-implementation skill's
Testing Surface section, hitting a real Postgres instance via
testcontainers.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_new_persists_submitted_claims(client: AsyncClient) -> None:
    """GET /claims?new=3 persists 3 claims in submitted status."""
    resp = await client.get("/claims", params={"new": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 3
    assert len(data["claims"]) == 3
    for claim in data["claims"]:
        assert claim["status"] == "submitted"


async def test_updates_on_empty_db(client: AsyncClient) -> None:
    """GET /claims?updates=2 on empty DB returns 0 claims, no error."""
    resp = await client.get("/claims", params={"updates": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 0
    assert data["claims"] == []


async def test_sequential_new_and_update_advances_status(
    client: AsyncClient,
) -> None:
    """Two sequential calls with new=1 then updates=1 advance the claim.

    The first call creates a claim in ``submitted``.  The second call
    creates another new claim and advances the first to ``in_review``.
    """
    resp1 = await client.get("/claims", params={"new": 1})
    assert resp1.status_code == 200
    first_claims = resp1.json()["claims"]
    assert len(first_claims) == 1
    first_id = first_claims[0]["claim_id"]
    assert first_claims[0]["status"] == "submitted"

    resp2 = await client.get("/claims", params={"new": 1, "updates": 1})
    assert resp2.status_code == 200
    second_claims = resp2.json()["claims"]
    assert len(second_claims) == 2

    advanced = next(c for c in second_claims if c["claim_id"] == first_id)
    assert advanced["status"] == "in_review"


async def test_duplicates_flag_appends_copy(client: AsyncClient) -> None:
    """GET /claims?new=2&duplicates=true returns 3 entries with a duplicate.

    Two claims share the same ``claim_id`` — the original and the
    duplicate appended at the end.
    """
    resp = await client.get("/claims", params={"new": 2, "duplicates": "true"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_count"] == 3
    assert len(data["claims"]) == 3

    claim_ids = [c["claim_id"] for c in data["claims"]]
    duplicated_ids = [cid for cid in set(claim_ids) if claim_ids.count(cid) == 2]
    assert len(duplicated_ids) == 1


async def test_duplicates_flag_noop_when_no_new(client: AsyncClient) -> None:
    """Subsequent call with duplicates=true and new=0 returns no duplicates.

    First seed the DB, then call with only the flag — no duplication
    should occur because no new claims were created on this request.
    """
    await client.get("/claims", params={"new": 2})
    resp = await client.get("/claims", params={"duplicates": "true"})
    assert resp.status_code == 200
    data = resp.json()
    claim_ids = [c["claim_id"] for c in data["claims"]]
    assert len(claim_ids) == len(set(claim_ids)), "No duplicates expected"


async def test_null_patient_id_flag(client: AsyncClient) -> None:
    """GET /claims?new=2&null_patient_id=true nulls exactly one patient_id."""
    resp = await client.get("/claims", params={"new": 2, "null_patient_id": "true"})
    assert resp.status_code == 200
    claims = resp.json()["claims"]
    null_patient_claims = [c for c in claims if c["patient_id"] is None]
    assert len(null_patient_claims) == 1


async def test_null_patient_id_self_heals(client: AsyncClient) -> None:
    """A subsequent call with new=0 restores the previously-nulled patient_id.

    This proves the database was never corrupted by the injection.
    """
    resp1 = await client.get("/claims", params={"new": 2, "null_patient_id": "true"})
    claims1 = resp1.json()["claims"]
    nulled = [c for c in claims1 if c["patient_id"] is None]
    assert len(nulled) == 1
    nulled_id = nulled[0]["claim_id"]

    resp2 = await client.get("/claims")
    assert resp2.status_code == 200
    claims2 = resp2.json()["claims"]
    restored = next(c for c in claims2 if c["claim_id"] == nulled_id)
    assert restored["patient_id"] is not None


async def test_paid_claim_omits_denial_reason_code(
    client: AsyncClient,
) -> None:
    """A paid claim's JSON has no ``denial_reason_code`` key at all."""
    await client.get("/claims", params={"new": 50})
    await client.get("/claims", params={"updates": 50})
    resp = await client.get("/claims", params={"updates": 50})
    data = resp.json()

    paid_claims = [c for c in data["claims"] if c["status"] == "paid"]
    assert len(paid_claims) > 0, "Expected at least one paid claim"
    for claim in paid_claims:
        assert "denial_reason_code" not in claim


async def test_denied_claim_has_denial_reason_code(
    client: AsyncClient,
) -> None:
    """A denied claim's JSON has ``denial_reason_code`` as a non-null string."""
    await client.get("/claims", params={"new": 50})
    await client.get("/claims", params={"updates": 50})
    resp = await client.get("/claims", params={"updates": 50})
    data = resp.json()

    denied_claims = [c for c in data["claims"] if c["status"] == "denied"]
    assert len(denied_claims) > 0, "Expected at least one denied claim"
    for claim in denied_claims:
        assert "denial_reason_code" in claim
        assert isinstance(claim["denial_reason_code"], str)
        assert len(claim["denial_reason_code"]) > 0
