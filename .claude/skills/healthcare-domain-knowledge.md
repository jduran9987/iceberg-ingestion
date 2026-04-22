---
name: healthcare-domain-knowledge
description: Domain knowledge for generating realistic simulated medical claims data. Use whenever implementing the claims generator, deciding realistic field values, defining the claims or claim-line schema, writing documentation about claims data, or populating adjudication amounts. Covers the claim lifecycle, CPT/ICD-10/NPI/POS/CARC code pools, realistic ID formats, and payload structure.
---

# Healthcare Claims Domain Knowledge

## What a Claim Is

A medical claim is the billing record a healthcare provider sends to an insurance payer to request reimbursement for services rendered to a patient. A claim is **adjudicated** over time — it moves through a lifecycle and its monetary fields are populated by the payer as the claim is processed. Claims are the highest-volume data entity in a healthcare revenue cycle.

## Claim Lifecycle

All new claims start in `submitted`. An update advances the claim exactly one step:

1. `submitted` — provider has transmitted the claim; no adjudication info yet.
2. `in_review` — payer is evaluating.
3. `paid` **or** `denied` — terminal states; never updated again.

### Field population by status

**`submitted`** (creation):
- `adjudicated_date`: null
- `total_allowed_amount`: null
- `total_paid_amount`: null
- `patient_responsibility`: null
- `denial_reason_code`: null
- Line-level `allowed_amount`, `paid_amount`: null

**`in_review`** (review):
- Same nulls as `submitted`.
- Bump `last_updated_at`.

**`paid`**:
- `adjudicated_date`: today.
- `total_allowed_amount`: 60–80% of `total_billed_amount` (uniform random).
- `total_paid_amount`: 75–95% of `total_allowed_amount`.
- `patient_responsibility`: `total_allowed_amount - total_paid_amount`.
- `denial_reason_code`: stays null.
- Line `allowed_amount` / `paid_amount`: distribute proportionally from the totals based on each line's share of `charge_amount`.

**`denied`**:
- `adjudicated_date`: today.
- `total_allowed_amount`: `0.00`.
- `total_paid_amount`: `0.00`.
- `patient_responsibility`: equals `total_billed_amount`.
- `denial_reason_code`: random CARC code from the pool below.
- Line `allowed_amount` / `paid_amount`: `0.00`.

Round all amounts to 2 decimal places. The `patient_responsibility` should equal `total_allowed - total_paid` exactly after rounding.

## Parent Schema — `Claim`

| Field                    | Type          | Required | Nullable | Notes                                                        |
|--------------------------|---------------|----------|----------|--------------------------------------------------------------|
| `claim_id`               | string        | Yes      | No       | Natural key; format `CLM-<YYYY>-<8-digit sequence>`          |
| `patient_id`             | string        | Yes      | No*      | Format `PAT-<7-digit>`. See data-quality notes.              |
| `payer_id`               | string        | Yes      | No       |                                                              |
| `payer_name`             | string        | Yes      | No       | e.g., UnitedHealthcare, Aetna, Cigna                         |
| `plan_type`              | string        | Yes      | No       | `HMO`, `PPO`, `EPO`, `POS`, `HDHP`                           |
| `member_id`              | string        | Yes      | No       | 3-letter payer prefix + 9 digits                             |
| `group_number`           | string        | Yes      | No       | Format `GRP-<5 digits>`                                       |
| `claim_type`             | string        | Yes      | No       | `professional` or `institutional`                             |
| `place_of_service`       | string        | Yes      | No       | CMS POS code (2-digit string)                                |
| `billing_provider_npi`   | string        | Yes      | No       | 10-digit NPI                                                 |
| `rendering_provider_npi` | string        | Yes      | No       | 10-digit NPI                                                 |
| `service_date_from`      | date          | Yes      | No       |                                                              |
| `service_date_to`        | date          | Yes      | No       | `>= service_date_from`                                        |
| `submitted_date`         | date          | Yes      | No       | `>= service_date_to`                                          |
| `adjudicated_date`       | date          | Yes      | Yes      | Populated on `paid`/`denied`                                 |
| `status`                 | string        | Yes      | No       | `submitted`, `in_review`, `paid`, `denied`                    |
| `total_billed_amount`    | decimal(12,2) | Yes      | No       | Sum of line `charge_amount`                                   |
| `total_allowed_amount`   | decimal(12,2) | Yes      | Yes      | Populated on `paid`/`denied`                                 |
| `total_paid_amount`      | decimal(12,2) | Yes      | Yes      | Populated on `paid`/`denied`                                 |
| `patient_responsibility` | decimal(12,2) | Yes      | Yes      | Populated on `paid`/`denied`                                 |
| `denial_reason_code`     | string        | No       | Yes      | **Omitted from payload when null**                           |
| `claim_lines`            | array         | Yes      | No       | Nested child entity, min 1                                   |
| `created_at`             | timestamp     | Yes      | No       | Immutable after creation                                     |
| `last_updated_at`        | timestamp     | Yes      | No       | Equals `created_at` on creation; bumped on any mutation      |

`*` `patient_id` is **not nullable** in the schema or in the persisted database — it is always populated. It only ever appears as `null` in a response via the `null_patient_id=true` data-quality injection, which mutates the response object only (see the api-implementation skill).

## Child Schema — `ClaimLine`

| Field             | Type          | Required | Nullable | Notes                                                  |
|-------------------|---------------|----------|----------|--------------------------------------------------------|
| `line_id`         | string        | Yes      | No       | Format `<claim_id>-L<line_number>`                      |
| `line_number`     | int           | Yes      | No       | 1-indexed                                              |
| `cpt_code`        | string        | Yes      | No       | 5-char CPT/HCPCS                                       |
| `cpt_description` | string        | Yes      | No       | Human-readable text for the CPT code                   |
| `modifier_1`      | string        | Yes      | Yes      | 2-char CPT modifier                                    |
| `modifier_2`      | string        | Yes      | Yes      | 2-char CPT modifier                                    |
| `icd10_primary`   | string        | Yes      | No       | Primary ICD-10 diagnosis                               |
| `icd10_secondary` | array[string] | Yes      | No       | May be an empty array                                  |
| `units`           | int           | Yes      | No       | `>= 1`                                                  |
| `charge_amount`   | decimal(12,2) | Yes      | No       |                                                        |
| `allowed_amount`  | decimal(12,2) | Yes      | Yes      | Populated on `paid`/`denied`                           |
| `paid_amount`     | decimal(12,2) | Yes      | Yes      | Populated on `paid`/`denied`                           |
| `service_date`    | date          | Yes      | No       | Within parent's `service_date_from`..`service_date_to` |

## Reference Value Pools

### Payers
| payer_id         | payer_name                |
|------------------|---------------------------|
| `PAYER-UHC-001`  | UnitedHealthcare          |
| `PAYER-AET-002`  | Aetna                     |
| `PAYER-CIG-003`  | Cigna                     |
| `PAYER-BCB-004`  | Blue Cross Blue Shield    |
| `PAYER-HUM-005`  | Humana                    |
| `PAYER-MED-006`  | Medicare                  |
| `PAYER-MCD-007`  | Medicaid                  |

### Plan types
`HMO`, `PPO`, `EPO`, `POS`, `HDHP`

### Place of Service (CMS codes)
| Code | Meaning                |
|------|------------------------|
| `11` | Office                 |
| `21` | Inpatient Hospital     |
| `22` | Outpatient Hospital    |
| `23` | Emergency Room         |
| `81` | Independent Laboratory |

### CPT codes (with descriptions & charge ranges)
| Code    | Description                                              | Charge range ($) |
|---------|----------------------------------------------------------|------------------|
| `99213` | Office visit, established patient, 20-29 min             | 100 – 250        |
| `99214` | Office visit, established patient, 30-39 min             | 150 – 350        |
| `99203` | Office visit, new patient, 30-44 min                     | 175 – 400        |
| `85025` | Complete blood count with differential                   | 25 – 60          |
| `80053` | Comprehensive metabolic panel                            | 40 – 230         |
| `80061` | Lipid panel                                              | 35 – 120         |
| `93000` | Electrocardiogram, complete                              | 50 – 175         |
| `71046` | Chest X-ray, 2 views                                     | 100 – 350        |
| `73721` | MRI lower extremity joint without contrast               | 900 – 2500       |
| `45378` | Colonoscopy, diagnostic                                  | 1200 – 2500      |
| `36415` | Routine venipuncture                                     | 15 – 40          |
| `90471` | Immunization administration                              | 25 – 90          |

### ICD-10 codes
| Code       | Description                                                          |
|------------|----------------------------------------------------------------------|
| `E11.9`    | Type 2 diabetes mellitus without complications                       |
| `I10`      | Essential (primary) hypertension                                     |
| `E78.5`    | Hyperlipidemia, unspecified                                          |
| `J06.9`    | Acute upper respiratory infection, unspecified                       |
| `M25.561`  | Pain in right knee                                                   |
| `M54.50`   | Low back pain, unspecified                                           |
| `Z12.11`   | Encounter for screening for malignant neoplasm of colon              |
| `Z00.00`   | Encounter for general adult medical exam without abnormal findings   |
| `F41.9`    | Anxiety disorder, unspecified                                        |
| `K21.9`    | Gastro-esophageal reflux disease without esophagitis                 |

### CPT modifiers (sparse — most lines have none)
| Modifier | Meaning                                                  |
|----------|----------------------------------------------------------|
| `25`     | Significant, separately identifiable E/M service         |
| `59`     | Distinct procedural service                              |
| `33`     | Preventive service                                       |
| `LT`     | Left side                                                |
| `RT`     | Right side                                               |

Recommended modifier frequency: `modifier_1` populated on ~15% of lines, `modifier_2` on ~3%.

### CARC denial reason codes
| Code     | Meaning                                   |
|----------|-------------------------------------------|
| `CO-197` | Precertification/authorization absent     |
| `CO-16`  | Claim lacks information                   |
| `CO-45`  | Charge exceeds fee schedule               |
| `CO-29`  | Time limit for filing expired             |
| `PR-1`   | Deductible amount                         |
| `PR-204` | Service not covered                       |

## ID Generation

| ID              | Format                                     | Pool / uniqueness                |
|-----------------|--------------------------------------------|----------------------------------|
| `claim_id`      | `CLM-<YYYY>-<8-digit sequence>`            | Globally unique                  |
| `patient_id`    | `PAT-<7-digit>`                            | Pool of ~500 recurring patients  |
| `member_id`     | `<3-letter payer prefix><9 digits>`        | Pool of ~500 recurring           |
| `group_number`  | `GRP-<5 digits>`                           | Pool of ~30                      |
| `billing_provider_npi` / `rendering_provider_npi` | 10 random digits | Pool of ~50 recurring providers  |
| `line_id`       | `<claim_id>-L<line_number>`                | Unique within claim              |

The recurring pools give the data realistic repetition so downstream analytics can practice joins and dimension modeling.

## Generation Heuristics

- Each claim has 1–5 lines, weighted toward 1–2 (e.g., 40% / 30% / 15% / 10% / 5%).
- `claim_type`: 90% `professional`, 10% `institutional`.
- `service_date_from` = `service_date_to` on 95% of claims; multi-day spans are rare.
- `submitted_date` = `service_date_to` + 1 to 7 days.
- Each line's `icd10_primary` is random; `icd10_secondary` has 0–3 entries (weighted toward 0–1).

## Payload Envelope

```json
{
  "generated_at": "<iso8601 UTC>",
  "record_count": <int>,
  "claims": [ <Claim>, ... ]
}
```

`record_count` is computed **after** data-quality injection — so if `duplicates=true` added a row, it counts in `record_count`.

## Example Paid Claim (denial_reason_code omitted)

```json
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
    }
  ],
  "created_at": "2026-04-10T09:14:22Z",
  "last_updated_at": "2026-04-18T16:03:47Z"
}
```

Note `denial_reason_code` is absent because this claim was paid (null).

## Example Denied Claim (denial_reason_code present)

```json
{
  "claim_id": "CLM-2026-00017993",
  "...": "...",
  "status": "denied",
  "total_billed_amount": 356.00,
  "total_allowed_amount": 0.00,
  "total_paid_amount": 0.00,
  "patient_responsibility": 356.00,
  "denial_reason_code": "CO-197",
  "...": "..."
}
```

## README Content Guidance

When drafting the user-facing `README.md` for the API, include:

1. **Healthcare context** — what a claim is, what adjudication means, brief intro to CPT / ICD-10 / NPI / CARC codes.
2. **Schema** — the tables above (parent + child) with types, required, nullable, description.
3. **Example payload** — one paid claim (demonstrating `denial_reason_code` omission) and one denied claim (showing it present).
4. **API usage** — all four query parameters with examples, e.g. `GET /claims?new=5&updates=3&duplicates=true&null_patient_id=true`.
5. **Data quality** — explain what `duplicates` and `null_patient_id` do and why they self-heal (response-only mutation, never persisted).
