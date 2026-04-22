# Healthcare Claims Iceberg Lab

A hands-on learning project for **Apache Iceberg** table concepts, using simulated healthcare claims data as the source feed. The focus is the data platform, not the data itself — claims just happen to be a rich, realistic domain for practicing the kinds of patterns Iceberg is good at: incremental loads, Slowly Changing Dimension (SCD) Type II, schema evolution, and data-quality handling.

## Purpose

- Learn how Iceberg manages table state, snapshots, and metadata.
- Practice SCD Type II transformations on a source that genuinely mutates over time.
- Work with incremental loads driven by `created_at` / `last_updated_at` watermarks.
- Handle realistic data-quality issues (duplicates, missing identifiers).

## Data Flow

```
┌─────────────┐      ┌────────────────────┐      ┌─────────────────────────┐
│  FastAPI    │      │  PySpark Ingest    │      │  PySpark Transform      │
│  simulator  │ ───► │       (raw)        │ ───► │       (bronze)          │
│  (source/)  │      │ (transformation/)  │      │    (transformation/)    │
└─────────────┘      └────────────────────┘      └─────────────────────────┘
      │                      │                            │
      ▼                      ▼                            ▼
   Postgres              S3 Iceberg                    S3 Iceberg
  (live state)           (raw claims)             (flat, analytics-ready)
```

1. **API** (`source/`) — a FastAPI service backed by Postgres generates simulated claims on demand. Every call returns all historical + new + updated records, with realistic adjudication lifecycle mutations. See [`source/README.md`](./source/README.md) for full details.
2. **Ingest job** (`transformation/`) — a PySpark job pulls the API response and lands the raw nested claims payload into Iceberg bronze tables in S3. Incremental behavior is driven by `last_updated_at`.
3. **Transform job** (`transformation/`) — a PySpark job reads bronze, applies SCD Type II merges, flattens the nested `claim_lines` into its own normalized table (with a foreign key back to the parent claim), and writes analytics-ready silver/gold Iceberg tables.

## Infrastructure

- **Docker Compose** orchestrates the local runtime. All services are containers:
  - `api` — the FastAPI claims simulator
  - `postgres` — backing store for the API
  - `spark` — PySpark runner for the ingest and transform jobs
- **AWS S3** — storage layer for all Iceberg tables (bronze, silver, gold).
- **AWS Glue Data Catalog** — the Iceberg catalog; tracks table metadata and makes tables queryable by other AWS services (Athena, EMR, etc.).
- **Terraform** (`infrastructure/`) — provisions and manages the S3 buckets, Glue catalog databases, IAM roles, and any supporting AWS resources. All AWS state is code-managed.

## Repository Structure

```
.
├── source/              # FastAPI claims data simulator
├── transformation/      # PySpark ingest + transform jobs
├── infrastructure/      # Terraform AWS resources
├── docker-compose.yml   # Local orchestration
├── .claude/skills/      # Claude Code skills (domain, implementation, conventions)
└── CLAUDE.md            # Project-wide agent instructions
```

Each subdirectory has its own `README.md` and, where applicable, `CLAUDE.md` with project-specific detail.

## Getting Started

```bash
# spin up the simulator + postgres locally
docker compose up api postgres

# generate some claims
curl "http://localhost:8000/claims?new=10"

# run the ingest job
docker compose run spark ingest

# run the transform job
docker compose run spark transform
```

See the subdirectory READMEs for deeper walkthroughs.
