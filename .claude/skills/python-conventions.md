---
name: python-conventions
description: Python project conventions for this repository — UV package manager, Python 3.14, UV packaged-application layout, uv_build backend, ruff default rules, Google-style docstrings, and the Pydantic vs dataclasses split. Use whenever writing, reviewing, formatting, or restructuring any Python file in this project, initializing new subpackages, or configuring pyproject.toml.
---

# Python Conventions

These conventions apply to **all** Python code in this repository.

## Tooling

- **Package manager**: [UV](https://docs.astral.sh/uv/). All commands run via `uv` — never `pip`, never a bare `python` invocation.
  - Install/sync deps: `uv sync`
  - Add a runtime dep: `uv add <pkg>`
  - Add a dev-only dep: `uv add --dev <pkg>`
  - Run any command: `uv run <command>` (e.g., `uv run uvicorn ...`, `uv run pytest`, `uv run ruff check .`)
- **Python version**: 3.14. Pin in `pyproject.toml`:
  ```toml
  [project]
  requires-python = ">=3.14,<3.15"
  ```
- **Build backend**: `uv_build`. In `pyproject.toml`:
  ```toml
  [build-system]
  requires = ["uv_build>=0.5,<1"]
  build-backend = "uv_build"
  ```

## Project Layout — UV "Packaged Application"

Follow the UV packaged-application pattern documented at
<https://docs.astral.sh/uv/concepts/projects/init/#applications>.

Initialize with:
```bash
uv init --package --app source
```

Resulting layout (the API lives under `source/`):

```
source/
├── pyproject.toml
├── README.md
├── uv.lock
└── src/
    └── claims_simulator/
        ├── __init__.py
        └── main.py
```

- All application code lives under `src/<package_name>/`.
- Tests live in `source/tests/` (sibling of `src/`), **not** inside the package.
- Define a console-script entry point in `pyproject.toml`:
  ```toml
  [project.scripts]
  claims-simulator = "claims_simulator.main:run"
  ```
  where `run()` is a small function in `main.py` that launches uvicorn programmatically (useful for container CMDs and for `uv run claims-simulator`).

## Linting & Formatting — Ruff

Ruff with **default rules only**. Do not add custom selections or ignores.

Config in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py314"
```

Commands:
- Lint check: `uv run ruff check .`
- Format check: `uv run ruff format --check .`
- Auto-fix: `uv run ruff check --fix .`
- Auto-format: `uv run ruff format .`

All code must pass `uv run ruff check .` and `uv run ruff format --check .` cleanly before the task is considered done.

## Docstrings — Google Style

Every **module**, **class**, and **function** (including methods, including private helpers) must have a Google-style docstring. Examples:

**Module docstring** (top of file, before imports):
```python
"""Short one-line summary of the module.

Longer description explaining what this module is responsible for and
how it fits into the broader application.
"""
```

**Function docstring**:
```python
def adjudicate_claim(claim: Claim, outcome: str) -> Claim:
    """Advance a claim to a terminal adjudication state.

    Args:
        claim: The claim to adjudicate. Must currently be in ``submitted``
            or ``in_review`` state.
        outcome: One of ``"paid"`` or ``"denied"``.

    Returns:
        The same claim object with ``status``, ``adjudicated_date``, and
        monetary fields populated.

    Raises:
        ValueError: If ``claim.status`` is already terminal or if
            ``outcome`` is not one of the allowed values.
    """
```

**Class docstring**:
```python
class ClaimGenerator:
    """Generates simulated claims with realistic code and amount distributions.

    Attributes:
        payer_pool: Candidate payers to draw from.
        cpt_pool: Candidate CPT codes with weighted selection.
    """
```

Private helpers (leading underscore) may have a single-line docstring, but must have one.

## Validation Split — Pydantic vs dataclasses

Strict separation between external I/O validation and internal data shape.

Use **Pydantic** for anything that crosses a trust boundary:
- FastAPI request models (query, path, body)
- FastAPI response models
- Environment/config loading (`pydantic-settings`)
- Parsing any untrusted JSON

Use **dataclasses** for internal, in-process data structures that never directly cross a boundary:
- Generator intermediate types (e.g., `GeneratedClaim`, `LifecycleTransition`)
- Value objects flowing between internal functions
- Per-module helper structures

Rule of thumb: if a dict is about to be serialized to JSON or was just deserialized from one, it belongs in a Pydantic model. If it only ever flows between internal Python functions, it belongs in a `@dataclass`.

**SQLModel** is the one exception — it doubles as both ORM model and Pydantic model for DB-layer purposes. Treat SQLModel classes as DB models only. Do **not** return them directly from a FastAPI endpoint; translate them into dedicated Pydantic response models at the API boundary.

## Imports

- Absolute imports only from within the package (e.g., `from claims_simulator.generator import new_claim`).
- No relative imports (`from .foo import bar`) — ruff default rules allow them, but absolute is the house style.
- Standard library, third-party, and first-party imports are grouped and separated by blank lines; `ruff format` handles this automatically.

## Type Hints

- All function signatures (parameters and return types) must be fully type-hinted.
- Prefer `X | None` over `Optional[X]` (Python 3.14 native).
- Prefer built-in generics (`list[int]`, `dict[str, Any]`) over `typing.List`/`typing.Dict`.

## Running & Testing

From within a package directory (e.g., `source/`):

```bash
uv sync                                # install/refresh deps
uv run ruff check .                    # lint
uv run ruff format --check .           # format check
uv run pytest                          # tests
uv run uvicorn claims_simulator.main:app --reload  # dev server
```

`pytest` is added as a dev dependency:
```bash
uv add --dev pytest pytest-asyncio httpx
```

## Definition of Done (per Python task)

1. Code passes `uv run ruff check .` with no errors.
2. Code passes `uv run ruff format --check .` with no changes needed.
3. Every module, class, and function has a Google-style docstring.
4. All function signatures are fully type-hinted.
5. External I/O uses Pydantic; internal data uses dataclasses (or SQLModel for DB rows).
6. Tests, if applicable to the task, pass via `uv run pytest`.
