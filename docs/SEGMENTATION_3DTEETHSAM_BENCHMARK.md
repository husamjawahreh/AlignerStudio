# 3DTeethSAM Internal Benchmark

**Status: BLOCKED**  
**INTERNAL RESEARCH ONLY**  
**NOT CLINICALLY VALIDATED**  
**NOT APPROVED FOR COMMERCIAL DEPLOYMENT**

## 1. Repository and Commit

- Repository: <https://github.com/Crisitofy/3DTeethSAM>
- Audited commit: `4845f4132cbbeca2ebc456d33de7e0c358385615`
- Repository license: no license metadata was available through the official
  GitHub license endpoint. SAM2 and Teeth3DS/3DTeethSeg terms require separate
  review.

## 2. Official Checkpoints

The official README links this Drive folder:

<https://drive.google.com/drive/folders/1-gGMov__sWje_2ONXyEq09yKPG-plTxU?usp=drive_link>

Downloaded only into the external research cache at
`~/.cache/alignerstudio-research/3dteethsam/checkpoints`:

| File                    |                Size | SHA-256                                                            | Role                  |
| ----------------------- | ------------------: | ------------------------------------------------------------------ | --------------------- |
| `best.pth`              | 1,701,295,825 bytes | `d6cb1acb935b225f0f798b616f9ae1b7249386de79ef4496b892f1e86f599616` | 3DTeethSAM model      |
| `sam2.1_hiera_large.pt` |   898,083,611 bytes | `2647878d5dfa5098f2f8649825738a9345572bae2d4350a2468587ece47dd318` | SAM2 foundation model |

No checkpoint was added to Git or production. Commercial/redistribution rights
were not established.

## 3. Canonical Inputs

The standard local benchmark inputs are:

- `data/benchmark/real-case/upper.stl`
  - SHA-256: `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48`
  - Size: 8,557,034 bytes
- `data/benchmark/real-case/lower.stl`
  - SHA-256: `dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b`
  - Size: 6,954,234 bytes

The canonical STL files were not modified. The official model requires OBJ
input and a Teeth3DS-like upper/lower directory layout, so any future benchmark
must create research-only OBJ working copies under the external benchmark cache.

## 4. Official Pipeline Contract

The repository documents:

- Python 3.10;
- PyTorch and torchvision requirements;
- PyTorch3D installed from its official repository;
- SAM2 checkpoint under `model/sam2/checkpoints/`;
- 3DTeethSAM checkpoint under `ckpts/`;
- multi-view rendering from OBJ geometry;
- seven-view/default view processing;
- 2D mask prediction followed by 2D-to-3D lifting; and
- per-vertex label output under `inference_results/labels/<jaw>/<case>.txt`
  plus cleaned OBJ output.

The inference code returns per-vertex labels after projecting view masks onto
mesh vertices. It does not expose a verified FDI/instance JSON contract in the
public README. The method is described as instance segmentation, but exact
instance-ID, confidence, missing-tooth, and original-face semantics require an
actual run and schema inspection.

## 5. Execution Gate

The official command was not run to inference because the host cannot satisfy
its runtime requirements:

```text
python start_inference.py \
  --input_dir <OBJ_LAYOUT> \
  --checkpoint ckpts/best.pth \
  --output_dir inference_results \
  --num_views 7 \
  --device cuda:0
```

Observed host conditions:

- `nvidia-smi`: failed because no NVIDIA driver could communicate;
- `nvcc`: not found;
- PyTorch3D/SAM2 GPU runtime was not installed;
- official pipeline expects large SAM2 Hiera-L and PyTorch3D rendering.

Per the benchmark rules, no CPU substitute, architecture alteration, or bypass
was attempted.

## 6. Requested Measurements

Because the official inference path was blocked before preprocessing, these are
unavailable:

- tooth instance/label counts;
- per-vertex label coverage;
- upper/lower behavior;
- FDI/tooth identity;
- missing, merged, fragmented, or tiny components;
- original vertex correspondence;
- original-mesh tooth reconstruction;
- upper/lower runtimes; and
- GPU memory usage.

No inference output or visual artifact was generated.

## 7. ToothInstance Mapping Assessment

**Status: BLOCKED.** The public output description suggests per-vertex label
coverage and cleaned OBJ output, which could potentially support deterministic
mesh reconstruction. However, the actual instance schema, FDI mapping,
confidence fields, and exact original-vertex/face semantics could not be
verified without a successful official run.

No AlignerStudio adapter was created or modified.

## 8. Final Status

**BLOCKED — GPU/runtime gate.** 3DTeethSAM has official checkpoints and a
reproducible documented input/output direction, but this host cannot execute the
required CUDA/PyTorch3D/SAM2 pipeline. The production segmentation gate and all
production behavior remain unchanged.
