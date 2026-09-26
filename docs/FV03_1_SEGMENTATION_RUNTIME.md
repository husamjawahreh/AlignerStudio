# FV-03.1 — Reproducible segmentation runtime and review evidence

| | |
|---|---|
| Phase | FV-03.1 only |
| Date | 2026-09-26 |
| Runtime reproducibility | Implemented |
| Review contract | Partial |
| Real segmentation | Unverified |
| Clinical accuracy | Not established |

FV-03 remains **PASS WITH BLOCKER / ENVIRONMENT-BLOCKED**. This phase makes the ToothInstanceNet runtime reproducible and the review record evidence-ready. It does not verify segmentation. No instances, confidence, FDI, or clinical score were fabricated. FV-04 was not started.

## Runtime requirements

The application process does not import PyTorch, CUDA, or `pointops`. A case can still be opened, prepared, and gated when those packages are absent.

The separate TIN runtime, recorded in `environment_specification()` and `engines/segmentation/runtime_readiness.py`, is:

| Pin | Value |
|---|---|
| Python | 3.12 |
| Validated PyTorch | `2.10.0+cu128` |
| Validated CUDA image | `12.8.1` |
| Upstream PyTorch / CUDA | `2.3.0` / `12.1` |
| pointops | `CUDAExtension` only. No `CppExtension`. CPU forward is ruled out. |
| Checkpoint | `instseg_full.ckpt` |
| Checkpoint SHA-256 | `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803` |
| Contract version | `3dteethland-424252e3d94a1565c8c2090eb5bb456b76386b93` |
| Source revision | `424252e3d94a1565c8c2090eb5bb456b76386b93` |
| Required input channels | 6 |
| Required outputs | offsets and sigmas, one seed logit, seven identify logits, instance ids from learned region clustering. FDI, arch, and left/right are not encoded. |

Build steps for that separate environment: install Python 3.12, install a CUDA PyTorch build matching one of the pins above, install a matching CUDA toolkit, build `pointops` from the pinned source, and place the checkpoint where the runtime can hash it. A compatible machine is expected to report self-test `READY_FOR_INFERENCE`. That result has not been observed here.

## Checkpoint contract

The self-test may read the checkpoint state dict without a patient case and without a forward pass. On this host the file is present, the SHA-256 matches the pin, and the tensor contract state is `TENSOR_CONTRACT_ESTABLISHED`. Observed input channels are 6. That metadata inspection does not make the runtime ready.

## Capability states

The self-test returns one of:

| State | When |
|---|---|
| `ENVIRONMENT_UNAVAILABLE` | Driver, PyTorch, or the CUDA extension is missing. |
| `MODEL_UNAVAILABLE` | The checkpoint file is missing or the SHA-256 does not match. |
| `MODEL_CONTRACT_INVALID` | The state dict does not re-derive the known tensor contract. |
| `RUNTIME_INITIALIZATION_FAILED` | The runtime imports but model initialization fails. |
| `INPUT_CONTRACT_INVALID` | A supplied prepared input fails the gate. The case-free self-test does not require a mesh. |
| `READY_FOR_INFERENCE` | Environment, checkpoint, contract, and initialization all pass. |

Unavailable values in the runtime manifest stay null. This host's manifest, measured 2026-09-26:

| Field | Value |
|---|---|
| Python | 3.12.3 |
| OS | Linux-7.0.0-34-generic-x86_64-with-glibc2.39 |
| CPU | Intel Core i5-10500H |
| RAM | 16,571,219,968 bytes |
| GPU vendor / model | null |
| Driver version | null |
| CUDA version | null |
| PyTorch | null |
| pointops / CUDA extension | unavailable |
| trimesh / numpy | 5.1.0 / 2.5.3 |
| torch / pointops packages | null |
| Checkpoint file | `instseg_full.ckpt` |
| Checkpoint SHA-256 | matches the pin above |
| Runtime capability | `DRIVER_UNAVAILABLE` |
| Self-test | `ENVIRONMENT_UNAVAILABLE` |

Also applicable: `PYTORCH_UNAVAILABLE`, `CUDA_EXTENSION_UNAVAILABLE`. Availability stays `ENVIRONMENT_BLOCKED`.

## Evidence bundle

Every committed segmentation run seals an evidence bundle. The seal is the SHA-256 of the canonical bundle. A later edit fails that seal. Review edits do not rewrite it. A stale job does not replace the sealed run.

A blocked bundle stores the blocker and leaves inference duration, device, peak memory, raw model output, and instance generation null. `real_inference` is false. `clinically_verified` is false. `QUALITY_EVALUATION` is `NOT_AVAILABLE` unless a separate reference segmentation is supplied. The model is not used as its own ground truth. A supplied reference can record Dice, IoU, surface distance, Hausdorff distance, instance count, connected-component statistics, boundary statistics, and invalid or self-intersecting counts. No such reference exists for this scan, so no score is reported.

## Blocked-run semantics and the real inference gate

The command is:

```bash
.venv/bin/python scripts/fv03_1_segmentation_runtime.py
```

It runs the case-free self-test, then the prepared-input probe when `data/benchmark/real-case/upper.stl` is present. Inference is entered only when the self-test is `READY_FOR_INFERENCE` and the prepared-input gate, model SHA, input SHA, model contract, and runtime capability all pass. Any failed gate stores the blocker and sets `real_inference` false. A passing gate would execute ToothInstanceNet and still would not mark the result clinically verified.

The FV-03 blocked-run record is unchanged:

| Step | FV-03 record |
|---|---|
| Prepared mesh load | 145.5 ms |
| Input gate | 326.3 ms, accepted |
| Capability detection | 1511.3 ms |
| Inference | not run |
| Peak RSS | 529.3 MB |

The FV-03.1 command appended a new measurement in `.research/tmp/fv03_1_report.json`. It does not replace that record.

| Step | FV-03.1 appended probe |
|---|---|
| Prepared mesh load | 34.1 ms |
| Input gate | 80.2 ms, accepted, readiness `READY_WITH_WARNINGS` |
| Capability detection | 340.6 ms |
| Inference | not entered |
| Self-test | `ENVIRONMENT_UNAVAILABLE` |
| RSS before / after | 399.9 MB / 331.6 MB |
| Peak RSS | 421.0 MB |

The appended probe ran in the same process as the self-test, after trimesh was already imported. Its peak is not a replacement for the FV-03 529.3 MB figure. `real_inference` is false. Primary blocker: `DRIVER_UNAVAILABLE`. Message: ToothInstanceNet cannot execute. No segmentation was fabricated.

Input facts for the same scan remain 8,557,034 bytes, 513,417 vertices, 171,139 faces, SHA-256 `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48`.

## Review provenance

Authorship stays `MODEL_PREDICTION`, `DOCTOR_MODIFIED`, `DOCTOR_ACCEPTED`, `DOCTOR_REJECTED`, and `REQUIRES_REVIEW`. Accept does not set `VERIFIED`.

Each doctor modification records the previous segmentation-state hash, affected instance ids, operation, parameters, timestamp, and a resulting geometry hash when face indices change. Undo, redo, and reset restore those recorded operations. The model snapshot is not rewritten. Merge checks that both instances exist, the face references are valid, and the prepared SHA matches, then writes a new derived review result.

Split is `SPLIT_UNAVAILABLE`. The intake form has no face-picking control that can represent a safe split, so the action changes no geometry.

Manual segmentation correction is a separate capability, status `NOT_IMPLEMENTED`. It does not substitute automatic model segmentation, a model prediction, or clinical verification. No manual editor was added.

Semantic identity stays `NOT_ESTABLISHED`. Model class labels, when a real run eventually emits them, stay model labels. FDI, tooth number, arch, left/right, and missing teeth are not inferred.

The review form shows `ENVIRONMENT_BLOCKED` or `SEGMENTATION_COMPLETED` as mutually exclusive outcomes. Review controls appear only when a completed result has `real_inference` true. A blocked run has no accept, merge, or undo controls. `QUALITY_EVALUATION NOT_AVAILABLE` is shown in either case.

FV-03.2 extends sealed runs with a provenance run contract, GeometricValidationEngine topology checks, preprocessing metadata (including optional RNG seed), and an immutable reference to `fv032_exact_repository_preprocessing_reproducibility.json`. See `docs/FV03_2_SEGMENTATION_EVIDENCE_GATE.md`. Historical blocked-run measurements in this document stay unchanged.

Playwright `tests/e2e/fv03_segmentation.spec.ts` passed in 45.9 s against `http://127.0.0.1:5177` and `http://127.0.0.1:8000`. The stored case `b491cd67-60c9-4a0e-a663-65181e607812` is `blocked`, self-test `ENVIRONMENT_UNAVAILABLE`, capability `DRIVER_UNAVAILABLE`, availability `ENVIRONMENT_BLOCKED`, semantic identity `NOT_ESTABLISHED`, zero instances, `real_inference` false, and quality `NOT_AVAILABLE`. The sealed bundle kind is `blocked_run` and its inference duration is null. The form showed `ENVIRONMENT_BLOCKED` and did not show `SEGMENTATION_COMPLETED` or review controls.

## Current host limitation

Real ToothInstanceNet inference did not execute. Segmentation is unverified. Clinical accuracy is not established. The next inference attempt belongs on a machine that reaches `READY_FOR_INFERENCE`, using the same accepted prepared artifact and the same evidence seal.
