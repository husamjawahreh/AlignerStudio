# CrossTooth (CVPR2025) Internal Benchmark

**Status: BLOCKED**  
**INTERNAL RESEARCH ONLY**  
**NOT CLINICALLY VALIDATED**  
**NOT APPROVED FOR COMMERCIAL DEPLOYMENT**

## 1. Repository and Commit

- Repository: <https://github.com/XiShuFan/CrossTooth_CVPR2025>
- Audited commit: `a637a9d37567d5364cad5eea6f7db91d7189a9ee`
  (`a637a9d` — first commit on `main`)
- Repository license: no `LICENSE` file in the checkout; GitHub
  `license` metadata is `null`. Commercial use, redistribution, and
  derivative-work rights were **not** established.
- Research checkout location (external cache only):
  `~/.cache/alignerstudio-research/crosstooth/repo`

No CrossTooth source was copied into production packages, adapters, or
engines.

## 2. Official Checkpoint

The README states:

> Pretrained model is at `models/PTv1/point_best_model.pth`.

| File                     |            Size | SHA-256                                                            | Role                                      |
| ------------------------ | --------------: | ------------------------------------------------------------------ | ----------------------------------------- |
| `point_best_model.pth`   | 27,020,998 bytes | `a03d521dfbf9f77d9077a470e123f66255245b3589ccd6af82972102c027baf9` | Official PTv1 point-feature checkpoint |

The checkpoint is bundled inside the official repository at
`models/PTv1/point_best_model.pth`. A research-only copy was also placed
at:

```text
~/.cache/alignerstudio-research/crosstooth/checkpoints/point_best_model.pth
```

No checkpoint was added to Git or production. The checkpoint bytes were
not altered.

## 3. Canonical Inputs

AlignerStudio standard real-case benchmark inputs (unmodified):

| File | Path | SHA-256 | Size |
| ---- | ---- | ------- | ---: |
| Upper | `data/benchmark/real-case/upper.stl` | `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48` | 8,557,034 bytes |
| Lower | `data/benchmark/real-case/lower.stl` | `dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b` | 6,954,234 bytes |

The canonical STL files were **not** modified. No research working copies
were created because the official inference path was blocked before any
preprocessing step.

## 4. Environment and Dependency Requirements

From `requirements.txt` and repository code:

| Requirement | Observed / documented |
| ----------- | --------------------- |
| OS | Ubuntu 20.04+ encouraged |
| Python | `# python==3.8.19` pin comment |
| PyTorch | `torch==1.13.1+cu117` (+ matching torchvision/torchaudio cu117 wheels) |
| `pointops` | Required from [Point Transformer](https://github.com/POSTECH-CVLab/point-transformer); model imports `models.PointTransformer.libs.pointops.functions.pointops` |
| CUDA packages | `spconv-cu117`, `torch-scatter/sparse/cluster/spline-conv` cu117 builds, `flash-attn` |
| Loader / geometry | `vedo==2023.4.4`, `einops`, `numpy`, optional `pymeshlab`/`open3d`/`pyrender` for prepare scripts |

Host audit for this machine:

- `nvidia-smi`: **failed** — no NVIDIA driver communication
- `nvcc`: **not found**
- `/dev/nvidia*`: unavailable
- Official CUDA 11.7 + compiled `pointops` stack: **not installable/runnable**
  on this host under the benchmark rules (no CPU substitute, no architecture
  change, no checkpoint replacement)

Additional checkout gap: the published repository **does not contain**
`models/PointTransformer/` (the `pointops` tree referenced by
`models/PTv1/point_transformer_seg.py`). Even with a GPU host, the official
import path would need the missing Point Transformer / `pointops` sources
installed as documented by the README.

## 5. Official Inference Path and Input Contract

Documented command:

```text
python predict.py --case "some.ply" --save_path "some_mask.ply"
```

Default checkpoint argument:

```text
--pretrain_model_path models/PTv1/point_best_model.pth
```

### Expected input format

- Official example input: `YBSESUN6_upper.ply` (ASCII PLY with vertices + faces).
- `ToothData` (`dataset/data.py`) loads the mesh with **vedo**, then:
  1. reads original vertex coordinates (`mesh.points()`);
  2. reads faces (`mesh.cells()`);
  3. builds **per-face** features = face centroid XYZ + cell normals (6 channels);
  4. pads/truncates via random permutation to `num_points` / `sample_points`
     (default **16000**);
  5. normalizes XYZ to unit ball.
- STL is **not** the documented predict input. Official path expects a mesh
  loadable as PLY (vedo can load other mesh types, but the README and sample
  are PLY). Any STL→PLY conversion would be research-only and was **not**
  performed because execution was blocked first.

### How correspondence is intended to work (code review only)

- The network classifies **sampled faces** (cell centroids), not original
  STL vertex indices.
- `output_pred_ply` writes:
  - vertices = original `point_coords` (full mesh vertices, neutral RGB);
  - faces = predicted face colors from class → palette, skipping padded
    `(0,0,0)` face index rows.
- Therefore official output is a **face-colored mask PLY** over the input
  mesh topology used at load time, not a per-original-STL-vertex label
  array and not a set of separate tooth meshes.
- Random face permutation + fixed 16k sampling means labels cover at most
  16000 faces per run; denser meshes are subsampled. Exact invertibility to
  every original STL face/vertex was **not** measured on-host.

### Model output schema (code review)

- `PointTransformerSeg38(..., num_classes=17 + 2)` → **19 logits**.
- Softmax + argmax → class ids; classes `17` and `18` are forced to `0`
  (background/gingiva-style) before coloring.
- `utils.py` defines label↔color tables for upper (`UL1`–`UL8`, `UR1`–`UR8`)
  and lower (`LL*`, `LR*`) and an `FDI2color` map (FDI 11–18, 21–28, 31–38,
  41–48).
- **Important code detail:** `predict.py` always applies `lower_palette`
  when coloring predictions, regardless of upper/lower filename. Upper vs
  lower behavior is therefore not validated without a live run.
- Sample shipped mask `YBSESUN6_upper_mask.ply` is an ASCII PLY with
  per-vertex XYZ (neutral) and **per-face RGBA** colors — consistent with
  semantic/face mask output, not an instance JSON.

CrossTooth is therefore best described as a **semantic / tooth-class face
segmentation** model with color-coded class IDs, **not** a complete
tooth-instance + FDI + landmarks pipeline.

## 6. Execution Gate (BLOCKED)

The official path was **not** run to inference.

Hard blockers on this host:

1. No NVIDIA driver / GPU runtime (`nvidia-smi` failure).
2. No `nvcc`.
3. Official dependency stack is CUDA 11.7-centric (`torch==1.13.1+cu117`,
   `spconv-cu117`, cu117 torch-geometric wheels, `flash-attn`).
4. Model implementation hard-codes CUDA tensors (e.g. `torch.cuda.IntTensor`
   in `TransitionDown`) and depends on CUDA `pointops`
   (`furthestsampling`, `queryandgroup`).
5. `pointops` / `models.PointTransformer` sources are missing from the
   published checkout and must be installed separately from the Point
   Transformer repository.

Per benchmark rules:

- no CPU substitute was created;
- model architecture was not altered;
- official checkpoint was not replaced;
- no fixture/fallback segmentation was added;
- production AlignerStudio was not modified for this model.

## 7. Requested Measurements

Because inference was blocked before preprocessing, the following are
**unavailable** (`null` in
[research/benchmark/crosstooth/benchmark.json](../research/benchmark/crosstooth/benchmark.json)):

| Measurement | Status |
| ----------- | ------ |
| Total input points | Not measured (no working PLY run) |
| Total predicted points | Not measured |
| Labels/classes produced | Code suggests classes 0–18 with 1–16 tooth-like; not measured live |
| Number of semantic classes | Designed 17+2 logits; not measured live |
| Teeth individually identifiable | Not measured |
| Individual tooth instances | Not produced by official schema (semantic classes) |
| FDI availability | Color/FDI tables exist in code; not verified live |
| Upper/lower behavior | Not measured; predict path always uses lower palette |
| Label coverage | Not measured |
| Merged teeth | Not measured |
| Fragmented teeth | Not measured |
| Suspicious tiny components | Not measured |
| Original STL vertex/face correspondence | Not measured |
| Reconstruct individual tooth meshes | Not measured |
| Runtime upper / lower | Not measured |
| GPU/CPU memory | Not measured |

No raw prediction PLY/mask was generated for the canonical real-case.

## 8. Connected-Component Instance Experiment

**Not run.**

A deterministic research-only connected-component analysis over predicted
labels was planned only after official masks existed. With no prediction
output, inventing instance splits or accuracy scores would violate the
benchmark rules. No production post-processing was implemented.

## 9. ToothInstance Contract Mapping

Target shape:

```text
ToothInstance {
  id
  fdi
  jaw
  mesh
  centroid
  landmarks
  confidence
}
```

Assessment against **official CrossTooth output + code** (no live run):

| Field | Status | Notes |
| ----- | ------ | ----- |
| `id` | **CANNOT BE SAFELY DERIVED** | Official output is class-colored faces, not stable instance IDs. Connected components might invent IDs later, but that is experimental and was not run. |
| `fdi` | **CANNOT BE SAFELY DERIVED** | `FDI2color` / UL-UR-LL-LR tables exist, but live class→FDI correctness, jaw-specific palette bugs, and missing-tooth behavior were not verified. |
| `jaw` | **CAN BE DERIVED** | Jaw can be supplied from the input path/name (`upper`/`lower`) outside the model; the model itself does not emit a verified jaw field. |
| `mesh` | **CANNOT BE SAFELY DERIVED** | Face colors on a subsampled/padded mesh do not equal validated watertight per-tooth meshes on the original STL without a proven correspondence and extraction path. |
| `centroid` | **CANNOT BE SAFELY DERIVED** | Would require trusted per-tooth point sets first. |
| `landmarks` | **NOT AVAILABLE** | No landmark head/output in the official predict path. |
| `confidence` | **NOT AVAILABLE** | Softmax exists internally but is not written to the mask PLY; no per-tooth confidence contract. |

**Semantic vs instance:** CrossTooth is expected to emit **semantic class
masks** (and colorized faces). It is **not** a complete tooth-instance/FDI
product pipeline. No accuracy score was manufactured.

## 10. Production Impact Confirmation

After this research-only audit:

- production code unchanged for CrossTooth integration;
- segmentation gate unchanged;
- no production adapter added;
- no production dependencies changed for CrossTooth;
- no fixture/fallback segmentation added;
- model architecture and checkpoint unaltered;
- canonical STLs unaltered.

Machine-readable record:
[research/benchmark/crosstooth/benchmark.json](../research/benchmark/crosstooth/benchmark.json).

## 11. Final Status

**BLOCKED** — environment/checkpoint/inference blocker.

Exact blocker summary: this host cannot run the official CUDA 11.7 +
`pointops` Point Transformer segmentation path (no NVIDIA driver, no
`nvcc`, hard CUDA ops in-model, missing `pointops` tree in checkout). The
benchmark stops here without a CPU bypass, architecture change, checkpoint
replacement, production adapter, or further model work.
