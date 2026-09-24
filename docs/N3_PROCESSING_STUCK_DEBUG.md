# N3 Processing Stuck Debug

## Root cause

The visible 0% jobs were queued behind two older jobs that had reached 70%
(`BUILDING_PLAN`) and never completed. The processing executor has two workers,
so those stale jobs occupied both workers; newer jobs remained at `PREPARING`
with 0% and never reached scan validation.

The API itself was healthy and the frontend status endpoint returned the persisted
state correctly. This was a backend worker lifecycle issue, not a frontend
polling issue and not a model-progress issue.

## Correction

- Added structured `PROCESSING_TRANSITION` logging at every status transition.
- Added `PROCESSING_CREATED` logging.
- On API startup, persisted `PROCESSING` jobs are recovered as explicit
  `FAILED` jobs with `error_code=PROCESS_RESTARTED`.
- Duplicate processing requests for the same active case return the existing
  job instead of starting another job.
- The authoritative persisted job/case status remains unchanged in shape.

The real model is still intentionally unchanged. It does not expose meaningful
fine-grained progress; milestone percentages plus elapsed/activity text remain
the truthful semantics.

## Observed recovery

After clean API restart, stale jobs transitioned to:

```text
stage_status: FAILED
error_code: PROCESS_RESTARTED
user_message: Case analysis was interrupted. Start analysis again.
```

The next processing request can now start without being masked by an old job.
