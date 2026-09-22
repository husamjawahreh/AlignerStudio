# Real-Case ToothInstanceNet Kaggle Run

This workflow runs the official ToothInstanceNet instance pipeline on the real
upper/lower STL inputs and produces an audited AlignerStudio development
fixture. It is not clinical validation and it does not modify production.

## 1. Required Kaggle datasets

Attach:

- `husamjawahreh/alignerstudio-real-case`
  - `upper.stl`
  - `lower.stl`
- `husamjawahreh/toothinstancenet-checkpoints`
  - `instseg_full.ckpt`

## 2. GPU requirement

Use a Kaggle GPU environment matching the validated runtime: Python 3.12,
PyTorch 2.10.0+cu128, CUDA available, and the native `pointops` extension.
Do not use CPU or substitute models.

## 3. Source/checkpoint paths

```text
source revision: 424252e3d94a1565c8c2090eb5bb456b76386b93
checkpoint: /kaggle/input/datasets/husamjawahreh/toothinstancenet-checkpoints/instseg_full.ckpt
checkpoint sha256: 100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803
inputs: /kaggle/input/datasets/husamjawahreh/alignerstudio-real-case
```

## 4. Setup cell

```python
!pip install -q -r /kaggle/working/AlignerStudio/research/benchmark/toothinstancenet/runtime/requirements-runtime.txt
!pip install -q --index-url https://download.pytorch.org/whl/cu128 torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0
```

Build/install the exact local source checkout and native pointops extension
before running the command below.

## 5. One execution command

```bash
python /kaggle/working/AlignerStudio/research/benchmark/toothinstancenet/kaggle/run_real_case.py
```

The runner verifies source revision/checkpoint, exact preprocessing counts,
runs official instances inference, creates meshes from original STL faces,
audits, and packages the ZIP.

## 6. Audit command

```bash
python /kaggle/working/AlignerStudio/research/benchmark/toothinstancenet/kaggle/audit_real_case_artifact.py \
  --artifact-dir /kaggle/working/toothinstancenet-real-case-artifact \
  --input-dir /kaggle/input/datasets/husamjawahreh/alignerstudio-real-case \
  --checkpoint-sha256 100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803
```

## 7. Packaging command

```bash
bash /kaggle/working/AlignerStudio/research/benchmark/toothinstancenet/kaggle/package_real_case_artifact.sh \
  /kaggle/working/toothinstancenet-real-case-artifact \
  /kaggle/working/toothinstancenet-real-case-artifact.zip
```

## 8. Output locations

```text
/kaggle/working/toothinstancenet-real-case-artifact/
/kaggle/working/toothinstancenet-real-case-artifact.zip
```

The package contains root `upper.json`/`lower.json`, audit/manifests, NPZ
correspondence files, and `individual_meshes/`.

## 9. Download ZIP

In Kaggle’s Files panel, download:

```text
/kaggle/working/toothinstancenet-real-case-artifact.zip
```

Unpack it to a local development directory and set:

```text
ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet_fixture
ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR=<unpacked-directory>
```

## 10. Success output

Success must report `REAL_CASE_ARTIFACT_READY` and an independent audit with
`status: PASS`. The package must identify:

```text
source_kind=validated_real_case
fixture=true
experimental=true
```

## 11. Count mismatch

Expected validated reference counts are lower `20040` and upper `21219`
selected InstSeg points. If counts differ, the runner stops unless
`--allow-count-difference` is explicitly supplied. Audit the preprocessing
before proceeding; do not silently accept the difference.

## 12. Checkpoint/native failures

A checkpoint mismatch is `checkpoint_integrity_failed`. Missing Torch/CUDA or
pointops is a runtime dependency failure. Do not download another checkpoint,
change the model, use CPU substitution, or fabricate output.
