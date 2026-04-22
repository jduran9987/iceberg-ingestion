# Healthcare Claims Data Simulator

## Overview

A FastAPI application that generates simulated but realistic medical claims data for downstream Iceberg/PySpark learning exercises. State is persisted in Postgres. A single endpoint returns all historical claims plus newly created and newly updated claims on every call, enabling consumers to practice incremental-load and SCD Type II patterns.

## Tech Stack

- **Python 3.14** managed by **UV**
- **FastAPI** — web framework
- **Postgres** — persistence
- **SQLModel** — ORM / table definitions
- **Pydantic** — external (request/response) validation
- **dataclasses** — internal data structures used by the generator

## Endpoint

`GET /claims`

| Query param        | Type | Default | Description                                                                             |
|--------------------|------|---------|-----------------------------------------------------------------------------------------|
| `new`              | int  | `0`     | Number of brand-new claims to generate and persist                                      |
| `updates`          | int  | `0`     | Number of existing claims to advance through the lifecycle                              |
| `duplicates`       | bool | `false` | If `true` and `new > 0`, one newly created claim is duplicated in the response only     |
| `null_patient_id`  | bool | `false` | If `true` and `new > 0`, one newly created claim has `patient_id` nulled in the response only |

## Behavior Summary

- Returns **all** claims every call: historical + newly created + newly updated.
- New claims are always created in `submitted` status.
- Updates advance a non-terminal claim one step through `submitted` → `in_review` → `paid` / `denied`.
- Terminal states (`paid`, `denied`) are never selected for update.
- If `updates` exceeds the count of eligible claims, every eligible claim is updated (no error).
- On an empty database, `updates=N` returns zero updates (no error).
- `denial_reason_code` is **omitted** from the payload when null. All other nullable fields serialize as explicit `null`.

## Data Quality Self-Healing

Both `duplicates` and `null_patient_id` mutate the **response only**. Persisted state is never corrupted, so the issues self-heal on subsequent calls. See the `api-implementation` skill for the full mechanism.

## Structure

Follows the UV "packaged application" pattern. Implementation, domain, and convention details live in the three skills under `.claude/skills/`. Consult them when working in this directory:

- `.claude/skills/python-conventions` — how to structure code, format, document
- `.claude/skills/healthcare-domain-knowledge` — what the data means and how to generate it
- `.claude/skills/api-implementation` — endpoint wiring, request flow, persistence
