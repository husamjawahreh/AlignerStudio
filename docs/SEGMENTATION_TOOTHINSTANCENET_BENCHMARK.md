# ToothInstanceNet Internal Benchmark

**Status: BLOCKED**  
**INTERNAL RESEARCH ONLY**  
**NOT CLINICALLY VALIDATED**  
**NOT APPROVED FOR COMMERCIAL DEPLOYMENT**

## 1. Environment

The benchmark used an isolated research cache and never modified the
production virtual environment, API, React app, production adapter, or
fail-closed segmentation gate.

- Repository: <https://github.com/nnistelrooij/3dteethland>
- Exact commit: `424252e3d94a1565c8c2090eb5bb456b76386b93`
- Source license: MIT
- Official requirements: Python 3.10, PyTorch 2.3.0 with CUDA 12.1,
  PyTorch Lightning 2.3.3, PyTorch Geometric/torch-scatter, and compiled CUDA
  kernels from the repository setup.
- Host GPU: unavailable; `nvidia-smi` could not communicate with an NVIDIA
  driver.
- `nvcc`: unavailable.
- `pointops`: unavailable.

## 2. Checkpoint Information

The official author-linked Google Drive folder was accessible:

<https://drive.google.com/drive/folders/1MIPNtsM3rW_VAUtD8RBPOso1IxyJZgdF?usp=sharing>

The following official checkpoint files were downloaded only into the external
research cache at `~/.cache/alignerstudio-research/toothinstancenet/checkpoints`:

| File                  |              Size | SHA-256                                                            | Official role                     |
| --------------------- | ----------------: | ------------------------------------------------------------------ | --------------------------------- |
| `align.ckpt`          | 217,409,208 bytes | `890d8e02ce9a83253c7c914048bbbc0f4bcbccdda405214ab493d5dcd4d3974a` | `model.align.checkpoint_path`     |
| `instseg_full.ckpt`   | 111,127,353 bytes | `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803` | `model.instseg.checkpoint_path`   |
| `landmarks_full.ckpt` | 115,592,777 bytes | `9d4489439a7e9cab4d368b51de5f6debc41540abd8936a8605afebf1bd2daeff` | `model.landmarks.checkpoint_path` |

Checkpoint usage is research-only. Commercial deployment and redistribution
rights were not established. No checkpoint was added to Git or to the
production application.

## 3. Exact Inputs

The original STL files were untouched. Benchmark working copies were renamed
only in the external research cache:

```text
~/.cache/alignerstudio-research/toothinstancenet/benchmark/input/STEM_upper.stl
~/.cache/alignerstudio-research/toothinstancenet/benchmark/input/STEM_lower.stl
```

Sources:

- `data/uploads/50d34180-53b5-4eb9-8164-f73b0b96650e-upper-38f5de61c3ac42d788fcee7f453318ce.stl`
- `data/uploads/50d34180-53b5-4eb9-8164-f73b0b96650e-lower-8bd6d9913fc44977997e307c337d585b.stl`

Input hashes and sizes are preserved in
[research/benchmark/toothinstancenet/benchmark.json](../research/benchmark/toothinstancenet/benchmark.json).

## 4. Preprocessing and Official Path

The official repository expects filenames containing `STEM_upper` or
`STEM_lower` and supports STL, PLY, and OBJ extensions. The config enables
normalization/cleaning, uniform-density voxel settings, proposal points, and
GPU model execution. The official inference entry point is:

```text
python infer.py instances --devices DEVICES --config teethland/config/config.yaml
```

The repository also supports a separate `landmarks` stage. The model is built
around CUDA point operations and PyTorch Lightning; no documented CPU fallback
was available for this benchmark host.

## 5. Inference Result

The official command was invoked against the exact repository checkout and
config. It stopped before loading the instance model because the isolated
research environment did not contain `pytorch_lightning`:

```text
ModuleNotFoundError: No module named 'pytorch_lightning'
```

Installing that package alone would not make the run viable on this host: the
official requirements also require CUDA 12.1 and compiled CUDA `pointops`, while
this machine has no NVIDIA driver and no `nvcc`.

## 6. Output Schema and Requested Measurements

Because inference was blocked, no raw ToothInstanceNet JSON was produced and
these measurements are unavailable:

- instance IDs;
- FDI/tooth labels;
- jaw field from prediction output;
- landmarks;
- confidence fields;
- represented vertices/points;
- missing teeth;
- fragmented or merged instances;
- runtime per jaw;
- GPU memory; and
- original-mesh correspondence.

The official README states that successful inference writes
`STEM_upper.json`/`STEM_lower.json` and landmark files. The exact generated JSON
schema could not be inspected because the model did not execute.

## 7. AlignerStudio Mapping Assessment

**Status: BLOCKED.** The public contract is promising because it claims tooth
instance JSON and landmark outputs with FDI-aware upper/lower filename handling.
However, without inference output this benchmark cannot verify the required
mapping into:

```text
ToothInstance {
  id, fdi, jaw, mesh, centroid, landmarks, confidence
}
```

A future isolated run must verify whether `instances` map directly to original
STL vertices/faces, whether FDI labels are explicit, and whether confidence is
provided. No production adapter is authorized.

## 8. Final Status

**BLOCKED — environment/inference blocker.** The checkpoint files exist and are
officially author-linked, but the current host cannot execute the official
ToothInstanceNet path because it lacks PyTorch Lightning, NVIDIA CUDA support,
`nvcc`, and compiled pointops. No CPU substitution, alternate checkpoint, or
production integration was attempted.
