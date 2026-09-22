# ToothInstanceNet Reproducible Runtime

Research-only Docker runtime for the existing AlignerStudio ToothInstanceNet
adapter and `run_acceptance.py`. It does not modify production and does not
clone or download the upstream model source at runtime.

## Build

The exact validated source checkout must exist locally at:

```text
~/.cache/alignerstudio-research/toothinstancenet/source
```

and must resolve to:

```text
424252e3d94a1565c8c2090eb5bb456b76386b93
```

From the repository root, stage the exact local source checkout and run the
plain Docker build command through the provided wrapper:

```bash
export ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE=$HOME/.cache/alignerstudio-research/toothinstancenet/source
research/benchmark/toothinstancenet/runtime/build.sh
```

The wrapper executes this exact build command inside a temporary context:

```bash
docker build -t alignerstudio-toothinstancenet:validated .
```

The image uses:

- Ubuntu 24.04
- NVIDIA CUDA 12.8.1 + cuDNN development image
- Python 3.12
- PyTorch 2.10.0 + cu128
- `torch-scatter` compiled in the image against that Torch/CUDA pair
- upstream `pointops` compiled in the image against that pair
- ToothInstanceNet source revision `424252e3d94a1565c8c2090eb5bb456b76386b93`

## Run

The checkpoint remains outside Git and is mounted read-only:

```bash
docker run --rm --gpus all \
  -e ALIGNERSTUDIO_TOOTHINSTANCENET_TEST_CASE=/case \
  -e ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT=/checkpoints/instseg_full.ckpt \
  -e ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE=/opt/3dteethland \
  -v "$PWD/data/benchmark/real-case:/case:ro" \
  -v "$HOME/.cache/alignerstudio-research/toothinstancenet/checkpoints:/checkpoints:ro" \
  -v "$HOME/.cache/alignerstudio-research/toothinstancenet/acceptance:/root/.cache/alignerstudio-research/toothinstancenet/acceptance" \
  alignerstudio-toothinstancenet:validated \
  python run_acceptance.py
```

The acceptance command verifies the checkpoint SHA-256 before loading the
model. It reports `runtime_unavailable` if no GPU is visible, and
`runtime_dependency_unavailable` for missing Torch/native dependencies. The
runtime never downloads weights and never uses Kaggle paths.

## Pre-flight check

After building, inspect the runtime manifest:

```bash
docker run --rm --gpus all \
  -e ALIGNERSTUDIO_TOOTHINSTANCENET_CHECKPOINT=/artifacts/instseg_full.ckpt \
  -v "$HOME/.cache/alignerstudio-research/toothinstancenet/checkpoints:/artifacts:ro" \
  -e ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE=/opt/3dteethland \
  alignerstudio-toothinstancenet:validated \
  python /opt/alignerstudio/runtime-manifest.py
```

This verifies `nvidia-smi`-equivalent CUDA visibility through Torch,
`torch.cuda.is_available()`, the CUDA device, all required pointops symbols,
the exact source revision, and checkpoint SHA-256. It exits with a clear
`runtime_unavailable`, `runtime_dependency_unavailable`, or
`checkpoint_integrity_failed` classification when blocked.

The upstream `pointops` extension must expose the compiled functions used by
ToothInstanceNet, including farthest-point sampling, ball/KNN queries,
stratified query-key pairs, CRPE aggregate values, and CRPE attention logits.

## Current host status

This host currently has no Docker, NVIDIA driver, GPU, `nvcc`, or installed PyTorch, so
the Docker acceptance run cannot be executed here until a host with a working
NVIDIA Container Toolkit is provided. No inference result is claimed.

The exact real acceptance command is:

```bash
python run_acceptance.py
```

The current status is **REAL_GPU_ACCEPTANCE_PENDING**.
