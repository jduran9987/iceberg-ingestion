# Healthcare Claims Data Simulator

A FastAPI service that generates simulated but realistic medical claims data for downstream Iceberg and PySpark learning. Claims are persisted in Postgres and evolve through a realistic adjudication lifecycle. Every call returns **all** data (historical + new + updated), giving consumers full freedom to practice incremental loads, Slowly Changing Dimension (SCD) Type II, and data-quality handling patterns.

---

## Table of Contents

1. [About the Data](#about-the-data)
2. [Payload Schema](#payload-schema)
3. [Example Payload](#example-payload)
4. [API Usage](#api-usage)
5. [Simulated Data Quality Issues](#simulated-data-quality-issues)

---

## About the Data

### What a medical claim is

A **medical claim** is the billing record a healthcare provider sends to an insurance payer to request reimbursement for services rendered to a patient. Claims are the highest-volume data entity in healthcare revenue cycle management, and they are rich in standardized coding — which makes them a great domain for learning data engineering patterns.

A claim is not a static record. After the provider submits it, the payer **adjudicates** it over a period of days to weeks, determining what portion of the billed charges are covered, what the patient owes, and whether the claim is approved or rejected. This progression is exactly what makes claims data a natural fit for SCD Type II exercises.

### Claim lifecycle

Every claim starts at `submitted` and advances one step at a time:

```
submitted  ──►  in_review  ──►  paid
                           └──►  denied
```

- **`submitted`** — The provider transmitted the claim. No adjudication information exists yet; allowed/paid amounts are null.
- **`in_review`** — The payer is evaluating the claim. Amounts are still null.
- **`paid`** — The payer approved payment. `total_allowed_amount`, `total_paid_amount`, and `patient_responsibility` are populated based on the plan's fee schedule and the patient's cost-sharing. `adjudicated_date` is set.
- **`denied`** — The payer rejected the claim. Allowed and paid amounts are `0.00`, `patient_responsibility` equals the full billed amount, and a `denial_reason_code` is recorded.

`paid` and `denied` are terminal states — once reached, the claim will not be updated again.

### Nested entity: claim lines

A claim contains one or more **claim lines** (a.k.a. service lines). Each line represents a single billable service — one CPT code, one unit of work, one charge. Multi-line claims are common: for example, an office visit plus a lab panel plus an imaging study would appear as three lines on the same claim. Lines are modeled as a nested child entity with a foreign key back to the parent claim, and they each carry their own monetary fields that mirror the parent-level totals.

### Code systems used

Real claims are built from standardized code systems. This simulator uses the same code systems with realistic (though small) sample pools:

| System   | Purpose                                | Examples in this simulator                                    |
|----------|----------------------------------------|--------------------------------------------------------------|
| **CPT** (Current Procedural Terminology) | What was done to the patient — the service/procedure | `99213` (office visit), `85025` (CBC), `73721` (knee MRI), `45378` (colonoscopy) |
| **ICD-10-CM** | Why the service was done — the diagnosis | `E11.9` (Type 2 diabetes), `I10` (hypertension), `Z12.11` (colon cancer screening) |
| **NPI** (National Provider Identifier) | Who rendered / billed the service | 10-digit numeric string per provider |
| **CMS POS** (Place of Service) | Where the service occurred | `11` (Office), `22` (Outpatient Hospital), `23` (ER) |
| **CPT modifiers** | Extra context on a service line | `25` (significant E/M), `LT`/`RT` (laterality) |
| **CARC** (Claim Adjustment Reason Code) | Why a claim or line was denied | `CO-197` (prior auth missing), `CO-16` (claim lacks info) |

### Payers

The simulator draws from a small pool of representative payers covering commercial, Medicare, and Medicaid lines of business: UnitedHealthcare, Aetna, Cigna, Blue Cross Blue Shield, Humana, Medicare, and Medicaid. Each payer is associated with one of five plan types: `HMO`, `PPO`, `EPO`, `POS`, or `HDHP`.

### Why this data is good for Iceberg practice

- **Mutable records**: the adjudication lifecycle produces genuine in-place updates, ideal for SCD Type II.
- **`created_at` and `last_updated_at`**: baked in, enabling watermark-based incremental loads.
- **Parent/child structure**: claims and claim lines exercise relational modeling across Iceberg tables.
- **Every call returns everything**: consumers must decide for themselves what's new, what's changed, and what's unchanged — exactly the problem space Iceberg merge operations solve.

---

## Payload Schema

Every response is wrapped in an **envelope** containing metadata and the list of claims.

### Envelope

| Field          | Type               | Required | Nullable | Description                                                          |
|----------------|--------------------|----------|----------|----------------------------------------------------------------------|
| `generated_at` | string (ISO 8601)  | Yes      | No       | UTC timestamp when this response was assembled                       |
| `record_count` | integer            | Yes      | No       | Number of entries in `claims` (counts duplicates from data-quality injection) |
| `claims`       | array of Claim     | Yes      | No       | All claims currently in the system; may be empty                     |

### Claim (parent entity)

| Field                    | Type              | Required | Nullable | Description                                                          |
|--------------------------|-------------------|----------|----------|----------------------------------------------------------------------|
| `claim_id`               | string            | Yes      | No       | Natural key. Format: `CLM-<YYYY>-<8-digit sequence>`                 |
| `patient_id`             | string            | Yes      | No\*     | Format: `PAT-<7-digit>`. See [data quality](#simulated-data-quality-issues). |
| `payer_id`               | string            | Yes      | No       | Payer identifier (e.g., `PAYER-UHC-001`)                             |
| `payer_name`             | string            | Yes      | No       | Human-readable payer name                                            |
| `plan_type`              | string            | Yes      | No       | One of `HMO`, `PPO`, `EPO`, `POS`, `HDHP`                            |
| `member_id`              | string            | Yes      | No       | Patient's member ID on the insurance plan                            |
| `group_number`           | string            | Yes      | No       | Employer/group identifier. Format: `GRP-<5 digits>`                   |
| `claim_type`             | string            | Yes      | No       | `professional` or `institutional`                                    |
| `place_of_service`       | string            | Yes      | No       | 2-digit CMS POS code                                                 |
| `billing_provider_npi`   | string            | Yes      | No       | 10-digit NPI of the billing entity                                   |
| `rendering_provider_npi` | string            | Yes      | No       | 10-digit NPI of the rendering clinician                              |
| `service_date_from`      | string (date)     | Yes      | No       | ISO 8601 date (start of service)                                     |
| `service_date_to`        | string (date)     | Yes      | No       | ISO 8601 date (end of service); `>= service_date_from`               |
| `submitted_date`         | string (date)     | Yes      | No       | Date the claim was sent to the payer                                 |
| `adjudicated_date`       | string (date)     | Yes      | Yes      | Populated when status becomes `paid` or `denied`                     |
| `status`                 | string            | Yes      | No       | `submitted`, `in_review`, `paid`, or `denied`                        |
| `total_billed_amount`    | number (2dp)      | Yes      | No       | Sum of line charges                                                  |
| `total_allowed_amount`   | number (2dp)      | Yes      | Yes      | What the payer agreed is reimbursable. Populated on `paid`/`denied`. |
| `total_paid_amount`      | number (2dp)      | Yes      | Yes      | What the payer actually paid. Populated on `paid`/`denied`.          |
| `patient_responsibility` | number (2dp)      | Yes      | Yes      | What the patient owes. Populated on `paid`/`denied`.                 |
| `denial_reason_code`     | string            | **No**   | Yes      | **Omitted from the payload entirely when null.** Populated only on `denied`. |
| `claim_lines`            | array of ClaimLine| Yes      | No       | Child entity — at least one line per claim                           |
| `created_at`             | string (ISO 8601) | Yes      | No       | UTC timestamp when the claim was first created. Immutable.           |
| `last_updated_at`        | string (ISO 8601) | Yes      | No       | UTC timestamp of the most recent change. Equals `created_at` at creation. |

\* `patient_id` is not nullable in the schema or in the persisted database — it is always populated. It only ever appears as `null` in a response via the `null_patient_id=true` data-quality injection, which mutates the response object only. See [Simulated Data Quality Issues](#simulated-data-quality-issues).

### ClaimLine (child entity)

| Field             | Type                | Required | Nullable | Description                                                          |
|-------------------|---------------------|----------|----------|----------------------------------------------------------------------|
| `line_id`         | string              | Yes      | No       | Unique line key. Format: `<claim_id>-L<line_number>`                 |
| `line_number`     | integer             | Yes      | No       | 1-indexed position within the claim                                  |
| `cpt_code`        | string              | Yes      | No       | 5-character CPT/HCPCS code                                           |
| `cpt_description` | string              | Yes      | No       | Human-readable description of the CPT code                           |
| `modifier_1`      | string              | Yes      | Yes      | 2-character CPT modifier, when applicable                            |
| `modifier_2`      | string              | Yes      | Yes      | Second 2-character CPT modifier, when applicable                     |
| `icd10_primary`   | string              | Yes      | No       | Primary ICD-10 diagnosis code for this line                          |
| `icd10_secondary` | array of string     | Yes      | No       | Additional ICD-10 codes; may be an empty array                       |
| `units`           | integer             | Yes      | No       | Service units billed; `>= 1`                                         |
| `charge_amount`   | number (2dp)        | Yes      | No       | Amount billed for this line                                          |
| `allowed_amount`  | number (2dp)        | Yes      | Yes      | Amount the payer allowed for this line. Populated on `paid`/`denied`. |
| `paid_amount`     | number (2dp)        | Yes      | Yes      | Amount the payer paid for this line. Populated on `paid`/`denied`.   |
| `service_date`    | string (date)       | Yes      | No       | Service date for this specific line (within the parent's range)      |

### Summary of optional vs nullable

- **Optional** (may be absent from the payload): `denial_reason_code` only. Absent when the claim is not denied.
- **Nullable** (always present but may be `null`): `adjudicated_date`, `total_allowed_amount`, `total_paid_amount`, `patient_responsibility`, `modifier_1`, `modifier_2`, `allowed_amount`, `paid_amount`.
- **Required and non-nullable**: all other fields, including `patient_id`\*.

---

## Example Payload

The example below shows three claims at different lifecycle stages. Note how `denial_reason_code` appears only on the denied claim, while fields like `adjudicated_date` and the allowed/paid amounts appear as explicit `null` on the in-review claim.

```json
{
  "generated_at": "2026-04-21T14:32:10Z",
  "record_count": 3,
  "claims": [
    {
      "claim_id": "CLM-2026-00018427",
      "patient_id": "PAT-0000451",
      "payer_id": "PAYER-UHC-001",
      "payer_name": "UnitedHealthcare",
      "plan_type": "PPO",
      "member_id": "UHC849201733",
      "group_number": "GRP-44812",
      "claim_type": "professional",
      "place_of_service": "11",
      "billing_provider_npi": "1558332947",
      "rendering_provider_npi": "1194783021",
      "service_date_from": "2026-04-08",
      "service_date_to": "2026-04-08",
      "submitted_date": "2026-04-10",
      "adjudicated_date": "2026-04-18",
      "status": "paid",
      "total_billed_amount": 487.00,
      "total_allowed_amount": 312.45,
      "total_paid_amount": 249.96,
      "patient_responsibility": 62.49,
      "claim_lines": [
        {
          "line_id": "CLM-2026-00018427-L1",
          "line_number": 1,
          "cpt_code": "99213",
          "cpt_description": "Office visit, established patient, 20-29 min",
          "modifier_1": null,
          "modifier_2": null,
          "icd10_primary": "E11.9",
          "icd10_secondary": ["I10", "E78.5"],
          "units": 1,
          "charge_amount": 225.00,
          "allowed_amount": 142.30,
          "paid_amount": 113.84,
          "service_date": "2026-04-08"
        },
        {
          "line_id": "CLM-2026-00018427-L2",
          "line_number": 2,
          "cpt_code": "85025",
          "cpt_description": "Complete blood count with differential",
          "modifier_1": null,
          "modifier_2": null,
          "icd10_primary": "E11.9",
          "icd10_secondary": [],
          "units": 1,
          "charge_amount": 42.00,
          "allowed_amount": 28.15,
          "paid_amount": 22.52,
          "service_date": "2026-04-08"
        },
        {
          "line_id": "CLM-2026-00018427-L3",
          "line_number": 3,
          "cpt_code": "80053",
          "cpt_description": "Comprehensive metabolic panel",
          "modifier_1": null,
          "modifier_2": null,
          "icd10_primary": "E11.9",
          "icd10_secondary": ["E78.5"],
          "units": 1,
          "charge_amount": 220.00,
          "allowed_amount": 142.00,
          "paid_amount": 113.60,
          "service_date": "2026-04-08"
        }
      ],
      "created_at": "2026-04-10T09:14:22Z",
      "last_updated_at": "2026-04-18T16:03:47Z"
    },
    {
      "claim_id": "CLM-2026-00018428",
      "patient_id": "PAT-0001287",
      "payer_id": "PAYER-AET-002",
      "payer_name": "Aetna",
      "plan_type": "HMO",
      "member_id": "AET552918044",
      "group_number": "GRP-10293",
      "claim_type": "professional",
      "place_of_service": "22",
      "billing_provider_npi": "1770293845",
      "rendering_provider_npi": "1770293845",
      "service_date_from": "2026-04-15",
      "service_date_to": "2026-04-15",
      "submitted_date": "2026-04-17",
      "adjudicated_date": null,
      "status": "in_review",
      "total_billed_amount": 1842.50,
      "total_allowed_amount": null,
      "total_paid_amount": null,
      "patient_responsibility": null,
      "claim_lines": [
        {
          "line_id": "CLM-2026-00018428-L1",
          "line_number": 1,
          "cpt_code": "45378",
          "cpt_description": "Colonoscopy, diagnostic",
          "modifier_1": "33",
          "modifier_2": null,
          "icd10_primary": "Z12.11",
          "icd10_secondary": [],
          "units": 1,
          "charge_amount": 1842.50,
          "allowed_amount": null,
          "paid_amount": null,
          "service_date": "2026-04-15"
        }
      ],
      "created_at": "2026-04-17T11:42:08Z",
      "last_updated_at": "2026-04-17T11:42:08Z"
    },
    {
      "claim_id": "CLM-2026-00017993",
      "patient_id": "PAT-0000892",
      "payer_id": "PAYER-CIG-003",
      "payer_name": "Cigna",
      "plan_type": "PPO",
      "member_id": "CIG773104528",
      "group_number": "GRP-88201",
      "claim_type": "professional",
      "place_of_service": "11",
      "billing_provider_npi": "1336682104",
      "rendering_provider_npi": "1829945712",
      "service_date_from": "2026-03-28",
      "service_date_to": "2026-03-28",
      "submitted_date": "2026-03-30",
      "adjudicated_date": "2026-04-20",
      "status": "denied",
      "total_billed_amount": 356.00,
      "total_allowed_amount": 0.00,
      "total_paid_amount": 0.00,
      "patient_responsibility": 356.00,
      "denial_reason_code": "CO-197",
      "claim_lines": [
        {
          "line_id": "CLM-2026-00017993-L1",
          "line_number": 1,
          "cpt_code": "73721",
          "cpt_description": "MRI lower extremity joint without contrast",
          "modifier_1": null,
          "modifier_2": null,
          "icd10_primary": "M25.561",
          "icd10_secondary": [],
          "units": 1,
          "charge_amount": 356.00,
          "allowed_amount": 0.00,
          "paid_amount": 0.00,
          "service_date": "2026-03-28"
        }
      ],
      "created_at": "2026-03-30T08:22:15Z",
      "last_updated_at": "2026-04-20T13:55:31Z"
    }
  ]
}
```

Key things to notice in the example:

- The **paid** claim (first) and the **in-review** claim (second) both lack `denial_reason_code` in their payload — it's omitted entirely, not set to `null`.
- The **denied** claim (third) has `denial_reason_code: "CO-197"`.
- The in-review claim has explicit `null` values for `adjudicated_date`, `total_allowed_amount`, `total_paid_amount`, and `patient_responsibility` — these are **nullable but always present**.
- `created_at` on the paid claim is `2026-04-10T09:14:22Z`; `last_updated_at` is `2026-04-18T16:03:47Z` — the gap reflects the adjudication that happened mid-lifecycle.

---

## API Usage

### Endpoint

```
GET /claims
```

A single endpoint returns the entire state of the simulator, optionally after generating new claims and/or advancing existing ones.

### Query Parameters

All parameters are optional.

| Parameter         | Type    | Default | Description                                                                                                              |
|-------------------|---------|---------|--------------------------------------------------------------------------------------------------------------------------|
| `new`             | integer | `0`     | Number of brand-new claims to generate and persist before returning the response. Must be `>= 0`.                        |
| `updates`         | integer | `0`     | Number of existing non-terminal claims to advance through the lifecycle. Must be `>= 0`.                                 |
| `duplicates`      | boolean | `false` | When `true` **and** `new > 0`, one of the newly generated claims is duplicated in the response. See [data quality](#simulated-data-quality-issues). |
| `null_patient_id` | boolean | `false` | When `true` **and** `new > 0`, one of the newly generated claims has its `patient_id` nulled in the response. See [data quality](#simulated-data-quality-issues). |

### Behavior Notes

- The response always contains **every** claim currently in the database (historical + just-created + just-updated), not just the ones touched by this call.
- New claims are always created in `submitted` status.
- Updates advance a claim one step: `submitted` → `in_review`, or `in_review` → `paid`/`denied`. Terminal claims (`paid`, `denied`) are never selected for update.
- If `updates` exceeds the number of non-terminal claims, every eligible claim is updated (no error).
- On an empty database, `updates=N` returns zero updated claims (no error).
- `duplicates` and `null_patient_id` are silently no-ops when `new == 0`.

### Examples

Fetch whatever currently exists, generate nothing:

```
GET /claims
```

Generate 10 new claims and return everything:

```
GET /claims?new=10
```

Generate 5 new claims, advance 3 existing claims through the lifecycle:

```
GET /claims?new=5&updates=3
```

Generate new claims and inject both data-quality issues into this response:

```
GET /claims?new=5&duplicates=true&null_patient_id=true
```

Only advance existing claims (no new ones):

```
GET /claims?updates=10
```

### Response Codes

| Status | When                                                                 |
|--------|----------------------------------------------------------------------|
| `200`  | Success.                                                             |
| `422`  | Invalid query parameters (e.g., negative integer for `new` / `updates`). |
| `503`  | Database unavailable.                                                |
| `500`  | Unexpected server error.                                             |

---

## Simulated Data Quality Issues

Real-world data pipelines must handle imperfect source data. This simulator intentionally injects two common issues on demand so downstream consumers can practice detection, quarantining, and deduplication logic.

Both issues are **response-only**: they mutate the JSON being returned on this one call and never touch the persisted database state. This is what makes them self-healing.

### `duplicates=true`

**What it does.** If `new > 0`, the service picks one of the claims generated this call and appends a second identical copy of it to the response array. The duplicate has the same `claim_id`, the same `claim_lines`, the same timestamps — everything.

**Why this happens in real life.** Duplicate records appear at the source for many reasons: a provider's billing system retries on transient failures, an EDI gateway redelivers a batch, an operator clicks "submit" twice. Downstream systems must deduplicate by natural key.

**How it self-heals.** Because the duplicate is appended to the response only (not inserted into Postgres), the very next call reads clean rows from the database. Even if the caller passes `duplicates=true` again, a **new** claim from *that* call will be duplicated — the previous call's duplicate is gone.

**Constraints.**
- Only takes effect when `new > 0`. Passing `duplicates=true` with `new=0` is a silent no-op.
- Exactly one duplicate is injected per call.
- The duplicate is appended at the end of the `claims` array to make it easy to spot.
- `record_count` in the envelope **counts the duplicate**, so it will be `new + updates_in_response + historical + 1`.

### `null_patient_id=true`

**What it does.** If `new > 0`, the service picks one of the claims generated this call and sets its `patient_id` to `null` in the response. When both flags are set, the service prefers a different claim than the one chosen for duplication.

**Why this happens in real life.** Missing identifiers are common in source healthcare data: EHR integration failures, manual entry mistakes, patient records not yet matched to the master index, denormalized feeds with partial joins. Downstream pipelines must decide whether to drop, quarantine, or attempt to recover these rows.

**How it self-heals.** The `patient_id` is nulled on the response object only — the underlying row in Postgres retains its real `patient_id`. The next call re-reads the persisted data, and the previously-nulled claim appears with its correct identifier.

**Constraints.**
- Only takes effect when `new > 0`. Passing `null_patient_id=true` with `new=0` is a silent no-op.
- Exactly one claim has its `patient_id` nulled per call.
- When combined with `duplicates=true`, the injector prefers to target two different claims so you can observe both issues on the same response.

### Self-healing summary

Call sequence to demonstrate self-healing:

1. `GET /claims?new=3&duplicates=true&null_patient_id=true` → response contains 4 entries: 3 new + 1 duplicate. One of the new claims has `patient_id: null`.
2. `GET /claims` → response contains 3 entries. No duplicate. The previously-nulled claim now shows its real `patient_id`.
3. `GET /claims?new=2&duplicates=true` → response contains 3 entries: 2 new + 1 duplicate of one of this call's new claims. The original 3 historical claims are clean and unchanged.

Because the corruption never reaches persistence, downstream SCD Type II and deduplication exercises can be designed to detect and recover from these issues without any manual cleanup of the simulator's state.
