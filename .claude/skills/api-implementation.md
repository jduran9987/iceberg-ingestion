---
name: api-implementation
description: Implementation blueprint for the claims-simulator FastAPI service — endpoint definition, query-parameter validation, request flow, persistence model, SCD II update behavior, and response-only data-quality injection. Use whenever building, modifying, debugging, or testing the API layer, the generator, or the database interactions.
---

# API Implementation

## Endpoint

`GET /claims`

All query parameters are optional and must use FastAPI `Query` validators:

| Name              | Type | Default | Constraint                                  |
|-------------------|------|---------|---------------------------------------------|
| `new`             | int  | `0`     | `ge=0`                                      |
| `updates`         | int  | `0`     | `ge=0`                                      |
| `duplicates`      | bool | `false` | Has effect only when `new > 0`              |
| `null_patient_id` | bool | `false` | Has effect only when `new > 0`              |

## Response Shape

```json
{
  "generated_at": "<iso8601 UTC timestamp>",
  "record_count": <int>,
  "claims": [ ... ]
}
```

`record_count` is `len(claims)` **after** data-quality injection (so a duplicate row is counted).

`claims` are ordered by `created_at ASC, claim_id ASC` for stability. A duplicate-injected row is appended at the end of the array so it is easy to spot.

## Request Flow

Steps executed per request, in order:

1. **Generate new claims** (`new` count). Each new claim:
   - Gets `status = "submitted"`.
   - Has 1–5 lines (see healthcare-domain-knowledge skill for distribution).
   - Has null adjudication fields (see lifecycle rules).
   - Sets `created_at = last_updated_at = now()` (UTC).
   - Is **persisted** to Postgres along with its lines.
2. **Apply updates** (`updates` count):
   - Query eligible claims: `WHERE status IN ('submitted', 'in_review')`, ordered by `last_updated_at ASC` (advance oldest first).
   - Take up to `updates` of them.
   - Advance each one step through the lifecycle (`submitted` → `in_review`, or `in_review` → `paid`/`denied` — 70% paid / 30% denied).
   - Populate amounts per the domain-knowledge rules.
   - Set `last_updated_at = now()`; keep `created_at` unchanged.
   - **Persist** parent and line changes.
   - If fewer eligible than requested, update all eligible (no error).
   - If none eligible, skip silently.
3. **Read all claims** from Postgres (load parents + their lines).
4. **Inject data-quality issues** into the response list only (never persisted):
   - If `duplicates=True` **and** at least one claim was newly created in step 1, pick one of the newly created claims and append a second copy of it to the response array.
   - If `null_patient_id=True` **and** at least one claim was newly created in step 1, pick one of the newly created claims (prefer a different one than the duplicate target if both flags are set) and set its `patient_id` to `None` on the response copy only.
5. **Serialize**. `denial_reason_code` is omitted from the JSON when null; all other nullable fields serialize as explicit `null`.
6. Return `{generated_at, record_count, claims}`.

## Omitting `denial_reason_code` When Null

Use Pydantic's per-field exclusion. Define the response model with `denial_reason_code: str | None = None` and call `model_dump(exclude_none=False)` globally, **except** apply `exclude_none=True` scoped to that single key. The cleanest pattern is a custom serializer on the response model that drops `denial_reason_code` from the emitted dict only when it is `None`. Do **not** use a blanket `exclude_none=True` — that would also drop `adjudicated_date`, `total_allowed_amount`, etc., which must appear as explicit null.

## Persistence Model (SQLModel)

Two tables only:

### `claim`
Primary key: `claim_id` (string, natural key).
All parent fields from the domain schema, plus `created_at` and `last_updated_at` (both `timestamptz NOT NULL`).
`patient_id` is **NOT NULL** at the DB level — nulling happens only in the response.

### `claim_line`
Primary key: `line_id`.
Foreign key: `claim_id` → `claim.claim_id` (ON DELETE CASCADE).
All line fields from the domain schema.
Store `icd10_secondary` as a Postgres `text[]` (array column); in SQLModel use `sa_column=Column(ARRAY(String))`.

### Indexes
- `claim(status)` — used in the update-eligibility query.
- `claim(last_updated_at)` — used to order update candidates.
- `claim_line(claim_id)` — FK lookup.

## Pydantic vs SQLModel vs dataclasses

- **SQLModel** — the two DB tables above. Never returned directly from the endpoint.
- **Pydantic** — query parameter validation (via `Query`), and response models: `ClaimLineResponse`, `ClaimResponse`, `ClaimsEnvelopeResponse`. Translate SQLModel rows into `ClaimResponse` at the API boundary.
- **dataclasses** — internal generator types:
  - `GeneratedClaim` / `GeneratedClaimLine` — in-memory representation produced by the generator before persistence.
  - `LifecycleTransition` — describes a status change and derived amounts.
  - `AmountAllocation` — per-line distribution result when moving to `paid`.

## Module Layout

```
source/src/claims_simulator/
├── __init__.py
├── main.py               # FastAPI app construction, lifespan, route registration
├── config.py             # pydantic-settings (DB URL, etc.)
├── api/
│   ├── __init__.py
│   ├── routes.py         # GET /claims handler
│   └── schemas.py        # Pydantic request/response models
├── db/
│   ├── __init__.py
│   ├── models.py         # SQLModel tables
│   ├── session.py        # engine, session factory, get_session dependency
│   └── repository.py     # CRUD: list_all, list_eligible_for_update, insert, update
├── generator/
│   ├── __init__.py
│   ├── reference.py      # Payer/CPT/ICD/POS/CARC pools as module-level constants
│   ├── ids.py            # ID generators (claim_id sequence, NPI, member_id, etc.)
│   ├── new_claim.py      # Build a fresh `submitted` claim (+ lines)
│   ├── lifecycle.py      # advance_status, compute_paid_amounts, compute_denied_amounts
│   └── types.py          # Internal dataclasses
└── quality/
    ├── __init__.py
    └── inject.py         # duplicates + null_patient_id response-only mutations
```

## Self-Healing Data Quality

The mutations in `quality/inject.py` operate on the already-serialized-or-about-to-be-serialized list of response objects. They do **not** touch the SQLModel entities, the session, or the DB. Because persisted state is never corrupted, a subsequent call (without the flag, or with the flag but on a different new row) produces a clean payload for the previously-affected claim_id.

Important invariants:
- The `duplicates` and `null_patient_id` flags must be **no-ops when `new == 0`**. Enforce this in `inject.py`, not by rejecting the request — the API accepts the flags regardless and they just have nothing to act on.
- Injection must never mutate the in-memory objects that might still be referenced elsewhere. Deep-copy the target claim (and its lines) before mutating.

## Error Handling

| Condition                                       | Behavior                                     |
|-------------------------------------------------|----------------------------------------------|
| `new` or `updates` negative                     | 422 (FastAPI `Query(ge=0)` validator)        |
| Empty DB + `updates > 0`                        | 200 OK, normal response, possibly no claims  |
| Postgres unavailable                            | 503 Service Unavailable                      |
| Any other unexpected generator/DB exception     | 500 Internal Server Error                    |

## Determinism & Ordering

- `claims` array: ordered by `created_at ASC, claim_id ASC`. A duplicate-injected row is appended at the end.
- `claim_lines` within a claim: ordered by `line_number ASC`.
- Use a seeded RNG only when a test fixture requires it — production runtime uses `random.Random()` with system entropy.

## Testing Surface

At minimum the following should be verifiable:

- `GET /claims?new=3` — persists 3 claims in `submitted`, returns 3 claims.
- `GET /claims?updates=2` on empty DB — returns 0 claims, no error.
- `GET /claims?new=1&updates=1` called twice in sequence — second call shows first call's claim advanced to `in_review`.
- `GET /claims?new=2&duplicates=true` — response has 3 entries; 2 share the same `claim_id`.
- Subsequent `GET /claims?duplicates=true` with `new=0` — response has no duplicates.
- `GET /claims?new=2&null_patient_id=true` — exactly one of the new claims has `patient_id: null` in the response.
- Subsequent `GET /claims` with `new=0` — the previously-nulled `patient_id` is present again (proving the DB was never corrupted).
- Paid claim serializes without the `denial_reason_code` key entirely.
- Denied claim serializes with `denial_reason_code` as a non-null string.

## Running Locally

```bash
# from source/
uv sync
uv run uvicorn claims_simulator.main:app --reload --host 0.0.0.0 --port 8000
```

In production / docker-compose, use `uv run uvicorn ...` as the container CMD.
