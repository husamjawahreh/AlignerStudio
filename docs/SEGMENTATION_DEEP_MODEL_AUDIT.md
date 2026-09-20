# Deep 3D Intraoral Tooth-Segmentation Model Audit

**Audit date:** 2026-09-20  
**Scope:** research only. No production code, dependency, adapter, gate,
fixture, checkpoint, or inference output was changed or added.

Canonical inputs for all future model evaluation remain unchanged:

- `data/benchmark/real-case/upper.stl`
  - SHA-256: `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48`
- `data/benchmark/real-case/lower.stl`
  - SHA-256: `dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b`

## Executive Findings

- **ToothGroupNetwork / TGNet** is the only primary candidate with a documented
  real 3D intraoral OBJ inference path, author-linked pretrained checkpoints,
  challenge-format instance/FDI JSON, and enough documentation for a meaningful
  isolated benchmark. It is blocked on this host by CUDA/pointops and remains
  legally unresolved because source and weight terms are absent and the
  referenced Teeth3DS data has separate terms.
- **TSegAgent** is technically interesting, but its FDI stage depends on an
  external VLM service (`OPENAI_API_KEY` or `ARK_API_KEY`), SAM3 installation and
  separately accessed weights. No paid API was called. Its SAM3 dependency is
  not version-pinned and GitHub reports `Other/NOASSERTION` licensing metadata.
- **OrthoTwin3D/OrthoGeo3D** is a project roadmap plus a DGCNN semantic baseline;
  instance postprocessing, landmarks, and geometry are explicitly future work.
  No released pretrained checkpoint was found.
- **PMTSeg** has a substantial photo-guided instance pipeline and research
  outputs, but no downloadable checkpoint was found. It requires CUDA PointNet2,
  `nvcc`, CMake, OpenGL/EGL, and the `revras` rasterizer.
- **THISNet** has an instance-mask architecture but its test script expects a
  placeholder local checkpoint and hard-codes CUDA. No FDI contract or weight
  download is published.
- The unified `3d_tooth_segmentation` repository maintains a DGCNN semantic
  baseline and training/evaluation scripts, but no pretrained checkpoint or
  instance/FDI output contract was found. No further realistic candidate was
  identified in its registry/code.
- No accuracy score was produced. No model was run and no checkpoint was
  downloaded.

## Compatibility Matrix

Values are factual audit states: `YES`, `NO`, `PARTIAL`, `UNKNOWN`, or `BLOCKED`.

| Model | 3D IOS | STL | Instances | FDI | Original Mesh | Landmarks | Confidence | Pretrained | CPU | GPU | Checkpoint Available | License Status | Commercial Status | Engineering Effort | Execution Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TSegAgent | YES | UNKNOWN | YES | PARTIAL | PARTIAL | UNKNOWN | PARTIAL | PARTIAL | NO | YES | UNKNOWN | SOURCE_APACHE / SAM3_OTHER / VLM_UNCLEAR | UNKNOWN | HIGH | BLOCKED |
| OrthoTwin3D / OrthoGeo3D | YES | UNKNOWN | PARTIAL | PARTIAL | PARTIAL | NO | NO | NO | UNKNOWN | YES | NO | NO REPOSITORY LICENSE | UNKNOWN | HIGH | BLOCKED |
| ToothGroupNetwork / TGNet | YES | NO | YES | YES | PARTIAL | NO | UNKNOWN | YES | NO | YES | YES | SOURCE/WEIGHTS UNCLEAR | NOT ESTABLISHED | MEDIUM | BLOCKED |
| Unified DGCNN baseline | YES | UNKNOWN | NO | PARTIAL | PARTIAL | NO | PARTIAL | NO | UNKNOWN | YES | NO | NO REPOSITORY LICENSE | UNKNOWN | HIGH | BLOCKED |
| PMTSeg | YES | UNKNOWN | YES | PARTIAL | PARTIAL | NO | PARTIAL | NO | NO | YES | NO | SOURCE_APACHE / WEIGHTS UNCLEAR | UNKNOWN | HIGH | BLOCKED |
| THISNet | YES | UNKNOWN | YES | UNKNOWN | PARTIAL | NO | PARTIAL | NO | NO | YES | NO | NO REPOSITORY LICENSE | UNKNOWN | HIGH | BLOCKED |

`3D IOS` means the repository targets 3D intraoral/dental scans, not that the
exact AlignerStudio STL pair has been accepted. `Original Mesh` is only YES
when the published path proves stable original vertex/face indexing; none of
these audits met that standard.

## Repository and Commit Inventory

| Candidate | Repository | Audited commit | Repository license metadata |
| --- | --- | --- | --- |
| TSegAgent | <https://github.com/znshje/TSegAgent> | `5dea4d347966121a7cdbb18e7a08009af1a2d310` | Apache-2.0 file and GitHub metadata |
| OrthoGeo3D | <https://github.com/lachtarnour/OrthoGeo3D> | `16a20f13a6968214787c76f854627a361455a9be` | None found; GitHub `license: null` |
| ToothGroupNetwork | <https://github.com/limhoyeon/ToothGroupNetwork> | `d7e16a4b8fca811975c3a4c7c1429bb0a51b3083` | None found; GitHub `license: null` |
| Unified benchmark | <https://github.com/irfanfadhullah/3d_tooth_segmentation> | `e344796c1492e270ba930609f60625a66778180d` | None found; GitHub `license: null` |
| PMTSeg | <https://github.com/znshje/PMTSeg> | `e07a508ab9089113e5efd4835d18f6e0d753096e` | Apache-2.0 file and GitHub metadata |
| THISNet | <https://github.com/li-pengcheng/THISNet> | `9fb881e78a24c52cb0d0cde1576369d142f53f85` | None found; GitHub `license: null` |

All clones are external research cache only:
`~/.cache/alignerstudio-research/model-discovery/`.

## TSegAgent Audit

**Repository:** <https://github.com/znshje/TSegAgent>  
**Commit:** `5dea4d347966121a7cdbb18e7a08009af1a2d310`  
**Source license:** Apache-2.0. This does not grant rights to SAM3 weights,
VLM services, or Teeth3DS data.

### Runtime and dependencies

- README requires Python `3.12+`, PyTorch `2.7+`, CUDA `12.6+`, C++17, and
  OpenGL development libraries.
- `requirements.txt` pins `torch==2.9.1+cu130`,
  `torchvision==0.24.1+cu130`, `vedo==2025.5.4`, `trimesh==4.10.0`,
  `openai==2.9.0`, `transformers>=5.0.0rc0`, `accelerate`, and `peft`.
- SAM3 is installed separately from `facebookresearch/sam3`; TSegAgent does
  **not** pin an exact SAM3 commit/version. GitHub metadata for SAM3 reports
  `Other` / `NOASSERTION`, not a usable commercial license grant.
- The project also builds `reversible_rasterizer` for rendered pixel-to-face
  relationships.
- Single-GPU feasibility is plausible in principle, but the repository gives
  no VRAM estimate. A single GPU with the stated CUDA/PyTorch stack plus SAM3
  is required; current host cannot run it.

### Input, output, and VLM/FDI behavior

- Documented input is a Teeth3DS-style directory containing separate
  `*_upper.obj` and `*_lower.obj` files plus split lists and labels. Arbitrary
  STL/OBJ dental scans are not demonstrated.
- The pipeline is zero-shot segmentation through SAM3 plus geometry-aware
  rendering. It produces instance masks and has JSON export code.
- FDI classification is not an entirely local model stage. README requires
  either `OPENAI_API_KEY` or `ARK_API_KEY`; documented VLM choices are
  `chatgpt-5.2` and `doubao-seed 1.8`. `--disable-gpt` explicitly disables FDI
  classification.
- No paid API was called during this audit. Whether a local VLM can replace
  the service is **UNKNOWN**; the repository documents service names, not a
  local replacement interface or equivalent accuracy contract.
- Reversible rasterization is intended to map rendered pixels to mesh faces.
  The exact exported JSON schema, original-face guarantees, and vertex mapping
  were not validated by execution. A safe mesh field therefore remains
  **DERIVABLE only after a benchmark**, not available now.
- Landmarks are not documented. Confidence is not a stable per-tooth output
  contract even if internal mask/VLM scores exist.

### Checkpoint and usage status

No TSegAgent checkpoint is published in the repository. SAM3 weights require
separate access through the SAM3 project. Source, SAM3, VLM, and dataset rights
must be cleared independently. Current status: **BLOCKED**.

### ToothInstance mapping

| Field | Status |
| --- | --- |
| `id` | AVAILABLE only if exported mask-instance schema is confirmed |
| `fdi` | DERIVABLE only through the external VLM stage |
| `jaw` | DERIVABLE from upper/lower dataset context |
| `mesh` | DERIVABLE only after validating rasterizer face mapping |
| `centroid` | DERIVABLE from trusted instance geometry |
| `landmarks` | NOT AVAILABLE |
| `confidence` | CANNOT BE SAFELY DERIVED |

## OrthoGeo3D / OrthoTwin3D Audit

**Repository:** <https://github.com/lachtarnour/OrthoGeo3D>  
**Commit:** `16a20f13a6968214787c76f854627a361455a9be`  
**License:** none found.

The README calls the repository **OrthoTwin3D** and lays out a project plan:
point-wise FDI segmentation, instance postprocessing, landmarks, geometry, and
future multitask/transformer work. The maintained implementation is a DGCNN
semantic baseline trained on prepared 60,000-point Teeth3DS tensors.

- Input: prepared point data; no direct STL inference command.
- Output: point-wise labels and validation metrics. Instance cleanup and
  landmarks are listed as project phases, not a completed output contract.
- Checkpoint: README references `OUTPUT_DIR/.../best.pt` generated by training;
  no released pretrained checkpoint was found.
- Dataset preparation downloads/uses Teeth3DS. Dataset and model-weight rights
  are not documented for commercial use.
- No FDI JSON, original mesh/face projection, landmark, or confidence contract
  was verified.

**Status:** reject from actual benchmarking until a released checkpoint and a
completed inference/export path exist.

ToothInstance mapping: `id` can be derived only after unimplemented instance
postprocessing; `fdi` is PARTIAL; `jaw` is derivable from input; `mesh` cannot
be safely derived; centroid is derivable only after trusted instances;
landmarks and confidence are not available.

## ToothGroupNetwork / TGNet Audit

**Repository:** <https://github.com/limhoyeon/ToothGroupNetwork>  
**Commit:** `d7e16a4b8fca811975c3a4c7c1429bb0a51b3083`  
**License:** no repository license file or GitHub license metadata.

This is the strongest documented candidate for an isolated future benchmark,
not a production recommendation.

- Input: separate upper/lower OBJ meshes named `casename_upper.obj` and
  `casename_lower.obj`; axes must follow the project convention. Raw STL is
  not the documented input.
- Preprocessing: farthest-point sampling. Inference can receive the original
  OBJ parent directory and perform sampling internally.
- Output: challenge-format JSON files matching ground truth format. The
  challenge semantics provide instance and FDI labels, and separate upper/lower
  output files.
- Checkpoints: README links author-provided Google Drive `ckpts(new).zip`.
  It was not downloaded during this audit.
- Runtime: tested with PyTorch 1.7.1 CUDA 11.0; custom `pointops`; batch size
  one; minimum 11 GB GPU; RTX40 compatibility issues are explicitly noted.
- The JSON likely supports per-point/vertex challenge indexes, but original
  full-mesh correspondence after FPS must be verified experimentally. No
  landmark field is documented. Confidence semantics are unknown.
- Referenced 3DTeethSeg/Teeth3DS data has separate terms; data rights do not
  follow from repository visibility. Weight rights are not stated.

### ToothInstance mapping

| Field | Status |
| --- | --- |
| `id` | AVAILABLE in challenge JSON semantics |
| `fdi` | AVAILABLE in challenge JSON semantics |
| `jaw` | DERIVABLE from filename |
| `mesh` | DERIVABLE only after validating JSON indexes and FPS mapping |
| `centroid` | DERIVABLE from trusted point sets |
| `landmarks` | NOT AVAILABLE |
| `confidence` | UNKNOWN |

**Benchmark gate:** obtain the linked archive and rights information first,
then run only in an isolated GPU environment. Do not train.

## Unified Benchmark Audit and Additional Candidates

**Repository:** <https://github.com/irfanfadhullah/3d_tooth_segmentation>  
**Commit:** `e344796c1492e270ba930609f60625a66778180d`  
**License:** none found.

The repository is a maintained DGCNN segmentation baseline with data download,
patient split, preprocessing, training, and evaluation scripts. It is not a
registry containing a set of ready-to-run pretrained models. No checkpoint
link, model archive, or individual-instance/FDI export was found.

- Input: prepared Teeth3DS point tensors; STL/OBJ/PLY direct support is not
  documented.
- Output: point-wise semantic labels and metrics.
- CPU behavior: not established. GPU is expected for practical training and
  inference.
- Original mesh correspondence, landmarks, confidence, and missing-tooth
  handling are not documented.

**Additional shortlist:** no additional model beyond this DGCNN baseline met
all of the requested realistic-candidate criteria. In particular, no model in
the inspected registry had both an obtainable pretrained checkpoint and a
verified individual-tooth/FDI inference contract. No training was attempted.

## PMTSeg Audit

**Repository:** <https://github.com/znshje/PMTSeg>  
**Commit:** `e07a508ab9089113e5efd4835d18f6e0d753096e`  
**Source license:** Apache-2.0. Weight and data rights are not stated.

- Targets photo-guided tooth segmentation on a 3D oral scan.
- Requires CUDA PointNet2 extensions, `nvcc`, CMake >=3.27, OpenGL/EGL,
  `revras`, and prepared Teeth3DS-compatible data.
- The test command expects `best_1.ckpt` in a locally trained experiment
  directory. No downloadable pretrained checkpoint was found.
- Documented outputs include PLY meshes, JSON labels, JPG overlays, and TLA,
  TSA, and TIR metrics. A stable FDI field, landmarks, or confidence contract
  was not documented.
- `revras` suggests useful geometry/raster correspondence, but original STL
  vertex/face preservation was not proven.

ToothInstance: `id` PARTIAL; `fdi` CANNOT BE SAFELY DERIVED; `jaw`
DERIVABLE; `mesh` PARTIAL; `centroid` DERIVABLE after trusted masks;
`landmarks` NOT AVAILABLE; `confidence` PARTIAL.

**Status:** reject pending a published checkpoint and legal review.

## THISNet Audit

**Repository:** <https://github.com/li-pengcheng/THISNet>  
**Commit:** `9fb881e78a24c52cb0d0cde1576369d142f53f85`  
**License:** none found.

- README describes tooth instance segmentation on 3D dental models.
- `test.py` expects local `ckpt_xx_xxxx.pth`; no downloadable checkpoint was
  found. It uses `torch.load`, CUDA tensors, `DataParallel`, and `.cuda()`.
- Environment is PyTorch 1.8.0 with CUDA 11.1. No CPU inference path is
  documented.
- Input is prepared PLY/face feature data; no direct STL command is documented.
- Output includes instance masks and PLY output, but no FDI mapping, landmark
  output, or stable original-face contract was verified.

ToothInstance: `id` AVAILABLE as mask slots; `fdi` NOT AVAILABLE; `jaw`
DERIVABLE from input; `mesh` PARTIAL; `centroid` DERIVABLE after masks;
`landmarks` NOT AVAILABLE; `confidence` PARTIAL.

**Status:** reject pending a real checkpoint and output-contract evidence.

## License and Weights Findings

- A repository license is not a checkpoint license. Apache-2.0 for TSegAgent or
  PMTSeg does not clear SAM3, model weights, VLM services, or training data.
- Public Google Drive links do not establish commercial rights. TGNet’s archive
  is author-linked but has no visible weight license in the repository.
- Teeth3DS/3DTeethSeg dataset terms must be reviewed independently. Dataset
  access, source code, and checkpoint rights are separate decisions.
- Candidates with missing or unresolved weights were not downloaded and were not
  run.

## Current-Machine Feasibility

Host observations:

- Python `3.12.3` is available.
- `nvidia-smi` fails because no NVIDIA driver can communicate.
- `nvcc` is not installed.
- No NVIDIA GPU is available to the current environment.

Consequences:

- TGNet, TSegAgent, PMTSeg, and THISNet are blocked by their CUDA/custom-kernel
  paths.
- OrthoGeo3D and the unified DGCNN baseline lack released checkpoints before
  hardware becomes relevant.
- No CPU substitute, architecture alteration, or local model replacement was
  attempted.

## Cloud-GPU Feasibility

- **TGNet:** technically plausible on a Linux CUDA VM with at least 11 GB VRAM,
  CUDA 11-era compatibility, custom pointops, and the linked checkpoint. A
  16–24 GB GPU is a prudent research target because the README documents batch
  size one and RTX40 issues.
- **TSegAgent:** technically plausible only with CUDA >=12.6, PyTorch >=2.7,
  SAM3 and rasterizer builds, SAM3 weights, and either a cleared VLM service or
  a validated local replacement. VRAM is undocumented; budget a modern
  24 GB+ GPU until measured.
- **PMTSeg:** requires a CUDA GPU plus PointNet2, `revras`, OpenGL/EGL, and
  checkpoint. Cloud execution is possible in principle but not justified
  without weights.
- **THISNet:** requires a CUDA 11.1-era environment and missing checkpoint.
- **OrthoGeo3D / DGCNN:** a cloud GPU could run a training-generated checkpoint,
  but that is outside this audit and not a pretrained benchmark.

## Candidates Worth Actual Benchmarking

Only **ToothGroupNetwork / TGNet** passes the documentation gate for a future
isolated benchmark: real 3D dental OBJ input, author-linked pretrained
inference, plausible instances and FDI JSON, and explicit upper/lower handling.
Before execution, retrieve the checkpoint and obtain written usage clearance.

**TSegAgent** remains a feasibility candidate, not an execution candidate,
until SAM3 weights/license, exact dependency compatibility, VLM/API policy,
and a local/no-cost FDI path are resolved.

No candidate was executed in this audit.

## Production Boundary

- Production segmentation architecture unchanged.
- FastAPI, React, treatment planning, export, existing adapters, and
  `model_unavailable` fail-closed behavior unchanged.
- No fixture or fake segmentation added.
- No checkpoint downloaded, inference run, or training run.

## Final Audit Counts

- Serious candidates remaining: **2** — TGNet and TSegAgent.
- Technically runnable on the current machine: **0**.
- Blocked by current hardware: **TGNet, TSegAgent, PMTSeg, THISNet**.
- Blocked by licensing/usage uncertainty: **TGNet, TSegAgent, PMTSeg, and all candidates with missing weight/data terms**.
- Blocked by missing checkpoints: **OrthoGeo3D, unified DGCNN baseline, PMTSeg, THISNet**.
- Proceed to actual benchmark: **TGNet only, after checkpoint and rights review**.

Machine-readable details are in
[research/benchmark/model-discovery.json](../research/benchmark/model-discovery.json).
