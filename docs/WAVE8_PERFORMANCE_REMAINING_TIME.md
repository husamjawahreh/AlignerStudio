# Wave 8 — Performance and remaining time

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**Live ToothInstanceNet inference:** no. This host remains **BLOCKED_BY_ENVIRONMENT**.

Waiting stays honest. A long job shows its phase and elapsed time. A remaining time appears only when this computer has already finished the same kind of job for the same input class. Progress stays the percent the server sent. Elapsed time is not turned into a percent or a countdown.

## Workflow state during long work

The Wave 7 resolver is unchanged. Opening a step is still navigation. Creating a plan, regenerating staging, and refreshing validation stay explicit.

| Class | Duration | Examples |
| --- | --- | --- |
| Fast | under 2 seconds | Step change, next-action resolution, selection |
| Medium | under 30 seconds | Treatment setup and staging on the cited upper real case |
| Long | under 3 minutes | Upper real geometric validation in the WP-12 benchmark |
| Very long | 3 minutes or more | First dual-arch validation inside plan creation, previously about 18 minutes |

Each processing job already has a job id, phase, start time, elapsed time, server progress when one exists, and cancel. Wave 8 adds `remaining_time` on the live status read. It is not stored as a clinical result.

## Remaining-time method

Samples are completed `case-processing` durations on this computer: operation, environment fingerprint (system, machine, CPU count), and input class (`both-arches`, `upper-only`, `lower-only`, or `unknown`). Meshes, scans, and patient references are not stored.

| Evidence | What the doctor sees |
| --- | --- |
| No matching samples | Elapsed time, current phase, and “No reliable remaining-time estimate” |
| 1–2 samples, or a wide spread | “estimated” with “Uncertainty is high” |
| 3 or more samples and a tight spread | “estimated” and “Not a guarantee” |
| Elapsed time already outside the observed range | No estimate. Not “0 seconds remaining” |

A percent is shown only when `overall_progress` is a number from the job. A benchmark from another run is a labeled historical sample and is not copied into the estimate. One status surface shows the sentence. While the processing overlay is open, the header does not repeat it.

## Polling and cancellation

Status is polled about once a second only while the job is `PROCESSING`. Completion, failure, cancellation, stale, and interrupted states stop the poll. The treatment load after completion runs once per job id, including when the poll effect cleans up. Cancellation writes `CANCELLED`, does not record a duration, and does not present a partial result as completed. A retry is a new job. Native validation work is cancelled on a best-effort basis, the same as WP-13. Instant cancellation of an in-flight native call is not promised.

## Caching

| Cache | Key | Invalidation | Risk |
| --- | --- | --- | --- |
| Validation report | plan id, staging id, engine version, thresholds | New staging, plan, or threshold | Misses rather than serving another case |
| Fixture reconstruction | artifact, arch, checksum | Explicit clear, upload hash | Test-only geometry |
| Operation durations | operation, this computer, input class | Bounded to 48 samples | Not clinical state. Ignored when the computer fingerprint differs |

Mutable treatment state is not cached under a key that omits plan, staging, or thresholds.

## What was measured

New measurements are in `.research/tmp/wave8_performance/`. The two-tooth validation timing is fixture/test-only. Real-case setup, staging, validation, compose, review-bundle size, and reopen memory are the WP-12 benchmark, cited and not re-run:

| Work | Cited median | Provenance |
| --- | --- | --- |
| Treatment setup | 1.389 s | WP-12 upper real |
| Staging | 1.533 s | WP-12 upper real |
| Validation in-process | 214.5 s | WP-12 upper real, 3 stages |
| Validation isolated | 105.7 s | WP-12, not a claim that dual-arch is fast |
| Compose, cache hit | 5.33 s | WP-12 |
| Review bundle serialize | 6.60 s, about 16.6 MB | WP-12. Provenance fields were not removed |

Opening Treatment Setup, switching stage, and changing a view do not regenerate staging or start validation. Stage regeneration is the explicit control.

## What was not sped up

GeometricValidationEngine was not changed. Process isolation from WP-12 still keeps status polling off the validation worker. There was no safe change that shortened narrow-phase time without skipping checks. Review-bundle bytes were not stripped. Manufacturing readiness was not claimed.

The one behavioral fix is that a repeated completion poll cannot start a second treatment load.

## Browser QA

Headless Chromium passed the navigation and processing matrix at 1366×768, 1600×1000, and 1280×800 (48 screenshots, about 2.6 minutes). Evidence is `.research/tmp/wave8_browser_qa/`. Fixture crowns in those shots are generated test meshes, not patient inference. Opening Analysis did not start segmentation. Opening Staging did not regenerate stages. With no history the overlay says “No reliable remaining-time estimate.” A measured payload is shown once, with “Not a guarantee.” Cancel leaves a cancelled job.

## This host, this session

| Measurement | Result | Provenance |
| --- | --- | --- |
| Remaining-time estimator, 2000 calls | median 0.114 ms per call | synthetic durations, no geometry |
| Two-tooth validation, cache miss | 14.3 ms | fixture tetrahedra, not a patient case |
| Two-tooth validation, cache hit | median 0.013 ms | same fixture, report id unchanged |
| Threshold change | cache miss | same fixture |
| Frontend Vitest | 198 passed | includes the Wave 8 estimator tests |
| WP-12 and WP-13 | 15 passed | |
| WP-10 | 20 passed, then the process was stopped on the real-case evidence test | the last three tests were not confirmed here |

## Known limitations

- Live ToothInstanceNet inference did not run.
- First-time and dual-arch validation can still take many minutes. The UI says so instead of inventing a finish time.
- Remaining time is for the whole case-processing job, not a promise about a single phase.
- WP-14 and WP-15 were not started. Wave 9 and later were not started.
