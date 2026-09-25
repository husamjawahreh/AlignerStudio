# WP-13 — Reliability, Recovery & Data Integrity

**Work package:** FIRST VERSION WP-13  
**Date:** 2026-09-25  
**Authoritative roadmap:** `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md` §11, `Aligner_Studio_First_Version_World_Class_Plan.md` WP-13  
**Baselines:** WP-01…WP-12 docs (WP-12 performance blockers accepted, not reworked)  
**Scope:** Reliability, recovery, and data integrity only.  
**Explicit stop:** **WP-14 and WP-15 were NOT started.**

---

## 1. Verdict

**PASS WITH BLOCKER** (same GPU/runtime blocker as prior WPs for live ToothInstanceNet inference; multi-process API deploy still needs an external lock for duplicate jobs — in-process only).

WP-13 proved:

- Honest durable job states including **INTERRUPTED** (restart) distinct from FAILED / CANCELLED / STALE / COMPLETED
- Atomic case-store persistence (tmp + replace)
- Cancel demotes in-flight segmentation; never reports COMPLETED
- Failure-injection hooks (test-only) for persistence integrity proofs
- Case isolation for validation report cache keys (`plan_id` embeds case)
- Browser refresh restores case + workflow step from durable backend + sessionStorage hints
- Real-case interruption matrix **11/11 PASS** (`.research/tmp/wp13_reliability/interruption_matrix.json`)
- Export verify/reopen integrity preserved
- Doctor edit history remains in durable treatment sessions; undo stack is non-authoritative (documented)

---

## 2. Reliability audit

| Failure point | Finding | Mitigation |
|---|---|---|
| Case store mid-write | Non-atomic `write_text` could corrupt JSON | **Atomic tmp+replace** |
| API restart mid-PROCESSING | Previously FAILED+PROCESS_RESTARTED | **INTERRUPTED** + demote seg `processing`→`interrupted` |
| Cancel mid-segmentation | Seg record could stay `processing` | **cancelled** status on cancel |
| Validation ProcessPool after cancel | Orphan workers possible | **cancel_validation_work** recreates pool |
| Browser refresh | Only case id; always treatment-setup | **workspace step hint** + resolve from durable treatment |
| WP-12 report cache | Keyed by staging_id only | **plan_id\|staging_id\|…** (case-bound) |
| Partial compose | Session only saved after full compose | Unchanged — correct (no mid-validate “complete”) |
| Multi-process duplicate jobs | In-process lock only | Documented limitation |

---

## 3. Job lifecycle

Durable `stage_status` values:

| State | Meaning |
|---|---|
| `PROCESSING` | Live job with heartbeat / active future |
| `COMPLETED` | Durable success (`result=ok`) |
| `FAILED` | Terminal error (non-restart) |
| `CANCELLED` | User cancel — not completion |
| `STALE` | Heartbeat lost, no live future (`JOB_STALE`) |
| `INTERRUPTED` | Process restart while PROCESSING (`PROCESS_RESTARTED`) |

Identity fields preserved: `job_id`, `case_id`, `input_hash`, stages, progress, heartbeat, error codes, provenance via case/session records.

---

## 4. Crash recovery

| Scenario | Behavior |
|---|---|
| Backend kill during PROCESSING | On store reload → `INTERRUPTED` / `PROCESS_RESTARTED`; never COMPLETED |
| Mid-segmentation | Seg `status=interrupted` |
| Mid-validation (inject) | No treatment session checkpoint written |
| Mid-export (inject) | Exception before package success claim |
| Browser refresh during PROCESSING | Polls durable status; UI does not invent COMPLETED |
| Retry after INTERRUPTED | New `job_id`, progress resets to 0 |

Resume-from-mid-stage is **not** claimed — fail closed and restart.

---

## 5. Idempotency

| Operation | Behavior |
|---|---|
| Start processing while PROCESSING | Returns same `job_id` |
| Start after INTERRUPTED/FAILED/CANCELLED/STALE | New job identity |
| Session save | Atomic replace per `case_id` |
| Export verify | Re-openable; hash mismatches empty when intact |

---

## 6. Persistence integrity

1. **Case store:** write tmp → `replace` (atomic on POSIX).
2. **Treatment sessions:** existing gzip+pickle tmp+replace (unchanged).
3. **Completion rule:** `_remember` / COMPLETED only after durable writes succeed.
4. **Failure injection** (`ALIGNERSTUDIO_FAILURE_INJECTION=1` + `ALIGNERSTUDIO_FAIL_AT`):
   - `after_upload_persist`
   - `after_segmentation_output`
   - `before_validation_complete`
   - `after_validation_persist`
   - `before_production_complete`
   - `during_export`
   - `before_case_store_persist`  
   Default **off**.

---

## 7. Version consistency

Existing WP-06/09/10 freshness evaluators unchanged. Session round-trip tests assert `plan_id`, `staging_id`, `report_id`, `version_id` survive reload. Stale validation/production bindings still mark dependent artifacts stale — not silently reused.

---

## 8. Case isolation

| Resource | Isolation |
|---|---|
| Case store records | Keyed by `case.id` |
| Session files | `{case_id}.session.gz` + embedded `case_id` check |
| Validation report cache | `plan_id|staging_id|thresholds` (`plan_id` case-bound) |
| Fixture reconstruct cache | Content-addressed artifact hashes (same STL bytes → same reconstruct; not treatment plans) |
| Jobs | Per-case processing status |

Cross-case tests in `tests/python/test_wp13_reliability.py`.

---

## 9. Cancellation

`cancel_processing`:

- Terminal `CANCELLED` / `error_code=CANCELLED`
- `result` is not `ok`
- In-flight segmentation → `cancelled`
- Best-effort `cancel_validation_work()` for WP-12 process pool

---

## 10. Export / reopen

Export → verify (`verified: true`, empty `hash_mismatches`) → new `TreatmentSessionStore` load → re-verify. Session checkpoint required for editable reopen; export ZIP alone is audit-only (honest `session_reimport_available: false`).

---

## 11. Browser refresh

`sessionStorage`:

- `alignerstudio.activeCaseId`
- `alignerstudio.activeWorkspace` (hint only)

Authoritative clinical state: API case + treatment session.  
`resolveRestoredWorkspace` restores production/staging/etc. only when treatment exists; otherwise analysis/intake.

**Undo/redo stacks** remain React-local; durable truth is `editHistory` / session — not silently reverted on refresh, but undo stack itself is not recovered (documented limitation).

---

## 12. Undo / redo / doctor edits

- Edits persist via `_remember` → session.gz
- Refresh reloads treatment bundle including edit history
- Undo stack not durable — doctor must re-navigate; accepted edits are not discarded

---

## 13. Failure injection

Module: `services/api/app/failure_injection.py`  
Tests prove inject-on persist and default-off safety.

---

## 14. Real-case interruption matrix

Script: `scripts/wp13_interruption_matrix.py`  
Evidence: `.research/tmp/wp13_reliability/interruption_matrix.json`

| ID | Scenario | Result |
|---|---|---|
| A | Refresh during processing | PASS |
| B | Backend restart during processing | PASS (`INTERRUPTED`) |
| C | Segmentation interruption | PASS |
| D | Validation interruption (inject) | PASS |
| E | Export interruption (inject) | PASS |
| F | Cancellation | PASS |
| G | Reopen after interruption | PASS |
| H | Stale detection | PASS (FV-01/P7) |
| I | Duplicate request | PASS |
| J | Export verify/reopen | PASS |
| K | Real-case determinism (14 tooth_ref) | PASS |

---

## 15. Determinism

Official upper arch reload: identical 14 `tooth_ref` values; ZIP SHA preserved; no FDI fabrication.

---

## 16. Test results

| Suite | Result |
|---|---|
| `tests/python/test_wp13_reliability.py` | passed (with P7) |
| `tests/python/test_p7_performance_reliability.py` | passed (INTERRUPTED assert) |
| `tests/python/test_wp12_performance.py` | regression |
| `tests/python/test_fv01_processing_lifecycle.py` | regression |
| `tests/python/test_wp01_real_clinical_pipeline.py` | regression |
| Frontend vitest / typecheck / lint / build | run in WP-13 gate |
| Interruption matrix | **11/11 PASS** |

---

## 17. Known limitations

1. No mid-stage resume — restart requires new job.
2. Multi-process API: duplicate-job protection is in-process only.
3. Undo/redo UI stack not durable across refresh.
4. Cooperative cancel cannot forcibly kill native C extensions mid-call; validation pool is best-effort recreated.
5. Fixture cache shares reconstruct for identical artifact bytes (intentional content addressing).

---

## 18. Environment blockers

- Live ToothInstanceNet GPU inference unavailable (same as WP-01…WP-12).
- Dual-arch geometric validation still multi-minute CPU (WP-12 blocker); reliability ensures honesty, not speed.

---

## 19. Files changed

- `services/api/app/store.py` — atomic persist; INTERRUPTED recovery
- `services/api/app/processing.py` — INTERRUPTED status; cancel integrity; inject points
- `services/api/app/failure_injection.py` — new
- `services/api/app/routers/cases.py` — upload inject point
- `services/api/app/treatment_sessions.py` — export/production inject
- `engines/validation/isolated_execution.py` — cancel_validation_work
- `engines/validation/report_cache.py` — plan_id in key
- `apps/web/src/caseWorkspacePersistence.ts` — workspace hint + resolve
- `apps/web/src/app/App.tsx` — refresh restore
- `apps/web/src/caseWorkspacePersistence.test.ts`
- `tests/python/test_wp13_reliability.py`
- `tests/python/test_p7_performance_reliability.py` — INTERRUPTED expect
- `scripts/wp13_interruption_matrix.py`
- `docs/WP13_RELIABILITY.md` (this file)

---

## 20. Explicit confirmation

**WP-14 (Desktop packaging) and WP-15 (Final Real-Case Gate) were NOT started.**  
WP-12 performance work was not redone.
