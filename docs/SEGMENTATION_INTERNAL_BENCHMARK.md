# MeshSegNet Internal Segmentation Benchmark

> **INTERNAL RESEARCH ONLY**  
> **NOT CLINICALLY VALIDATED**  
> **NOT APPROVED FOR COMMERCIAL DEPLOYMENT**

**Run date:** 2026-09-20  
**Production impact:** none. The checkpoint, source checkout, isolated virtual
environment, and outputs are outside the repository under
`~/.cache/alignerstudio-research/meshsegnet`. Production API, adapter,
SegmentationEngine, dependencies, and fail-closed behavior were not changed.

## Selected Research Artifact

MeshSegNet was selected for this internal smoke test because the author-published
repository contains checkpoint archives and an STL prediction script.

- **Repository:** <https://github.com/Tai-Hsien/MeshSegNet>
- **Source commit:** `dca46b411dcabdbf4374f65e354522b54932b4f9`
- **Source license:** MIT
- **Checkpoint archive URL:**
  <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/models/MeshSegNet_Max_15_classes_72samples_lr1e-2_best.zip>
- **Artifact filename:** `MeshSegNet_Max_15_classes_72samples_lr1e-2_best.zip`
- **Artifact SHA-256:**
  `727cd3c52fc85c55271782b5d432d2cc8199ec2445cfb39570249e3ea99675d2`
- **Git object SHA reported by GitHub:** `a5fdd3e18944c6543176c5d7ed6e368d18db05fb`
- **Checkpoint license:** `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`
- **Weight handling:** author-published artifact downloaded only to the external
  research cache; not committed, redistributed, or exposed to AlignerStudio.

The authors' code is MIT, but no separate checkpoint or training-data license
was found. The artifact is therefore usable only for this controlled internal
engineering evaluation, not production or commercial deployment.

### Mandibular Research Artifact

- **Checkpoint archive URL:**
  <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/models/MeshSegNet_Man_15_classes_72samples_lr1e-2_best.zip>
- **Artifact filename:** `MeshSegNet_Man_15_classes_72samples_lr1e-2_best.zip`
- **Artifact SHA-256:**
  `d74c87e0c1cbc47fcedcc6f8574c1ad484dd2e21a98cabfb3465a42a2760a0cf`
- **Weight handling and license status:** identical to the maxillary artifact:
  external research cache only and `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`.

## Isolated Runtime

| Item                  | Value                                                |
| --------------------- | ---------------------------------------------------- |
| Python                | 3.12 research virtual environment outside repository |
| PyTorch               | `2.14.0+cpu`                                         |
| vedo                  | `2026.6.1`                                           |
| SciPy                 | `1.18.1`                                             |
| pandas                | `3.0.6`                                              |
| CUDA / GPU            | No usable NVIDIA GPU detected; CPU evaluation only   |
| GPU VRAM              | Not available / not measured                         |
| Production virtualenv | Not modified                                         |

The author repository lists a Linux environment with PyTorch `1.13.1`, CUDA
11.7 runtime packages, vedo, VTK, SciPy, and pygco. The evaluated CPU runtime
is a compatibility environment, not a reproduction of the authors' hardware.

## Input and Published Preprocessing

- **Input case:** `tests/fixtures/synthetic_segmentation_arch.obj`
- **Provenance:** existing PHI-free synthetic engineering fixture, not a dental
  scan and not a clinical test case.
- **Input geometry:** two disconnected tetrahedral regions, eight triangular
  cells total.
- **Accepted experimental formats:** STL, OBJ, or PLY as supported by vedo.
- **Published features:** 15 values per cell: three triangle vertices (9),
  normalized barycenter/relative position (3), and normalized cell normal (3).
- **Published graph inputs:** short- and long-range dense adjacency matrices
  derived from barycenter distances less than `0.1` and `0.2` in the normalized
  feature space.
- **Published size behavior:** meshes above 10,000 cells are decimated before
  inference. This alters original mesh correspondence and is unacceptable for
  production until an explicit projection contract is designed.

## Result

| Measure                                | Result                                                                                                                                                                                                               |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Inference success                      | Yes                                                                                                                                                                                                                  |
| Device                                 | CPU                                                                                                                                                                                                                  |
| Runtime                                | `0.11293185799968342` seconds end-to-end for 8 cells                                                                                                                                                                 |
| Label histogram                        | 6 cells label `0`, 2 cells label `7`                                                                                                                                                                                 |
| Detected connected non-gingiva regions | 1 region, label `7`, 2 cells                                                                                                                                                                                         |
| Export                                 | Labeled VTP plus JSON summary in external research cache                                                                                                                                                             |
| Visual inspection                      | Output VTP contains the published `Label` cell-data field. The synthetic mesh produced one tiny non-gingiva region; this is only a plumbing observation, not a quality result.                                       |
| FDI identity                           | Not available: MeshSegNet's 15 classes are gingiva plus 14 tooth classes, but the author repository does not publish a formal FDI mapping contract.                                                                  |
| `ToothInstance` conversion             | Not performed. Connected non-gingiva triangles can form an experimental mesh region, but class-to-FDI semantics, full-mesh correspondence after decimation, confidence semantics, and validity rules are incomplete. |

## Experimental Files

- **Runner:** `experimental/segmentation/run_meshsegnet_evaluation.py`
- **External source checkout:** `~/.cache/alignerstudio-research/meshsegnet/source`
- **External checkpoint:** `~/.cache/alignerstudio-research/meshsegnet/MeshSegNet_Max_15_classes_72samples_lr1e-2_best.zip`
- **External output VTP:**
  `~/.cache/alignerstudio-research/meshsegnet/results/synthetic_segmentation_arch_meshsegnet.vtp`
- **External output JSON:**
  `~/.cache/alignerstudio-research/meshsegnet/results/synthetic_segmentation_arch_meshsegnet.json`

## Output Semantics and Limits

The original architecture accepts a feature tensor and two adjacency tensors,
then returns 15-class per-cell probabilities. Label zero is treated as
gingiva/background by the author inference path. The repository describes
separate maxillary and mandibular archives, but does not publish a formal label-
to-FDI table.

This experiment deliberately does not infer FDI, generate a domain
`ToothInstance`, or feed a treatment plan. It also does not evaluate accuracy:
the PHI-free fixture has no dental ground truth and is structurally unlike an
intraoral scan.

## Production-Integration Estimate

Before any production work, obtain legal clearance for the checkpoint and
training data, or train an owned artifact on cleared data. Technical work would
then require a separate architecture review for:

1. versioned STL-to-15-feature preprocessing that matches the approved model;
2. dense adjacency memory limits and deterministic decimation/projection;
3. per-cell output mapping back to original mesh faces;
4. connected-component extraction and safe `ToothInstance` construction;
5. a documented FDI/class mapping or separate identification step;
6. confidence, error, and missing-tooth semantics; and
7. an adapter interface that accepts all three model inputs without weakening
   the current production gate.

No conclusion here supports clinical quality, safety, or commercial use.

## Real Upper/Lower Case Evaluation

An existing locally uploaded, anonymized upper/lower pair was evaluated only
inside the external research cache. It is not reproduced in this repository,
not shared, and not used by any production code. The scan identity is not
asserted in this document because the uploaded filenames are anonymized.

| Measure                               | Upper                        | Lower                        |
| ------------------------------------- | ---------------------------- | ---------------------------- |
| Author checkpoint                     | Maxillary archive            | Mandibular archive           |
| Input cells                           | 171,139                      | 139,083                      |
| Working cells after author decimation | 10,000                       | 10,000                       |
| Inference success                     | Yes                          | Yes                          |
| Device                                | CPU                          | CPU                          |
| End-to-end runtime                    | 19.61 seconds                | 14.17 seconds                |
| GPU VRAM                              | Not available / not measured | Not available / not measured |
| Published classes present             | 0 through 14                 | 0 through 14                 |
| Gingiva/background cells (class 0)    | 3,997                        | 4,230                        |
| Connected non-gingiva regions         | 33                           | 29                           |
| Projection back to original mesh      | No                           | No                           |
| FDI identity                          | Unavailable                  | Unavailable                  |
| `ToothInstance` conversion            | Not safe/validated           | Not safe/validated           |

### Class Distributions

```text
upper: 0=3997, 1=568, 2=760, 3=542, 4=368, 5=159, 6=238, 7=340,
       8=412, 9=268, 10=273, 11=388, 12=347, 13=683, 14=657
lower: 0=4230, 1=585, 2=761, 3=407, 4=313, 5=295, 6=248, 7=285,
       8=267, 9=257, 10=259, 11=335, 12=368, 13=788, 14=602
```

### Qualitative Visual Assessment

Colorized face-centroid PNGs were generated from the decimated meshes. Large
same-label regions visibly track portions of the dental arches, and the upper
and lower checkpoints both produce distinct non-gingiva structures. However,
both outputs contain small disconnected fragments, including one-face regions:

- upper: 33 connected non-gingiva regions for 14 non-gingiva classes;
- lower: 29 connected non-gingiva regions for 14 non-gingiva classes.

The outputs therefore do **not** visually establish one clean region per tooth.
They are unsuitable as direct `ToothInstance` objects without a separately
designed, validated projection and region-cleanup process. This is a qualitative
engineering observation only; it is not an accuracy or clinical assessment.

### Real-Case Artifacts Outside the Repository

For each arch, the external research cache contains:

- original high-resolution VTP mesh;
- labeled, decimated working VTP mesh;
- `meshsegnet_labels.png` colorized face-centroid visualization;
- `label-00.obj` through `label-14.obj` per-class meshes; and
- a JSON summary containing input/working cell counts, region counts, labels,
  runtime, checkpoint path, and projection status.

Artifacts are rooted at:

```text
~/.cache/alignerstudio-research/meshsegnet/real-case/upper/
~/.cache/alignerstudio-research/meshsegnet/real-case/lower/
```

The published decimation prevents direct correspondence to every original mesh
face. No projection was attempted, and no model output was passed to
AlignerStudio's domain, API, review, or treatment-planning layers.
