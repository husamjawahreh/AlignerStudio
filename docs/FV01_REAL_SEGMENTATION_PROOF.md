# FV-01 — Real segmentation proof

| | |
|---|---|
| Phase | FV-01 only |
| Date | 2026-09-26 |
| Verdict | **PASS WITH BLOCKER** |
| Host | Linux 7.0.0-34-generic, Python 3.12.3, Intel Core i5-10500H, 16,571,219,968 bytes RAM |
| Clinical accuracy | Not claimed. `clinical_accuracy_claim=false`. Output class `ENGINEERING_OUTPUT`. |

Live ToothInstanceNet inference did not run. The blocker is measured and reproducible. This document does not mark First Version readiness.

## FV-01.1 update (2026-09-26)

The tensor contract is no longer unknown. `scripts/fv01_execution_runner.py` loaded `instseg_full.ckpt` state-dict shapes without PyTorch and without a forward pass. Primary state on this host is now `DRIVER_UNAVAILABLE`, with `PYTORCH_UNAVAILABLE`, `POINTOPS_UNAVAILABLE`, `ONNX_UNAVAILABLE`, and `ONNX_BACKEND_NOT_READY` kept as separate applicable states. Inference still did not run. Detail and the architecture recommendation are in [FV01_SEGMENTATION_EXECUTION_BENCHMARK.md](FV01_SEGMENTATION_EXECUTION_BENCHMARK.md). The machine-readable host report is `research/benchmark/toothinstancenet/fv01_1_host_execution.json`.

## Path

Uploaded STL bytes are hashed per arch (`source_mesh_sha256`). The case input hash is a digest of case id, arch, path, and that file hash. `process_uploaded_case` selects the backend from `ALIGNERSTUDIO_SEGMENTATION_BACKEND` (default `onnx`). Real-case mode calls `require_real_case_mode()` before segmentation. `toothinstancenet_fixture` is refused there, in `segmentation_runtime`, and again at persist time by `refuse_fixture_on_real_record`.

When the ToothInstanceNet backend is selected, the engine prepares the mesh, calls the adapter, and maps clusters to instances. The mapper writes a semantic class only when the instance index is inside the model class array and the class is 0–6. It writes confidence only when that instance's score is finite and in `[0, 1]`. It writes `identity=None`, `planning_mode=semantic_only_experimental`, and `identification_incomplete`. It does not call `verified_fdi_number`.

`process_real_uploaded_arch` stamps `segmentation_contract` from the diagnostic plus a non-hashing environment probe. The store rejects a real-case payload whose fixture bit is set or whose source hash does not match the upload. Reopen reads that stored payload. The frontend was not changed. Analysis already shows FDI only when `planningMode` is `clinical_fdi`, which this path no longer emits.

Defects fixed on this path:

- Seven-class labels were stored as FDI and `clinical_fdi`.
- One mean of all class scores was copied onto every instance.
- An out-of-range instance index could borrow a neighbor class.

## Environment probe

Command: `services/api/.venv/bin/python scripts/fv01_segmentation_probe.py`

The probe reports Python, OS, CPU, RAM, `nvidia-smi`, PyTorch (including a CUDA tensor when both are present), pointops, ONNX Runtime, checkpoint presence and SHA-256 when hashing is requested, the code-declared input and output description, the selected backend, and whether inference can execute. It does not download weights, does not select the fixture backend, and does not run ToothInstanceNet.

Measured on this host:

| Field | Value |
|---|---|
| Primary state | `GPU_UNAVAILABLE` |
| Also applicable | `BACKEND_UNAVAILABLE`, `DEPENDENCY_MISSING`, `MODEL_CONTRACT_UNKNOWN` |
| `inference_can_execute` | false |
| `nvidia-smi` | present, exit 9 |
| Driver message | NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running. |
| GPU name | none |
| PyTorch | not installed |
| CUDA tensor executed | false |
| pointops | absent |
| ONNX Runtime | not installed |
| Selected backend | `onnx` |
| Checkpoint env | unset |
| Source checkout env | unset |
| Fixture selected | false |

State order: `INFERENCE_FAILED` if a run was attempted and failed; `INFERENCE_READY` only after a CUDA tensor executed, the checkpoint hash matches the pin, source and pointops are present, and the tensor contract was re-derived; otherwise `GPU_UNAVAILABLE` when the driver is invisible or torch is present without CUDA; then `MODEL_MISSING`, `DEPENDENCY_MISSING`, `BACKEND_UNAVAILABLE`, and `MODEL_CONTRACT_UNKNOWN`. `ENVIRONMENT_READY` is not used as a success substitute.

## Model contract

`MODEL_CONTRACT_UNKNOWN`.

The file `~/.cache/alignerstudio-research/toothinstancenet/checkpoints/instseg_full.ckpt` is present (111,127,353 bytes). Its SHA-256 is `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803`, which matches the pinned digest. That match identifies the file. The state dict was not loaded. Class names were not used as a tensor contract.

Code declares, and this process does not re-derive:

- input: triangle mesh, 6 channels, sampled xyz concatenated with vertex normals
- preprocessing: z-score std 17.3281, voxel size 0.025, pose normalize
- output: per-vertex instance ids and per-cluster class scores
- declared class count: 7
- labels are not unique FDI
- the model does not produce arch, left/right, or FDI

The official Kaggle artifact used `instseg_full.ckpt` and `align.ckpt`. It recorded 14 instances per arch, repeating labels (upper 11–17, lower 31–37), `distinguish_left_right: false`, and `clinical_accuracy_claim: false`. Those labels are not an authoritative numbering method. `landmarks_full.ckpt` was not used for that artifact.

## Inference

Not executed. There is no new instance count, no preprocessing/inference/postprocess time, and no GPU memory sample. A blocked upload stamps the probe primary state and zero instances. That is not an engineering segmentation success and not a clinical result.

The same probe is the rerun entry on a clean GPU machine: `scripts/fv01_segmentation_probe.py`. Inference itself still requires the ToothInstanceNet backend, the source checkout, PyTorch, pointops, and a visible CUDA device. CPU inference is not a supported fallback. The request path calls `run_fv01_probe(hash_checkpoint=False)` so an upload does not hash the 111 MB file.

## Binding and persistence

`segmentation_contract.source_mesh_hash` must equal the uploaded STL SHA-256. `input_hash` / `case_input_hash` must match the case input digest when both are set. Each review instance carries the same source mesh hash. `assert_segmentation_bound` rejects a contract reused for a different mesh.

Persisted contract fields: `case_id`, `job_id`, `input_hash`, `case_input_hash`, `source_mesh_hash`, `arch`, `model_name`, `model_version`, `checkpoint_sha256` (null on the request path; the proof probe records the hash separately), `backend`, `algorithm_version`, `inference_status`, `output_class`, `clinical_accuracy_claim`, `fdi_authoritative`, `tooth_instances`, `tooth_instance_count`, `truth_state`, `limitations`, `provenance`, `fixture`, `created_at`, `timings_ms`, `environment_probe_state`, `inference_can_execute`.

Review rows for a later FV-03 consumer: `tooth_ref`, `arch`, `source_mesh_hash`, `model_label`, `confidence` only when `confidence_available`, `fdi` only when `fdi_authoritative` (always false on this path), and geometry `vertex_count`, `face_count`, `centroid`. No confidence is invented. A missing score is null, not 0.0.

## Fixture firewall

`require_real_case_mode()` refuses `toothinstancenet_fixture` even when `ALIGNERSTUDIO_ALLOW_TEST_FIXTURE_BACKEND=1`. The runtime refuses that backend for real-case processing. `refuse_fixture_on_real_record` refuses a real-case store write whose payload or contract has `fixture: true` or `processing_mode: test_fixture`. Tests keep the fixture backend explicit and test-only.

Regression: real-case processing with the fixture directory configured and the ToothInstanceNet backend selected does not load fixture geometry. Real-case plus an unavailable fixture fails honestly.

## Performance

Inference was not measured. The probe itself:

| Run | `probe_ms` | RSS delta |
|---|---|---|
| First hashed probe | 410.7 ms | 2100 KB |
| Second hashed probe | 296.4 ms | not re-recorded |

No performance target is set.

## Tests

`services/api/.venv/bin/pytest` on:

- `tests/python/test_fv01_real_segmentation_proof.py` (7)
- `tests/python/test_toothinstancenet_engine.py`
- `tests/python/test_toothinstancenet_adapter.py`
- `tests/python/test_toothinstancenet_pipeline.py`
- `tests/python/test_fv01_provenance_guards.py`
- `tests/python/test_wp01_real_clinical_pipeline.py`
- `tests/python/test_wave1_real_segmentation_recovery.py`
- `tests/python/test_wave2_segmentation_benchmark.py`
- `tests/python/test_toothinstancenet_fixture.py`

Result after the FDI and confidence fix: **62 passed**. Frontend typecheck, lint, and build were not run. Frontend code was not changed.

## Capability matrix

B1 and Q2 stay `IMPLEMENTED_BUT_NOT_PROVEN` + `ENVIRONMENT_BLOCKED`. B3 stays `NOT_AVAILABLE_BY_DATA`. None of these rows were marked verified.

## Limitations

- No live inference on this host.
- Tensor shapes are not re-derived from the checkpoint.
- No second real case.
- No clinical numbering, missing-tooth detection, landmarks, or clinical axes.
- Request-path contracts do not repeat the checkpoint hash; the proof probe does.
- Official external artifact remains `clinical_accuracy_claim=false`.

## Next

Do not start FV-02 from this result. The next measurement is the same probe and a real ToothInstanceNet run on a machine where CUDA, PyTorch, pointops, and the source checkout are present. Until that run exists, B1 and Q2 stay unproven.
