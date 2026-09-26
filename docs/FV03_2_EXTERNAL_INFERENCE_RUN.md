# FV-03.2 — External CUDA inference run

| | |
|---|---|
| READY_FOR_EXTERNAL_INFERENCE_RUN | true |
| GENUINE_EXTERNAL_INFERENCE_COMPLETED | false |
| Server seal of an A100 bundle | not performed |
| Clinical accuracy | NOT ESTABLISHED |
| FDI mapping | NOT ESTABLISHED |
| FV-04 | not started |

This document is the procedure for one real ToothInstanceNet run on the qualified CUDA host. Running the command on a machine without that runtime must not write raw instances.

## Preprocessing

Use the official repository prediction dataset:

`teethland.data.datasets.TeethSegDataset(norm=True, clean=True)`

followed by:

1. `ZScoreNormalize(norm=True)`
2. `PoseNormalize(clean=True)`
3. `InstanceCentroids`
4. `UniformDensityDownsample(0.025)`
5. `XYZAsFeatures`
6. `NormalAsFeatures`
7. `ToTensor`

Do not substitute `adapters.toothinstancenet.preprocessing.prepare_mesh`.

The seed `123456` is the verified reproducibility seed for this configuration. Pass it explicitly. It is not a universal production default. Recording the seed does not claim that CUDA inference is deterministic. The bundle records `inference_determinism = NOT_CLAIMED`.

## Model

| Item | Value |
|---|---|
| Checkpoint | `instseg_full.ckpt` |
| SHA-256 | `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803` |
| Input channels | 6 |
| Identify logits | 7 |
| Instance ids | learned region clustering from offsets, sigmas, and the seed head |
| Model class | raw class index, not FDI |

Do not change weights, architecture, or thresholds. Do not map the seven classes to tooth numbers, arch, or left/right.

## Prepared input

Export the accepted prepared mesh for one arch from the Aligner Studio case. The file SHA-256 must equal that case's prepared artifact SHA. The mesh filename stem must contain `upper` or `lower`, matching `--arch`. Face indices in the raw output refer to that file as loaded by trimesh with `process=False`. If the official dataset triangles differ from those faces, the run stops and does not remap them.

## Command

On the qualified Colab/A100 environment, with the pinned 3dteethland checkout and checkpoint:

```bash
export ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE=/content/3dteethland
export ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT=/content/drive/MyDrive/instseg_full.ckpt
export ALIGNERSTUDIO_TOOTHINSTANCENET_DEVICE=cuda

python scripts/fv03_2_external_inference_run.py \
  --execute \
  --prepared-mesh /path/to/prepared-upper.stl \
  --case-id CASE_ID \
  --arch upper \
  --seed 123456 \
  --output external_inference_bundle
```

Without `--execute`, the script prints the protocol and does not infer.

The process records the live Python, PyTorch, CUDA, GPU model, compute capability when CUDA exposes it, pointops build identity, and `nvcc` when present. Missing mandatory runtime fields block the bundle. Peak GPU memory and duration are recorded only from the executed forward. Model confidence is the identify-head softmax maximum when that value is finite and in `[0, 1]`. It is not clinical confidence.

## Bundle

Output directory: `external_inference_bundle/`

| File | Role |
|---|---|
| `manifest.json` | SHA-256 of the prepared file, checkpoint, raw output, and import payload |
| `runtime.json` | Measured host values. Not a substitute for the payload fields |
| `preprocessing.json` | Official pipeline, seed, determinism note |
| `model.json` | Qualified DentalNet contract and observed checkpoint SHA |
| `raw_output/instances.json` | Immutable raw instances |
| `validation.json` | Local precheck. `server_seal` stays `NOT_RUN` |
| `evidence.json` | Body for the import endpoint. No timestamp in this file |
| `README.md` | Transfer note |
| `status.json` | `GENUINE_EXTERNAL_INFERENCE_COMPLETED` is true only after this command's forward returns |

Do not edit the bundle after `manifest.json` is written.

## Import

Copy the directory back to the repository host. Post `evidence.json` to:

`POST /cases/{case_id}/uploads/{arch}/segmentation/external-evidence`

The server recomputes hashes, checkpoint identity, prepared SHA, geometry, and the evidence identity hash. A client `verified: true` field is ignored. A passing seal stores `execution_origin = EXTERNAL_CUDA` and `native_execution = false`. Review starts as `MODEL_PREDICTION`. Doctor acceptance is not clinical verification.

If geometry is invalid, the server does not seal the run and does not repair the mesh.

## Not established by this protocol

Preparing the runner does not establish clinical accuracy, FDI correctness, ground-truth segmentation quality, or doctor approval. Those stay not established until a real bundle is imported and, separately, a real reference or clinical review exists.
