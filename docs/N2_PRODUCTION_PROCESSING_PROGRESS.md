# N2 Production Processing Progress

## State model

Processing status is persisted as part of the existing case repository. The
contract contains:

- `job_id`, `case_id`;
- `overall_progress` from 0 to 100;
- current stage and stage status;
- measurable stage progress when available;
- completed and pending stages;
- error state/code, user-safe message, and internal diagnostic;
- start/update/completion timestamps.

Stages are centralized in `app.processing.STAGES`:

`PREPARING -> VALIDATING_SCANS -> SEGMENTING_UPPER/SEGMENTING_LOWER -> BUILDING_PLAN -> VALIDATING_PLAN -> FINALIZING`

The upper/lower branches run concurrently. Progress advances only when the
backend verifies a stage transition. Model internals do not fabricate a fine-
grained percentage; segmentation is represented as processing until its branch
completes.

## API

- `POST /cases/{case_id}/processing` starts or reconnects to the existing job.
- `GET /cases/{case_id}/processing-status` retrieves the persisted status.

Both endpoints use the existing case repository and authoritative case UUID.
A reload can retrieve the last persisted state. A future database migration can
replace the repository implementation without changing the frontend contract.

## Frontend

The production planning action starts the job and polls once per second. Polling
cleans up on component lifecycle and stops on completed, failed, or cancelled
states. The loading panel displays backend `user_message` and actual
`overall_progress`; it does not animate completion independently.

## Failure semantics

- `PROCESSING`: active backend work.
- `COMPLETED`: backend completed finalization and treatment data can be loaded.
- `FAILED`: the UI displays the backend user-safe reason; technical detail stays
  in diagnostics.
- `CANCELLED`: terminal non-success state.

No fixture, synthetic geometry, or clinical fallback is introduced.

## Performance measurements

The validated local artifact measured approximately 100.8 seconds for upper
segmentation and 427.4 seconds for lower segmentation in the observed direct
run. These are baseline measurements, not targets. N2 preserves the concurrent
branch architecture to reduce wall-clock time and does not replace
ToothInstanceNet or add an unverified fallback.

## Future migration

The status payload is deliberately transport-neutral. A production database or
SSE/WebSocket event layer can publish the same job/status contract later without
creating a second case identity or UI state store.
