# FV-03.2 — Real segmentation evidence gate and provenance foundation

| | |
|---|---|
| Phase | FV-03.2 |
| Date | 2026-09-26 |
| Implementation | Evidence gate, run contract, sealed provenance |
| Status | PARTIAL / EVIDENCE-PROVEN (contracts and reproducibility) |
| Real live inference on this host | Still environment-blocked unless `READY_FOR_INFERENCE` |
| Clinical accuracy | NOT ESTABLISHED |
| FDI mapping | NOT ESTABLISHED |
| Doctor clinical approval | NOT ESTABLISHED |

FV-03 and FV-03.1 historical blocked-run records remain authoritative for this host's local environment. This phase does not overwrite them.

## Verified external runtime qualification (immutable evidence)

A genuine external GPU qualification was completed on Google Colab:

| Item | Value |
|---|---|
| GPU | NVIDIA A100-SXM4-80GB |
| PyTorch | 2.11.0+cu128 |
| CUDA | 12.8 |
| pointops | Successfully built and imported |
| Checkpoint | `instseg_full.ckpt` |
| Checkpoint SHA-256 | `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803` |

## Repository preprocessing reproducibility evidence

Immutable file (do not rewrite or substitute):

`fv032_exact_repository_preprocessing_reproducibility.json`

| Field | Value |
|---|---|
| status | `REPOSITORY_PREPROCESSING_FIXED_SEED_REPRODUCIBLE` |
| seed | `123456` (metadata / configuration example; not the only allowed production seed) |
| upper.exact_reproducible | true |
| lower.exact_reproducible | true |
| model_changed | false |
| checkpoint_changed | false |
| thresholds_changed | false |
| kernel_changed | false |
| fixed_seed_only | true |

Exact repository prediction preprocessing recorded by that evidence:

1. `ZScoreNormalize(norm=True)`
2. `PoseNormalize(clean=True)`
3. `InstanceCentroids`
4. `UniformDensityDownsample(0.025)`
5. `XYZAsFeatures`
6. `NormalAsFeatures`
7. `ToTensor`

That evidence proves fixed-seed preprocessing reproducibility. It does **not** prove clinical accuracy, FDI correctness, clinical confidence, ground-truth segmentation quality, doctor acceptance, or clinical approval.

## What this phase implements

Reuses FV-03 jobs, FV-03.1 seals, review authorship, and GeometricValidationEngine topology checks.

| Area | Behavior |
|---|---|
| Run contract | `fv03.2-run-1` records provenance fields; unavailable values stay null / `NOT_AVAILABLE` / `INVALID` |
| Semantic identity | Model class is not FDI; mapping stays `NOT_ESTABLISHED` |
| Geometric validation | `validate_mesh_geometry` (GeometricValidationEngine) plus existing run checks; no silent repair |
| Evidence bundle | Deterministically hashable; original model output remains immutable |
| Preprocessing metadata | Pipeline + optional RNG seed as run configuration; Colab JSON referenced immutably |
| Review | `MODEL_PREDICTION` / `DOCTOR_MODIFIED` / `DOCTOR_ACCEPTED` / `DOCTOR_REJECTED` / `REQUIRES_REVIEW`; accept is not clinical verification |
| Quality evaluation | `QUALITY_EVALUATION = NOT_AVAILABLE` without genuine reference segmentation |
| Split | Remains `SPLIT_UNAVAILABLE` |
| External import | `POST /cases/{id}/uploads/{arch}/segmentation/external-evidence` seals only after server-side hash and geometry checks |

## External CUDA import / seal

The repository can import a transferred inference evidence bundle and seal it as `EXTERNAL_CUDA`.

| Rule | Behavior |
|---|---|
| Execution origin | Stays `EXTERNAL_CUDA`. It is not rewritten to `LOCAL_NATIVE`. |
| Local runtime | This host is not described as the A100 runtime. |
| `SIMULATED` | Cannot be sealed as real inference. |
| `UNKNOWN` | Cannot be presented as genuine inference. |
| Client `verified: true` | Ignored. The server computes the seal. |
| Checkpoint | Reference checkpoint SHA must match when the run claims that checkpoint. |
| Raw output | Must be present, hash-matched, and left immutable. |
| Validation | `GeometricValidationEngine` is authoritative. Invalid geometry is not sealed and is not repaired. |
| Review | A sealed run enters review as `MODEL_PREDICTION`. Doctor acceptance is not clinical verification. |
| Reproducibility | `REPRODUCIBLE` only when preprocessing and an explicit seed are recorded. Seed `123456` is metadata, not a production default. |
| Clinical claims | Clinical accuracy stays `NOT_ESTABLISHED`. FDI stays `NOT_ESTABLISHED`. Quality stays `NOT_AVAILABLE` without a genuine reference. |

Repository-side status for this path: **READY_FOR_EXTERNAL_INFERENCE_SEALING**.

That status means the importer can validate and seal a genuine external bundle. It does not mean an A100 forward pass has been sealed in this repository.

## External inference run protocol

`READY_FOR_EXTERNAL_INFERENCE_RUN` is true. `GENUINE_EXTERNAL_INFERENCE_COMPLETED` is false. The runner is `scripts/fv03_2_external_inference_run.py`. It calls `teethland.data.datasets.TeethSegDataset` with `norm=True` and `clean=True`, then `UniformDensityDownsample(0.025)`, `XYZAsFeatures`, `NormalAsFeatures`, and `ToTensor`. It does not call `adapters.toothinstancenet.preprocessing.prepare_mesh`.

The explicit reproducibility seed for this qualified configuration is `123456`. It is a run argument, not an application default. CUDA determinism is `NOT_CLAIMED`.

Procedure, bundle layout, and the import endpoint are in `docs/FV03_2_EXTERNAL_INFERENCE_RUN.md`.

FV-04 was not started.

## NOT ESTABLISHED

- Clinical accuracy
- FDI correctness / arch / left-right inference from model classes
- Ground-truth segmentation quality when no genuine reference exists
- Doctor clinical approval
- Live ToothInstanceNet inference on the local host when self-test is not `READY_FOR_INFERENCE`

## Tests

`tests/python/test_fv03_2_evidence.py` covers provenance, checkpoint SHA refusal, model-class/FDI separation, prepared SHA mismatch, invalid geometry, immutable model output under doctor edit, acceptance without clinical verification, quality `NOT_AVAILABLE`, deterministic evidence hashing, seed metadata, and immutable reference of the Colab JSON.
