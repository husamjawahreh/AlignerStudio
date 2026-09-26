# FV-01.1 — ToothInstanceNet execution and model-contract reproduction

| | |
|---|---|
| Phase | FV-01.1 only |
| Date | 2026-09-26 |
| Verdict | **PASS WITH BLOCKER** |
| Clinical accuracy | `NOT_ESTABLISHED` |
| Recommendation | **B.** ToothInstanceNet stays the primary segmentation path and requires a clean GPU runtime package. It is not production-ready on this host. |

No screenshots. Evidence is the runner JSON at `research/benchmark/toothinstancenet/fv01_1_host_execution.json`.

## Checkpoint identity

| Field | Value |
|---|---|
| Path | `~/.cache/alignerstudio-research/toothinstancenet/checkpoints/instseg_full.ckpt` |
| Bytes | 111,127,353 |
| SHA-256 | `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803` |
| Matches pin | yes |
| Archive | PyTorch zip, `archive/data.pkl` |
| Lightning | 2.3.3 |
| Epoch / global step | 499 / 112000 |
| `hyper_parameters` in file | no |
| Source revision | `424252e3d94a1565c8c2090eb5bb456b76386b93` (checkout matches the pin; env var unset) |
| State-dict tensors | 410 |

Shapes were read with a restricted unpickler. Weight values were not restored. PyTorch was not imported. The production segmentation pipeline was not changed to load this file.

## Tensor contract

`TENSOR_CONTRACT_ESTABLISHED`. This is not a clinical label map.

Evidence is the state dict, checked against the pinned source where a shape needs a layout. Source defaults that disagree with the tensors are not used.

| Tensor | Shape | Meaning |
|---|---|---|
| `instance_model.point_embedding.0.kpconv.K_points` | `(15, 3)` | 15 kernel points in 3D |
| `instance_model.point_embedding.0.kpconv.weight` | `(15, 6, 48)` | `[kernel points, num_inputs, num_outputs]`. Input width is 6. |
| `instance_model.heads.0.linear.weight` | `(6, 48)` | 3 offsets concatenated with 3 sigmas. `DentalNet` sets `out_channels=[6, 1, None]`. |
| `instance_model.heads.1.linear.weight` | `(1, 48)` | one seed logit |
| `instance_model.heads.2.*` | absent | the third head is features, not a classifier |
| `identify_model.mlp.0.weight` | `(64, 48)` | masked-average MLP, feature width 48 |
| `identify_model.mlp.2.weight` | `(64, 64)` | hidden layer |
| `identify_model.mlp.4.weight` | `(7, 64)` | 7 logits per instance |
| `identify_model.mlp.4.bias` | `(7,)` | classification bias |

Input is a variable-size point cloud. There is no fixed point count in the checkpoint. No state-dict key encodes FDI, arch, or left/right.

The network does not emit instance ids. `teethland/models/dentalnet.py` calls `learned_region_cluster` on offsets, sigmas, and seeds. The Aligner Studio adapter does the same after `instance_model`, then runs `identify_model` on those clusters. Instance ids are downstream logic.

The 7-logit head is a per-instance classifier, not a per-vertex semantic map. `TeethInstSegDataModule.num_classes` returns 7 only when left/right are not split, third molars are folded into second molars, and upper/lower are not doubled. That formula is not stored in the checkpoint. `teethland/config/config.yaml` in the same checkout sets `distinguish_left_right: true` and `m3_as_m2: False`, which would not return 7. Class index names are therefore not established. They are not FDI.

Preprocessing values (voxel size 0.025, z-score std 17.3281, pose normalize) are code and yaml declarations. They are not in the checkpoint, so they stay undeclared by this load.

## Runtime on this host

Command: `services/api/.venv/bin/python scripts/fv01_execution_runner.py`

Exit code: `2` (`DRIVER_UNAVAILABLE`).

| Check | Result |
|---|---|
| OS / CPU / RAM / Python | Linux 7.0.0-34-generic · Intel Core i5-10500H · 16,571,219,968 bytes · 3.12.3 |
| Driver | `nvidia-smi` present, exit 9, driver not visible |
| PyTorch | `PYTORCH_UNAVAILABLE` |
| CUDA tensor | not executed |
| `nvcc` | absent |
| pointops | `POINTOPS_UNAVAILABLE` |
| ONNX Runtime | `ONNX_UNAVAILABLE` |
| ONNX artifact | `ONNX_BACKEND_NOT_READY` |
| Selected backend | `onnx` |
| Fixture selected | false |
| Inference | not attempted |

Applicable states, uncollapsed: `DRIVER_UNAVAILABLE`, `PYTORCH_UNAVAILABLE`, `POINTOPS_UNAVAILABLE`, `ONNX_UNAVAILABLE`, `ONNX_BACKEND_NOT_READY`.

`MODEL_CONTRACT_UNKNOWN` is not applicable after the state-dict read.

## CPU

Ruled out. `setup.py` at the pinned revision builds `pointops` only with `CUDAExtension`. There is no `CppExtension`. The listed sources are CUDA files for farthest-point sampling, ball/KNN query, and CRPE attention. A CPU network forward is not available. No CPU fallback was implemented. `learned_region_cluster` itself is ordinary PyTorch, and it cannot run until the CUDA network has produced offsets, sigmas, and seeds.

## ONNX

`ONNX_BACKEND_NOT_READY`. No `.onnx` ToothInstanceNet artifact is configured. ONNX Runtime is not installed. The default `onnx` backend is a MeshSegNet face-feature adapter with no weights. It was not treated as a fallback, and no ONNX model was exported.

## Real inference

Not run. Requesting inference without a READY runtime is refused. There is no instance count, class distribution, preprocessing time, inference time, postprocess time, persistence time, or GPU memory sample from a forward pass.

On a machine that reports `READY`, the same script runs the production engine:

```bash
python scripts/fv01_execution_runner.py --run-inference --stl /path/to/real.stl
```

That path refuses fixture geometry, records the STL SHA-256, and does not write FDI.

## Engineering comparison

Clinical accuracy is `NOT_ESTABLISHED`. No labeled evaluation was run.

| Property | This host |
|---|---|
| Inference runtime | not measured |
| Preprocessing | not measured |
| Memory | runner RSS delta about 3.8 MB; no GPU memory |
| Output representation | point-cloud instance clustering plus 7 per-instance logits |
| Dependency footprint | CUDA PyTorch, compiled pointops, pinned source, 111 MB checkpoint |
| Reproducibility | runner report is deterministic for this file. Inference nondeterminism was not measured because no forward pass ran. |
| Integration | production engine exists and is blocked before the forward pass |

## Performance of the runner

| Measurement | Value |
|---|---|
| `runner_ms` | 328.3 |
| `contract_extraction_ms` | 20.6 |
| `inference_ms` | null |
| `peak_rss_kb_delta` | 3816 |
| `peak_gpu_memory_bytes` | null |

No inference target is set.

## Recommendation

**B.** Keep ToothInstanceNet as the primary segmentation backend, and require the clean GPU package before any real case is claimed: visible NVIDIA driver, CUDA PyTorch, compiled pointops, source revision `424252e3d94a1565c8c2090eb5bb456b76386b93`, and the pinned checkpoint. Do not replace it with another model from this measurement. Do not call the current code path production-ready. CPU and ONNX are not substitutes.

B1 and Q2 stay `IMPLEMENTED_BUT_NOT_PROVEN` + `ENVIRONMENT_BLOCKED`. B3 stays `NOT_AVAILABLE_BY_DATA`.

## Remaining blockers

- NVIDIA driver is not visible (`nvidia-smi` exit 9).
- PyTorch, CUDA, and pointops are not installed.
- No real STL has been segmented on this host.
- Class index names are not in the checkpoint.
- Clinical accuracy is not established.
