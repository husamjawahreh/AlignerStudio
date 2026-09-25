# P8 — World-Class QA & Release Candidate

Evidence against `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md` §12.

**No clinical, regulatory, manufacturing, human, or Production Candidate acceptance is claimed.**

## Implementation status

| Area | Status |
|---|---|
| Real-case QA matrix automation | **Covered + honest PENDING rows** (`tests/python/test_p8_qa_matrix.py`) |
| Engineering gate script | **PASS** — `docs/p8_gate_reports/gate_20260925T001942Z.txt` |
| Export reopen-for-audit | **Implemented** (integrity reopen; session re-import remains unavailable) |
| Browser component E2E (vitest) | **PASS** (refresh rehydrate + undo/redo) |
| Playwright clean-browser E2E | **PENDING / opt-in** (`tests/e2e/p8.smoke.spec.ts`) |
| Clean-machine acceptance | **PENDING** (human + clean OS environment required) |
| Production Candidate | **NOT CLAIMED** |

## Latest engineering gate run (`20260925T001942Z`)

| Gate | Result |
|---|---|
| backend pytest | **PASS** — 201 passed, 2 skipped, 144.60s |
| frontend typecheck | **PASS** |
| frontend lint | **PASS** — 0 errors, 1 warning (`StageViewer` gizmoMode deps) |
| frontend vitest | **PASS** — 25 files, 74 tests |
| frontend build | **PASS** |
| ruff | **PENDING/SKIP** — 53 pre-existing style findings (not a product correctness gate) |
| P8 matrix | **PASS** — 12 passed, 2 skipped |
| performance benches | **PENDING/SKIP** — set `P8_RUN_PERFORMANCE=1` |
| Playwright E2E | **PENDING/SKIP** — set `P8_RUN_PLAYWRIGHT=1` after install |
| clean-machine | **PENDING/SKIP** |
| **ENGINEERING_GATE** | **PASS** (with recorded PENDING items) |
| **PRODUCTION_CANDIDATE** | **NOT_CLAIMED** |

## Real-case matrix coverage

| Cell | Evidence | Status |
|---|---|---|
| multiple real cases | Only `official_real_case_stage2_verified_v1` in-repo | **PENDING** (explicit skip) |
| upper + lower | Combined fixture identification + P0.1 | **PASS** |
| upper only / lower only | API rejects single-arch plan (policy) | **PASS (unsupported-by-design)** |
| different orientations | No rotated verified real STLs | **PENDING** |
| different mesh densities | Real dense ZIP + synthetic denser oracle | **PARTIAL** |
| missing data | Fail-closed incomplete arch identity | **PASS** |
| ambiguous identity | Uncertain without FDI invention | **PASS** |
| processing interruption | P7 `PROCESS_RESTARTED` | **PASS** |
| browser refresh | sessionStorage + App rehydrate (bugfix: no longer clears id on mount) | **PASS** |
| backend restart | P7 session checkpoint restore | **PASS** |
| doctor editing | Demo edit + phase9/P4 | **PASS** |
| undo/redo | `p8Workflow.test.tsx` | **PASS** |
| validation | Phase7 + P0.2/P0.4 + matrix | **PASS** |
| export | Existing integrity suites | **PASS** |
| re-import | `export/reopen` audit verify; editable session re-import unavailable | **PARTIAL** (audit PASS / session PENDING) |
| manufacturing handoff | Shells/QC remain `unavailable` | **PASS (honest unavailable)** |

## Engineering gate checklist

Run:

```bash
chmod +x scripts/p8_engineering_gate.sh
./scripts/p8_engineering_gate.sh
# optional:
# P8_RUN_PERFORMANCE=1 ./scripts/p8_engineering_gate.sh
# P8_RUN_PLAYWRIGHT=1 ./scripts/p8_engineering_gate.sh   # after playwright install + live servers
```

| Gate | How evidenced |
|---|---|
| backend tests | `pytest tests/python` |
| frontend tests | `pnpm test` in `apps/web` |
| typecheck | `pnpm run typecheck` |
| lint | eslint (+ ruff recorded as style debt) |
| build | `pnpm run build` |
| browser/E2E | vitest App/workflow; Playwright optional/PENDING |
| real artifact tests | P0/P8 matrix when artifact present |
| performance benchmarks | opt-in `tests/performance` + P7 docs |
| geometry correctness | phase7 + denser oracle |
| export integrity | P0.3 / phase11 / reopen-for-audit |
| provenance integrity | fixture/export clinical_approval=false |
| model adapter regression | research adapters unavailable |
| memory/lifecycle | tracemalloc fixture peak guard + session clear |

## Clean-machine acceptance path

```text
CLEAN MACHINE → CLEAN BROWSER → REAL CASE → … → EXPORT → REOPEN + VERIFY
```

**Status: PENDING** in this environment. Automated gates cannot substitute a clean OS image,
clean browser profile, and operator-driven dual-arch real-case run.

Interim automated analogue (not clean-machine acceptance):

1. Engineering demo or fixture plan  
2. Doctor edit + undo/redo  
3. Validation review  
4. Export  
5. `POST /export/reopen` audit verify  

Session restore after API restart uses durable treatment-session checkpoints, **not** the export ZIP.

## Files changed (P8)

- `engines/export/treatment_export.py` — `reopen_for_audit`
- `services/api/app/treatment_sessions.py` — `reopen_export_for_audit`
- `services/api/app/routers/cases.py` — `POST .../export/reopen`
- `apps/web/src/app/App.tsx` — refresh remember/rehydrate race fix
- `apps/web/src/viewer/syntheticGingiva.ts` — unused param cleanup for lint
- `apps/web/vite.config.ts` — exclude `tests/e2e` from vitest
- `apps/web/src/app/p8Workflow.test.tsx`
- `tests/python/test_p8_qa_matrix.py`
- `scripts/p8_engineering_gate.sh`
- `tests/e2e/p8.smoke.spec.ts`, `tests/e2e/playwright.config.ts` (opt-in Playwright)
- `docs/P8_QA_RELEASE_CANDIDATE.md`
- `docs/p8_gate_reports/gate_20260925T001942Z.txt`
- `AlignerStudio_PRODUCTION_MASTER_PLAN_v2.1.md` §12 status

## Known limitations / blockers

1. Second verified real case absent → multi-case matrix PENDING  
2. No rotated real STLs → orientation matrix PENDING  
3. Editable session re-import from export ZIP unavailable by design  
4. Manufacturing shells/QC unavailable  
5. Playwright clean-browser E2E not default-installed  
6. Clean-machine human acceptance PENDING  
7. Heavy real validate benches remain opt-in (cost)  
8. Ruff style debt (53 findings) recorded, not blocking product gates  

## Production Candidate

**Not claimed.** Claim only after P8 engineering gate PASS **and** clean-machine + human acceptance evidence exist outside this automated report.
