# Healthcare Iceberg Learning Project

## Purpose

This project exists to learn Apache Iceberg table concepts through hands-on practice with realistic healthcare data. A FastAPI application generates simulated medical claims data that is ingested into Iceberg tables stored in AWS S3. PySpark handles the ingestion and transformation layers, exercising patterns such as incremental loads, Slowly Changing Dimension (SCD) Type II, and data-quality handling.

## Architecture

1. **Data source** (`source/`) — FastAPI application that generates simulated claims data with a realistic lifecycle (`submitted` → `in_review` → `paid`/`denied`). Exposes a single endpoint that returns all historical + new + updated records per call.
2. **Transformation layer** (`transformation/`) — PySpark jobs that consume the API output, ingest into Iceberg bronze tables, then apply SCD Type II and data-quality transformations into silver/gold layers.
3. **Infrastructure** (`infrastructure/`) — Terraform-managed AWS resources (S3 buckets for Iceberg storage, Glue catalog, IAM).

## Orchestration

A `docker-compose.yaml` at the project root orchestrates all runtime services as containers:

- `api` — the FastAPI claims simulator (`source/`)
- `spark` — the PySpark ingestion/transformation jobs (`transformation/`)
- `postgres` — backing store for the API simulator

## Directory Structure

```
.
├── source/              # Healthcare claims data simulator (FastAPI)
├── transformation/      # PySpark ingestion and transformation jobs
├── infrastructure/      # Terraform AWS infrastructure
├── docker-compose.yml   # Orchestrates all services
├── .claude/
│   └── skills/          # Project-scoped Claude Code skills
└── CLAUDE.md            # This file
```

## Sub-project Guidance

Each subdirectory has (or will have) its own `CLAUDE.md` with project-specific instructions. When working inside a subdirectory, read that directory's `CLAUDE.md` first.

## Skills

Project-scoped skills live under `.claude/skills/`:

- **`healthcare-domain-knowledge`** — Claims data domain: CPT, ICD-10, NPI, claim lifecycle rules, realistic value pools, payload schema.
- **`api-implementation`** — FastAPI endpoint, data-generation flow, SCD II update semantics, data-quality injection, module layout.
- **`python-conventions`** — UV, Python 3.14, packaged-application layout, `uv_build`, ruff, Google-style docstrings, Pydantic vs dataclasses conventions.

Invoke the relevant skill(s) whenever working on matching tasks.
