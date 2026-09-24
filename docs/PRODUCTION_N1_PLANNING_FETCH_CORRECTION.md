# Production N1 Planning Fetch Correction

## Exact root cause

The browser error occurred before the planning request. `handleGeneratePlan`
called:

1. `POST /cases/{case_id}/pipeline/upper`
2. `POST /cases/{case_id}/pipeline/lower`
3. `POST /cases/{case_id}/plan`

The first two requests were awaited sequentially. On the validated real-case
artifact, each segmentation request took approximately 100 seconds. The
browser/runtime connection expired while the second long request was pending,
which surfaced as the generic `TypeError: Failed to fetch`. The `/plan`
endpoint was not reached in the failing browser flow.

## Direct endpoint results

Using the existing Production Test UUID
`5db0afea-c2e8-49c9-8aba-c1f83d3324fd`:

- `GET /cases/{id}`: `200`, persisted case with both mesh paths.
- `POST /cases/{id}/pipeline/upper`: `200`, 14 instances,
  `identification_incomplete`, experimental validated artifact.
- `POST /cases/{id}/pipeline/lower`: same endpoint and artifact contract;
  long-running computation, not a case identity failure.
- `POST /cases/{id}/plan`: valid only after both pipeline requests complete;
  the endpoint returns a structured HTTP error when required inputs are not
  available and never fabricates a plan.

## Fix

Upper and lower pipeline requests now run concurrently with `Promise.all`.
They still use the same active case UUID and the same API endpoints. The
planning request remains fail-closed and structured.

The API client now classifies request timeouts and connection failures with
actionable messages instead of exposing only `Failed to fetch`.

## Regression coverage

- Persisted case reload preserves the same UUID.
- Case retrieval and downstream requests use the same identity.
- Planning failure returns structured API detail rather than a transport-level
  error.
- Existing frontend planning success/failure tests remain green.

## Remaining limitations

- The validated artifact remains experimental and requires explicit backend
  configuration.
- Segmentation remains computationally heavy; concurrent arch processing
  reduces wall-clock latency but does not change model runtime.
- Clinical identity/planning remains unavailable when the segmentation artifact
  cannot provide confirmed identity.