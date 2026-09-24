# Production N1 Correction Pass

## Root cause of the 404

The API case repository was process-local only. The browser retained the UUID
returned by `POST /cases`, but a reload/reloader or separate API worker started
with an empty `case_store`. Upload and validation could succeed in one process,
then `/cases/{id}/plan` or another downstream endpoint could receive the same
UUID in a process that no longer contained it and return `404 Case not found`.

## Correction

- Added a JSON-backed local case repository at the configured case-store path.
- Default path: alongside the API upload directory as `cases.json`.
- `create`, upload, remove, and validation mutations persist through the same
  repository.
- The existing UUID remains the sole authoritative case identity.
- Added `api.getCase` for explicit future retrieval, without adding a second
  frontend store.
- Added a regression test covering create, retrieval, segmentation-state
  request, and planning request with the same UUID. Missing mesh/model errors
  remain distinct from case-not-found errors.

## Doctor-facing cleanup

Visible fixture/engineering terms were removed from the production shell and
replaced with `Requires review`, `Analysis source under review`, actionable
case-preparation language, and technical-detail separation. Internal
provenance and test diagnostics remain available without being the normal
clinical workflow vocabulary.

## Validation language

Geometric findings are described as computed geometric review. Unsupported
movement constraints remain unavailable. Clinical approval is never inferred.

## Results

- Backend tests: 120 passed.
- Frontend tests: 19 passed.
- Typecheck: passed.
- Build: passed.
- Patch hygiene: passed.
- Lint: passed with the existing TransformControls hook dependency warning.

## Remaining limitations

- The local case store is JSON-backed rather than a production database.
- The validated ToothInstanceNet artifact remains experimental and requires
  explicit configuration.
- A clean dense real-case browser run remains the final workstation check;
  earlier shared-browser runs were limited by large segmentation responses and
  stale Vite sessions.
