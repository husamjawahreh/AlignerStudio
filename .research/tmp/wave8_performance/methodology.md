# Wave 8 measurement methodology

Measured on this host at 2026-09-26T03:15:01.800248+00:00.
Platform: Linux-7.0.0-34-generic-x86_64-with-glibc2.39. CPUs: 12.

## What was run now

- Remaining-time estimator, 2000 calls, synthetic durations, no geometry.
- Geometric validation cache miss and hit on two fixture tetrahedra. This is not a patient case and not the multi-minute dual-arch cost.
- Cache key still misses when the proximity threshold changes. Report id on a hit matches the stored report.

## What was cited, not re-run

WP-12 `.research/tmp/wp12_performance/benchmark.json` remains the real-case timing source for treatment setup, staging, upper validation, session compose, review-bundle serialization, and reopen RSS. Those rows are copied into `measurements.json` with provenance `cited_wp12_not_rerun`. They are not a new clinical run and they are not this user's remaining-time estimate.

Live ToothInstanceNet inference was not run. This host stays BLOCKED_BY_ENVIRONMENT.

## What was not treated as an ETA

Cited medians are evidence about this repository's earlier benchmark. The product shows a remaining time only from completed jobs recorded on the current computer for the same operation and input class.
