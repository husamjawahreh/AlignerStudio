# TSegAgent Feasibility Gate

**Research-only feasibility audit. No inference, training, API call, CUDA
installation, or production change was performed.**

Canonical inputs were not modified or converted:

- `data/benchmark/real-case/upper.stl`
  - SHA-256: `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48`
- `data/benchmark/real-case/lower.stl`
  - SHA-256: `dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b`

## TSEGAGENT_COMMIT

`5dea4d347966121a7cdbb18e7a08009af1a2d310`

The exact checkout is external:
`~/.cache/alignerstudio-research/model-discovery/TSegAgent`.
Its SAM3 submodule gitlink pins:
`2ec3c0711a9719ac324388adc662e471f8fe2168`.

## Input and Preprocessing

The documented input is a Teeth3DS-style directory containing:

```text
teeth3ds-dataset-root/
  Teeth3DS_train_test_split/
    testing-upper.txt
    testing-lower.txt
  obj/<case>/
    <case>_upper.obj
    <case>_lower.obj
```

The single-file API is:

```python
predictor.predict("/path/to/model/file")
predictor.visualize("/path/to/visualize/file")
predictor.export_json("/path/to/predicted/json")
```

The implementation uses `trimesh.load(model_path, process=False)`. It does not
document direct STL support, and no STL conversion was performed.

Preprocessing and geometry path:

1. Load mesh vertices, faces, and vertex normals without trimesh processing.
2. Compute curvature and use it for vertex coloring.
3. `MeshRenderer` translates by the bounding-box centroid and scales by the
   maximum radial distance.
4. Render 19 fixed orthographic views at 1280 x 800.
5. Prompt SAM3 with the text `tooth`.
6. Use reversible-rasterizer face IDs to project image masks to mesh faces.
7. Merge multi-view regions, remove disconnected parts, fill small gaps, and
   reorder positive face IDs by arch geometry.
8. Derive vertex labels by majority vote over incident positive faces.

No dental upper/lower axis convention is implemented in the single-file
predictor. Upper/lower handling is supplied by Teeth3DS filenames and the VLM
prompt.

## Dependency Audit

### TSegAgent

From the exact commit’s `requirements.txt`:

| Dependency | Version |
| --- | --- |
| Python | `>=3.12` |
| PyTorch | `2.9.1+cu130` |
| torchvision | `0.24.1+cu130` |
| CUDA | README requires `>=12.6`; wheel pins are cu130 |
| trimesh | `4.10.0` |
| vedo | `2025.5.4` |
| einops | `0.8.1` |
| decord | `0.6.0` |
| openai | `2.9.0` |
| fast-simplification | `0.1.13` |
| transformers | `>=5.0.0rc0` |
| accelerate / peft / datasets / pillow | unpinned |

### SAM3

SAM3 is not version-pinned as a package by TSegAgent; the submodule commit is
pinned to `2ec3c0711a9719ac324388adc662e471f8fe2168`.

The pinned SAM3 README states:

- Python 3.12;
- PyTorch 2.7 or higher;
- CUDA 12.6 or higher;
- example installation `torch==2.7.0` with cu126;
- C++17;
- optional `einops`, `ninja`, `flash-attn-3`, and `cc_torch`.

This is not an exact dependency match with TSegAgent’s `torch==2.9.1+cu130`
and `torchvision==0.24.1+cu130`; compatibility requires an isolated build.

### Reversible rasterizer

The bundled rasterizer is version `0.1.0`, Apache-2.0, and requires:

- CMake >=3.27;
- C++17;
- OpenGL and OpenGL EGL development libraries;
- pybind11 2.13.6 fetched by CMake;
- Eigen 3.4.0 fetched by CMake;
- vendored Assimp and GLAD;
- Python packages `numpy>=1.21` and `scikit-learn>=1.0`.

No rasterizer build was attempted.

### VLM/API

FDI classification uses `openai==2.9.0` and either:

- `OPENAI_API_KEY` with OpenAI’s API; or
- `ARK_API_KEY` with the ARK/Doubao endpoint.

Documented models are `gpt-5.2` / `chatgpt-5.2` and
`doubao-seed-1-8-251228`. No key was read, no request was made, and no paid API
was used.

## SAM3_STATUS

**PINNED_SOURCE_COMMIT_AVAILABLE; MANUAL_GATED_WEIGHTS_REQUIRED**

SAM3 source is publicly visible at:
<https://github.com/facebookresearch/sam3>

The exact submodule commit is available. Its source uses the SAM License,
updated November 19, 2025.

## SAM3_WEIGHTS_STATUS

SAM3 weights are hosted at:
<https://huggingface.co/facebook/sam3>

The repository metadata marks the model as manually gated. The official README
requires requesting access and authenticating before downloading checkpoints.
The metadata exposes filenames including `sam3.pt` and `model.safetensors`, but
not file sizes or SHA-256 values without authenticated access.

Therefore:

- exact source URL: available;
- filename: metadata exposes `sam3.pt` and `model.safetensors`;
- size: unavailable without gated access;
- SHA-256: unavailable without gated access;
- downloaded: no;
- legally usable for this benchmark: not yet established because access
  approval and acceptance of the SAM License are prerequisites.

The SAM License grants a non-exclusive, worldwide, non-transferable,
royalty-free limited license and permits use, reproduction, modification, and
distribution subject to the agreement. Redistribution must remain under the
agreement, research publications must acknowledge SAM, and the materials and
outputs are provided without warranty. This is not treated as commercial
clearance for AlignerStudio.

## VLM and FDI Gate

### VLM-free segmentation

**Yes, as a code path.** `Predictor(use_gpt=False)` and
`test_teeth3ds.py --disable-gpt` skip `_generate_fdi_predict_images`, so SAM3
segmentation and face/vertex postprocessing can run without an external VLM.

### FDI

**VLM required.** The FDI classifier uploads rendered images to the configured
OpenAI or ARK client and requests JSON containing `id`, `fdi`, `type`,
`bad_id`, and `jaw`. The local code then applies `fdi_optimize` to map the
classification back to face labels.

Without the VLM, output remains geometry-generated instance IDs and does not
contain FDI labels. No local replacement is documented or validated.

## Output Contract

Without VLM, JSON has the structure:

```json
{
  "labels": [0, 1, 1],
  "debug_info": {"face_coverage": 0.0},
  "face_id": [],
  "gpt_output": null
}
```

The implementation also retains internal `vertices`, `faces`, and
`face_labels` arrays before export.

- `face_labels`: positive integer regions generated from multi-view SAM3 masks;
  zero is unlabeled/background.
- `labels`: per-vertex majority vote of incident positive face labels.
- With VLM, `face_id` retains pre-FDI region IDs and `gpt_output` contains the
  VLM response.
- SAM3 mask scores are captured per rendered view but are not aggregated into
  or exported as per-tooth confidence.
- No landmark head or landmark output exists.

## ORIGINAL_MESH_MAPPING

**PARTIAL.** The reversible rasterizer returns a pixel-to-face ID map whose IDs
refer to the original face array passed to the renderer. This preserves face
index identity through projection. The output vertex labels are then derived
from the original face topology by incident-face majority voting.

Important limitations:

- `MeshRenderer.set_mesh` mutates the mesh coordinates by centering and
  normalizing them. Index identity is retained, but exported geometry is not
  in original clinical coordinates.
- Uncovered faces remain zero.
- Mixed-label faces are reduced to vertex majority labels.
- The output JSON contains labels, not a standalone mesh for each instance.
- A deterministic mesh reconstruction is possible only by retaining the source
  topology and explicitly handling unlabeled/mixed faces.

No source-to-canonical-OBJ mapping was created because the gate prohibits
conversion at this stage.

## ToothInstance Field Assessment

| Field | Status |
| --- | --- |
| `id` | AVAILABLE as research face/vertex region IDs |
| `fdi` | AVAILABLE only with the external VLM; unavailable in segmentation-only mode |
| `jaw` | DERIVABLE from upper/lower input context, not a stable no-VLM output field |
| `mesh` | DERIVABLE with retained source topology, but requires handling normalization, uncovered faces, and mixed labels |
| `centroid` | DERIVABLE from trusted regions |
| `landmarks` | NOT AVAILABLE |
| `confidence` | CANNOT BE SAFELY DERIVED as a per-tooth field |

## Rights Audit

| Material | Finding |
| --- | --- |
| TSegAgent source | Apache-2.0 |
| SAM3 source | SAM License, not Apache/MIT |
| SAM3 weights | Same SAM License terms, manually gated; no unauthenticated download or hash |
| VLM/API | OpenAI and ARK/Doubao service terms; no API call made |
| Dataset/training data | README points to Teeth3DS via OSF; separate dataset terms apply; related challenge terms identify data as CC BY-NC-ND 4.0 |
| TSegAgent checkpoint | None; only SAM3 weights are required |

**LEGAL_STATUS:** `RESEARCH_ONLY`

This does not establish commercial permission or clinical validity.

## Hardware and Cloud Plan

### CURRENT_MACHINE_STATUS

**BLOCKED.** The current machine has no NVIDIA driver, no NVIDIA GPU, and no
`nvcc`. SAM3 and the reversible rasterizer cannot be reproduced here.

### CLOUD_GPU_FEASIBILITY

**UNKNOWN**, not because the software path is conceptually impossible, but
because SAM3 VRAM requirements are not published and the gated checkpoint is
not available for a measured run.

A reproducible cloud plan, after access approval, would be:

1. Use a disposable Linux GPU VM with a modern NVIDIA GPU and CUDA >=12.6.
2. Prefer a 24 GB-class GPU as the first test target. 24 GB is a planning
   target, not a verified sufficiency claim.
3. Create Python 3.12 environment.
4. Install TSegAgent requirements in that environment only.
5. Install the exact SAM3 submodule commit and build `reversible_rasterizer`
   with CMake >=3.27, OpenGL/EGL, C++17, and pybind11/Eigen fetches.
6. Authenticate to Hugging Face only after access approval and record the
   checkpoint filename, size, and SHA-256 in the research artifact.
7. Run `--disable-gpt` first on a noncanonical smoke mesh to validate pure
   segmentation and export.
8. Convert canonical STL files to external OBJ working copies only after the
   smoke path works, preserving vertex/face correspondence and recording the
   conversion tool/version.
9. Run upper and lower separately with `use_gpt=False`; do not claim FDI.
10. Treat any future VLM/FDI experiment as a separately authorized, non-paid or
    explicitly approved step.

Disk: exact SAM3 checkpoint size is unavailable while gated. Reserve at least
30 GB free for the environment, source/build trees, gated weights, caches, and
rendered intermediates; this is an unverified planning reserve. RTX 40/50
compatibility is not documented by TSegAgent; use a current CUDA-compatible GPU
but treat architecture compatibility as an open gate.

## BENCHMARK_READY

**NO.** The segmentation-only code path is documented, but SAM3 checkpoint
access, exact dependency compatibility, VRAM sufficiency, and STL-to-OBJ
correspondence remain unverified.

## Final Feasibility Report

TSAGENT_COMMIT
`5dea4d347966121a7cdbb18e7a08009af1a2d310`

SOURCE_LICENSE
`Apache-2.0`

SAM3_STATUS
`PINNED_SOURCE_COMMIT_AVAILABLE; MANUAL_GATED_WEIGHTS_REQUIRED`

SAM3_WEIGHTS_STATUS
`NOT_PUBLICLY_OBTAINABLE_WITHOUT_MANUAL_ACCESS_APPROVAL; SIZE_AND_SHA256_UNAVAILABLE`

VLM_REQUIRED_FOR_FDI
`YES`

CHECKPOINT_STATUS
`TSegAgent_OWN_CHECKPOINT_NONE; SAM3_CHECKPOINT_GATED`

INPUT_COMPATIBILITY
`PARTIAL; DOCUMENTED_TEETH3DS_OBJ_LAYOUT, RAW_STL_NOT_VERIFIED`

ORIGINAL_MESH_MAPPING
`PARTIAL`

LANDMARKS
`NOT_AVAILABLE`

CONFIDENCE
`NOT_AVAILABLE_AS_PER_TOOTH_FIELD`

GPU_REQUIREMENT
`CUDA >=12.6 GPU; VRAM MINIMUM UNPUBLISHED`

CURRENT_MACHINE_STATUS
`BLOCKED`

CLOUD_GPU_FEASIBILITY
`UNKNOWN`

LEGAL_STATUS
`RESEARCH_ONLY`

BENCHMARK_READY
`NO`

RECOMMENDATION
`STOP_PENDING_SAM3_ACCESS_AND_RIGHTS_REVIEW`

Machine-readable record:
[research/benchmark/tsagent/feasibility.json](../research/benchmark/tsagent/feasibility.json)
