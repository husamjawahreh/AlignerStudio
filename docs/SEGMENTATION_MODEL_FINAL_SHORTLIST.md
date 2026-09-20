# Final Segmentation Model Shortlist

**Research-only shortlist date:** 2026-09-20  
**Production status:** no candidate is integrated, configured, or allowed to
bypass `model_unavailable`. No weights were downloaded or committed in this
research pass.

## Summary Comparison

| Model                          | Status                                        | Teeth Instances                                                                                                          | FDI                                                        | Original Mesh Mapping                                                                                                                                               | Upper/Lower                                        | Runtime                                                          | Fragmentation                                                                           | AlignerStudio Compatibility                                                          | License/Usage Status                                                                   |
| ------------------------------ | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| ToothInstanceNet / 3dteethland | CHECKPOINT AVAILABLE; benchmark candidate     | Explicit tooth-instance JSON and landmarks                                                                               | Yes, filename convention selects upper/lower FDI mapping   | Strongest public contract: scan is processed as a named STL/PLY/OBJ and output is saved beside the scan; exact internal vertex correspondence requires verification | Explicit `STEM_lower` / `STEM_upper` naming        | Not measured here; CUDA kernels and multi-GPU inference expected | Instance model, so less dependent on post-hoc same-label components; requires benchmark | **PARTIAL — REQUIRES ADAPTER**; closest to `ToothInstance` contract                  | MIT code; checkpoint/data usage terms require separate review                          |
| 3DTeethSAM                     | CHECKPOINT AVAILABLE; benchmark candidate     | Research README describes automatic 3D instance segmentation; public inference outputs per-vertex labels and cleaned OBJ | Not clearly documented as a production FDI output contract | Point/vertex lifting to OBJ; original correspondence is intended through vertex labels, but exact face/mesh contract needs verification                             | Explicit upper/lower Teeth3DS directory layout     | SAM2/PyTorch3D/PyTorch; GPU-oriented                             | Multi-view voting and lifting may reduce noise; benchmark required                      | **PARTIAL — REQUIRES ADAPTER**; output contract is less direct than ToothInstanceNet | Repository has no detected license metadata; SAM2/checkpoint/data terms require review |
| CrossTooth CVPR2025            | CHECKPOINT AVAILABLE; benchmark candidate     | Public `predict.py` outputs a segmentation mask PLY; individual instances not documented                                 | No public FDI output contract                              | PLY point/mask correspondence; no documented original STL face mapping                                                                                              | Example is upper PLY; arch handling not documented | Point Transformer/pointops; Ubuntu/CUDA/PyTorch expected         | Semantic mask quality requires benchmark; no instance contract                          | **REQUIRES MAJOR POSTPROCESSING**                                                    | Repository has no detected license metadata; checkpoint/data terms require review      |
| MeshSegNet baseline            | Evaluated internally; research reference only | Per-cell semantic classes; observed 33/29 connected non-gingiva regions after decimation                                 | No documented FDI contract                                 | No: author path decimates to 10,000 cells                                                                                                                           | Separate maxillary/mandibular checkpoints          | CPU run succeeded locally; dense adjacency; GPU practical        | Fragmentation observed directly                                                         | **REQUIRES MAJOR POSTPROCESSING**                                                    | MIT source; checkpoint/data rights unclear; `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`        |

## Candidate Details

### 1. ToothInstanceNet / 3dteethland

- **Official repository:** <https://github.com/nnistelrooij/3dteethland>
- **Repository status:** active public project; MIT license metadata reported by
  GitHub; current branch has inference, checkpoint configuration, and test/train
  paths.
- **Checkpoint:** README directs users to an author-provided Google Drive folder
  and requires checkpoint paths in `teethland/config/config.yaml`. A real
  checkpoint is publicly obtainable through that author-linked location, but it
  was not downloaded in this shortlist pass, so no SHA-256 is recorded here.
- **Input:** STL, PLY, or OBJ; filenames must contain `STEM_lower` or
  `STEM_upper` so FDI labels are assigned correctly.
- **Output:** `STEM_lower.json` / `STEM_upper.json` plus landmark JSON. The
  project is specifically named ToothInstanceNet and describes tooth-instance
  segmentations, not only semantic masks.
- **FDI:** README explicitly ties filename jaw handling to correct FDI labels.
- **Original correspondence:** stronger than MeshSegNet at the public contract
  level because the model accepts a scan and writes instance results beside it;
  exact vertex/face mapping and mesh reconstruction still need a benchmark.
- **Requirements:** Conda Python 3.10, pip requirements, compiled CUDA kernels,
  and multi-GPU inference device selection. CPU feasibility is not established.
- **Blockers:** author checkpoint/data license terms, Google Drive artifact
  reproducibility, CUDA kernel build, exact JSON schema, and mapping JSON
  instances into AlignerStudio `ToothInstance` meshes.

### 2. 3DTeethSAM

- **Official repository:** <https://github.com/Crisitofy/3DTeethSAM>
- **Repository status:** active 2025/2026 project; README identifies an official
  PyTorch implementation and AAAI 2026 oral paper.
- **Checkpoint:** README links an author-provided Google Drive containing 3DTeethSAM
  and SAM2 checkpoints. This is a real public checkpoint path, but no artifact
  was downloaded in this research pass and no SHA-256 is recorded.
- **Input:** Teeth3DS-like OBJ with upper/lower directory layout and optional
  JSON; preprocessing renders multi-view data and stores NPZ/HDF5 artifacts.
- **Output:** inference README documents per-vertex labels under
  `inference_results/labels/<jaw>/<case>.txt` and cleaned OBJ meshes. The method
  is described as instance segmentation, but a stable instance-ID plus FDI JSON
  contract is not documented as clearly as ToothInstanceNet.
- **FDI:** Teeth3DS-style labels are involved, but the public inference contract
  does not explicitly guarantee a directly consumable FDI mapping.
- **Original correspondence:** vertex labels are intended to lift predictions
  back to OBJ vertices; exact face/mesh handling and missing-tooth behavior need
  verification.
- **Requirements:** Python 3.10, PyTorch, SAM2 weights, PyTorch3D, CUDA/GPU
  infrastructure, multi-view rendering, and large foundation-model memory.
- **Blockers:** checkpoint/license status, SAM2 and data terms, GPU burden,
  multi-view preprocessing complexity, output-schema validation, and FDI/instance
  mapping.

### 3. CrossTooth CVPR2025

- **Official repository:** <https://github.com/XiShuFan/CrossTooth_CVPR2025>
- **Repository status:** public 2025 repository with an example intraoral scan.
- **Checkpoint:** repository README states `models/PTv1/point_best_model.pth` is
  provided. The exact file exists in the repository tree/model path; its SHA-256
  and usage rights must be recorded before any benchmark download.
- **Input:** example command is `python predict.py --case some.ply --save_path
some_mask.ply`; public path is PLY point data rather than raw STL/OBJ.
- **Output:** mask PLY. Public README does not document individual instance IDs,
  FDI labels, confidence semantics, or upper/lower-specific models.
- **Original correspondence:** PLY point correspondence is plausible, but STL
  face mapping and tooth-instance reconstruction are not documented.
- **Requirements:** Point Transformer/pointops installation, Python/PyTorch,
  Ubuntu 20.04+, and likely CUDA for practical execution.
- **Blockers:** no public FDI/instance contract, PLY conversion, unknown checkpoint
  license, no documented jaw handling, and major post-processing to build teeth.

### MeshSegNet Baseline

MeshSegNet remains the measured baseline, not a new candidate. Its official
checkpoint ran on the real upper/lower pair, but author decimation reduced each
mesh to 10,000 cells and produced fragmented semantic components. It does not
meet the desired instance/FDI output contract without substantial work.

## Findings

ToothInstanceNet has the strongest technical fit because its public input/output
contract is already shaped around `STL/PLY/OBJ -> tooth instances + landmarks +
FDI-aware jaw naming`. 3DTeethSAM is technically promising but has a heavier
multi-view/SAM2 path and a less explicit public FDI output. CrossTooth is easier
to characterize but outputs a point mask rather than a complete tooth-instance
contract.

These findings do not establish commercial or clinical approval. Checkpoints,
data, code dependencies, and output semantics require separate verification.
