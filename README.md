# AlignerStudio

Orthodontic treatment-planning application. Clean-room rebuild — no code is
reused from any prior AlignerStudio project.

## What This Is (Phase 13)

A vertical slice proving the shape of the pipeline:

```
Upload Case → Analyze Case → Generate Treatment Plan → Review Stages
  → Modify → Recalculate → Export
```

The implemented foundation now covers **Upload Case → mesh validation →
external-model segmentation architecture → geometric tooth identification →
stable coordinate frames → descriptive arch analysis → deterministic setup →
staging → geometric validation → review → explicit editing/restaging →
review-only adjunct proposals → deterministic engineering export**. See
[TREATMENT_PLAN.md](TREATMENT_PLAN.md) for exact phase status and
[ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture.

## Repository Layout

See [ARCHITECTURE.md](ARCHITECTURE.md#4-directory-map-phase-8) for the full
directory map and layer rules.

## Getting Started

### Backend (Python / FastAPI)

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
PYTHONPATH=../.. uvicorn app.main:app --reload
```

Run tests / lint / format (from repo root, with the `services/api` venv active):

```bash
pytest -q
ruff check .
ruff format --check .
```

### Frontend (React / TypeScript / Vite)

```bash
cd apps/web
npm install
npm run dev
```

Run tests / lint / format:

```bash
cd apps/web
npm run test
npm run lint
npm run typecheck
npm run format:check
```

### API-Backed Engineering Demo

Start the backend from the repository root:

```bash
source services/api/.venv/bin/activate
PYTHONPATH=.:services/api uvicorn app.main:app --app-dir services/api --reload
```

Then start the frontend with `pnpm --filter @alignerstudio/web dev` and choose
**Load engineering demo**. This runs the existing treatment engines behind the
API, exposes review/edit/recalculate/proposal data, and downloads an auditable
ZIP export. It is explicitly fixture-labeled and is never clinical output.

Uploaded cases require separate **Upper arch STL** and **Lower arch STL** files.
Each file is uploaded and validated through the real API; the case panel shows
its filename, size, validation state, and a remove action. Generate Plan remains
disabled until both arch files validate. Uploaded data never enters fixture mode.
Treatment generation remains unavailable until a real segmentation model and
identification inputs are configured; the application does not substitute a
fixture for uploaded data. See [docs/API_INTEGRATION.md](docs/API_INTEGRATION.md).

### Real Segmentation Requirements

No model weights are included. Before processing an uploaded case beyond mesh
validation, provide a legally cleared ONNX artifact and a separately verified
contract sidecar through `ALIGNERSTUDIO_SEGMENTATION_MODEL` and
`ALIGNERSTUDIO_SEGMENTATION_CONTRACT`. The sidecar records the supported
tensor/feature/output contract, confidence semantics, license verification,
and SHA-256 artifact hash. Without both, the API reports `model_unavailable`;
it never runs fixture segmentation for an uploaded STL.

## Branding

Official assets live in [assets/](assets/): `AS-logo.png`, `AS-favicon.png`,
`loader.gif`. UI uses a dark navy/charcoal theme with restrained gold and
cyan accents matching the logo — see `apps/web/src/styles`.

## Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — layering, principles, directory map.
- [TREATMENT_PLAN.md](TREATMENT_PLAN.md) — pipeline phase-by-phase status.
- [CLINICAL_BOUNDARIES.md](CLINICAL_BOUNDARIES.md) — every clinical
  threshold and its source.
- [REUSE_MATRIX.md](REUSE_MATRIX.md) — external algorithm/model tracking.
- [docs/TOOTH_IDENTIFICATION.md](docs/TOOTH_IDENTIFICATION.md) — geometric FDI identification and coordinate frames.
- [docs/ARCH_ANALYSIS.md](docs/ARCH_ANALYSIS.md) — descriptive arch measurements and ordering.
- [docs/GEOMETRIC_VALIDATION.md](docs/GEOMETRIC_VALIDATION.md) — mesh validation, contacts, proximity, and collisions.
- [docs/STAGING_ENGINE.md](docs/STAGING_ENGINE.md) — deterministic stage generation.
- [docs/EXPORT.md](docs/EXPORT.md) — deterministic engineering export package.
- [docs/API_INTEGRATION.md](docs/API_INTEGRATION.md) — API-backed review and demo workflow.
- [.github/copilot-instructions.md](.github/copilot-instructions.md) —
  AI agent working rules for this repo.

## Status

Phase 13 only. Do not treat any generated plan/segmentation/identification/
staging/validation/proposal/export output as
clinically valid — see `DataProvenance` and fixture labeling described in
[TREATMENT_PLAN.md](TREATMENT_PLAN.md).

The API-backed engineering demo works through review, explicit edit,
recalculation, adjunct review, and ZIP export. Fixture mode is engineering-only
and visibly labeled. No real segmentation model is bundled; real model
integration remains blocked pending a legally cleared artifact and verified
technical contract.
