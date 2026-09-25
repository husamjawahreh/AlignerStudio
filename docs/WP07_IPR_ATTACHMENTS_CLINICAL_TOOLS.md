# WP-07 — IPR + Attachments + Clinical Tools

**Work package:** FIRST VERSION WP-07  
**Verdict:** **PASS WITH BLOCKER** — clinical-tool contract, honesty UX, version binding, and doctor review are implemented over Phase-10 / WP-05 / WP-06 foundations; reliable contact-based clinical IPR and attachment prescriptions remain unavailable from crown-only geometry (honest `requires_review` / `not_available`).

**WP-08 and all later work packages were NOT started.**

---

## 1. Verdict

PASS WITH BLOCKER.

Delivered:

- Stable clinical-tools contract (`clinical_tools_1.0`) with truth states, readiness gates, provenance/limitations, and setup/staging freshness.
- Measured / computed-proposal / doctor-entered IPR distinction.
- Attachment candidates remain review-only with undetermined dimensions (no fabricated prescriptions).
- Refinement / Production nav no longer present empty capability as clinical “0”.
- Setup and staging version binding with stale detection and explicit regenerate.
- GeometricValidationEngine remains authoritative; clinical tools never claim clinical approval from geometric pass.

Blocker (environmental / evidence, not a process failure):

- Crown-only centroid-distance “IPR” is geometric COMPUTED / REQUIRES_REVIEW — not clinical enamel reduction.
- Attachment geometry (dimensions / manufacturing boolean) is NOT_AVAILABLE (WP-10).
- No enamel safety thresholds exist in project evidence; none were invented.

---

## 2. Existing clinical-tool audit

| Area | Pre-WP-07 state | Reuse |
|---|---|---|
| Phase-10 `TreatmentProposalEngine` / `IPRSite` / `AttachmentSite` | Centroid-distance space deltas; undetermined attachments | **Reused** — no second proposal system |
| P5 manufacturing boundary | Separate export/manufacturing gates | **Unchanged** |
| RefinementPanel / ProposalPanels | Showed site counts as `"0"` when empty | **Fixed** honesty labels |
| Review DTOs | Flat proposedAmount / attachment list | **Enriched** with truth/valueSource |
| WP-05 Treatment Setup versions | `version_id` lineage | **Bound** clinical tools |
| WP-06 Smart Staging | Freshness / regenerate | **Bound**; staging regen marks tools stale |
| GeometricValidationEngine | Collision/proximity authority | **Preserved** |
| Overlay layers (3D IPR/attachments) | Unavailable | Still unavailable (planning-review only) |

---

## 3. Clinical tool contract

`domain/treatment_plan/clinical_tools.py` + `engines/planning/clinical_tools_engine.py`

Every review payload includes `clinicalTools` with:

- `case` binding via adjuncts `proposal_id` / setup / staging version ids
- readiness gates (not a single score)
- `clinically_approved: false` always
- limitations / notes

IPR/attachment site DTOs carry tooth refs, units, truth state, value source, limitations.

---

## 4. Truth states

| State | Usage |
|---|---|
| VERIFIED | Never assigned from generation alone |
| COMPUTED | Available for geometric measurements conceptually; IPR proposals that need doctor review use REQUIRES_REVIEW |
| REQUIRES_REVIEW | Generated IPR proposals and all attachment candidates |
| NOT_AVAILABLE | Missing geometry / empty capability / undetermined methods |

---

## 5. IPR architecture

Pairs identified by `tooth_a` / `tooth_b` (FDI number or semantic `tooth_ref`), hashed `site_id`, arch consistency via planning mode filters. Not list position.

Value layers:

1. **Measured** — `current_measurement` (centroid distance)
2. **Computed proposal** — `required_space` / generated `proposed_amount`
3. **Doctor-entered** — `doctor_entered_amount` (distinct field)
4. **Active** — doctor-entered wins when present
5. **Review status** — ProposalStatus (needs_review / doctor_modified / accepted / rejected)

---

## 6. IPR measurement

Method: Phase-10 centroid distance between source/target tooth meshes.  
Unit: **`model units`** (explicit — not claimed as mm).  
Does **not** convert proximity into clinical IPR recommendations.  
Does **not** invent enamel limits.

---

## 7. IPR editing / review

- Numeric edit via existing API → sets `doctor_entered_amount` + status `doctor_modified`
- Accept / reject via existing status API
- Regeneration preserves doctor-entered amounts (`preserve_doctor_ipr_amounts`)
- Reset / regenerate clinical tools: `POST .../treatment/proposals/reset` → `regenerate_clinical_tools`

---

## 8. Attachment architecture

Controlled taxonomy reused: `rectangular | elliptical | beveled | undetermined`.  
Candidates created only when angular DOF present (existing Phase-10 heuristic) — marked as review candidates, not prescriptions.  
`dimensions=None`, `generated=False`.

---

## 9. Attachment placement

Reference point = target mesh centroid; orientation uses existing engineering coordinate frame when present.  
No invented clinical axes. Geometry manufacturing boolean deferred to WP-10.

---

## 10. Attachment review

ProposalStatus: generated / needs_review → accepted / rejected / doctor_modified.  
Acceptance ≠ clinical approval (`clinicallyApproved: false`).

---

## 11. Setup / staging binding

Session fields:

- `clinical_tools_setup_version_id`
- `clinical_tools_staging_version_id`

Set on compose, coupled restage (`_session_from_result`), restore setup version, and explicit `regenerate_clinical_tools`.

---

## 12. Validation integration

`readiness.validation = available` when a GeometricValidationEngine report exists.  
Findings remain on `validationSummary`. Clinical tools do not reinterpret collisions as IPR prescriptions.

---

## 13. Stale-state handling

| Event | Clinical tools |
|---|---|
| `apply_edit(..., restage=False)` | Adjuncts preserved → **stale** vs new setup |
| `regenerate_staging` | Adjuncts preserved → **stale** vs new staging |
| Coupled edit / recalculate | Adjuncts regenerated + binding updated → **current** |
| `regenerate_clinical_tools` / proposals reset | Explicit refresh → **current** |

No silent rebase of doctor decisions.

---

## 14. Refinement UX behavior

- Empty IPR/Attachments → **“Not available”** / **“Requires review”**, never clinical **“0”**
- With sites → `N · requires review`
- Stale → `Stale — regenerate` + banner
- ProposalPanels show measured / computed proposal / doctor-entered / truth / unit
- Count badge shows `n/a` when empty

---

## 15. Real-case evidence

Case: `official_real_case_stage2_verified_v1`

| Evidence | Result |
|---|---|
| Tooth instances | **28** (14+14), semantic refs, **no fabricated FDI** |
| IPR sites (adjacent same-arch pairs) | **26** |
| Measurable IPR pairs (centroid distance) | **26** (truth: `requires_review`, unit: `model units`) |
| Unavailable IPR pairs | **0** (geometry present; clinical prescription still unavailable) |
| Attachment candidates (with angular demo movement) | **1** (`undetermined` dims, `requires_review`) |
| Doctor-entered IPR | Persisted + reopen verified in tests |
| Setup/staging binding | Stale after setup-only edit; current after regenerate |
| Source integrity | Source vertices unchanged through regenerate |
| Identity integrity | `tooth_ref` strings preserved; `tooth_number is None` |
| Validation | Report remains present; `clinically_approved: false` |
| IPR generate time | **~361 ms** (Phase-10 proposal engine on real geometry) |
| Compose time (staging; validation stubbed for timing probe) | **~3.6 s** |

Centroid measurements are geometric COMPUTED inputs to review — **not** clinically verified IPR millimetres.

---

## 16. Performance

Measured wall-clock (non-invented):

| Operation | Time |
|---|---|
| Real-case IPR/adjuncts generate | ~361 ms |
| Real-case compose (staging; validation stubbed for probe) | ~3.6 s |
| Full GeometricValidationEngine on real case | dominates end-to-end treatment compose (order of minutes in CI/tests) |
| Clinical-tools regenerate (synthetic) | sub-second |

No fabricated benchmarks.

---

## 17. Tests

- `tests/python/test_wp07_clinical_tools.py` — contract, identity, measured/doctor, persistence, stale, attachments, validation, real-case, API
- Frontend: `workflowNavigationPresentation.test.ts` — no fake zeros
- Fixture / ProposalPanels updated for honesty fields
- Prior WP regression suites remain applicable (WP-01…06, P0–P8)

---

## 18. Limitations

- Centroid distance ≠ clinical IPR amount
- No enamel / biological movement thresholds
- No occlusion (WP-08)
- No attachment manufacturing geometry (WP-10)
- No 3D IPR/attachment overlays
- Attachment taxonomy is software domain representation only
- Fake confidence values from Phase-10 (`confidence` floats) were not newly invented and are not surfaced as clinical certainty in WP-07 UI

---

## 19. Environment blockers

- Official artifact must be present (`official_real_case_stage2_verified_v1.zip` or `.research/tmp/...`) for real-case tests
- Semantic-only planning mode: FDI absent by design

---

## 20. Explicit confirmation

**WP-08 (Occlusion), Advanced Anatomy, Production CAD (WP-10), WP-11 UX redesign, and new research-model integration were NOT started.**
