# Segmentation Model Audit

**Audit date:** 2026-09-20  
**Scope:** research only. No source, checkpoint, model artifact, dependency, or
runtime integration was downloaded or added.

## Decision Rule

A candidate must have documented permission for the intended commercial use and
an explicit license for its pretrained weights. Under the project rule, absent
weight terms are classified `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`; an MIT source
license does not establish rights to a checkpoint or its training data.

## Comparison

| Candidate                                                                                                 | Code License                                                          | Weights License                                                                            | Dataset License                                             | Commercial Use                                          | Weight Redistribution      | Input                                                                   | Output                                                       | Upper/Lower                                                      | ONNX                         | Technical Fit                                                                                 | Legal Risk                                 | Status                                                                         |
| --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------------------- | ------------------------------------------------------- | -------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------ |
| MeshSegNet                                                                                                | MIT, repository `LICENSE`                                             | `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`; repository does not publish separate checkpoint terms | Training data not provided; license not documented          | Source yes; checkpoint/data-derived use not established | Not explicitly established | VTP mesh in published workflow; 15 per-cell features; 6,000-cell sample | 15 class probabilities: gingiva plus 14 tooth classes        | Separate upper/lower trained models are stated                   | No official ONNX artifact    | Poor for current generic adapter: requires two adjacency tensors and fixed sampled cells      | High                                       | Rejected pending written checkpoint/data permission and verified ONNX contract |
| ToothGroupNetwork / TGNet                                                                                 | No `LICENSE` file at audited repository root                          | `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`; checkpoints are linked via Google Drive without terms | 3DTeethSeg'22 / Teeth3DS: CC BY-NC-ND 4.0                   | Not established; training dataset is non-commercial     | Not stated                 | Aligned upper/lower OBJ mesh; farthest-point sampling                   | Instance and FDI-label JSON compatible with challenge format | Yes, file naming and dataset include separate upper/lower arches | No official ONNX artifact    | Poor: PyTorch 1.7/CUDA custom point operations, batch size 1, stated minimum 11 GB GPU        | Critical                                   | Rejected                                                                       |
| 3DTeethSeg'22 reference algorithm and dataset                                                             | MIT for repository code                                               | No pretrained weights documented                                                           | CC BY-NC-ND 4.0                                             | Dataset use is not commercial                           | No weights documented      | Separate upper/lower OBJ meshes with per-vertex labels/instances        | Per-vertex FDI labels and tooth instances; 0 is gingiva      | Yes                                                              | No published ONNX checkpoint | Dataset/evaluation reference, not a deployable model package                                  | Critical for data-trained commercial model | Rejected as a model source; retain as evaluation reference only                |
| TSegNet / PointNet / PointNet++ / DGCNN / PointTransformer variants distributed through ToothGroupNetwork | Inherits unresolved ToothGroup repository/referenced dependency terms | `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`                                                        | Same CC BY-NC-ND 3DTeethSeg'22 source in published pipeline | Not established                                         | Not stated                 | Point-cloud samples derived from OBJ meshes                             | Challenge-format instances and labels                        | Yes through shared pipeline                                      | No official ONNX artifacts   | Point-cloud conversion may be feasible, but custom preprocessing/checkpoints are not verified | Critical                                   | Rejected                                                                       |

## Verified Technical Facts

### MeshSegNet

- The official repository describes a PyTorch mesh model for dental surface
  labeling and an MIT source license.
- Published training/inference preprocessing uses VTP meshes, per-cell
  geometry, centering and normalization. Features are nine cell-vertex values,
  three relative-position values, and three normal values.
- The architecture receives three tensors: features shaped like `(batch, 15,
cells)`, plus short- and long-range adjacency matrices. The repository example
  reports 6,000 cells for the model summary; the dataset implementation samples
  a fixed patch and computes adjacency from barycenter distances.
- The documented class count is 15: gingiva plus 14 teeth, second molar to
  second molar. The README does not state a formal FDI-output contract.
- The repository describes separate trained upper and lower models, prediction
  downsampling for meshes above 10,000 cells, and a GPU-memory warning.
- An ONNX conversion could be technically investigated only after a cleared
  artifact is supplied. It would need the feature and both adjacency inputs;
  the current AlignerStudio adapter intentionally rejects adjacency-dependent
  contracts.
- The repository has no release-published ONNX artifact or model-card-style
  checkpoint/license statement.

### ToothGroupNetwork / TGNet

- The official README identifies a challenge-winning point-cloud/mesh pipeline
  and links checkpoints through Google Drive, but the repository root has no
  `LICENSE` file and checkpoint terms are absent.
- It expects separately named `*_upper.obj` and `*_lower.obj` meshes with a
  prescribed axis orientation. Preprocessing uses farthest-point sampling.
- It supports TGNet, TSegNet, PointNet, PointNet++, DGCNN, and PointTransformer
  variants. TGNet requires FPS and boundary-aware stages; the published runtime
  depends on PyTorch, CUDA/C++ point operations, and states a minimum 11 GB GPU
  for its batch-size-one implementation.
- Outputs are challenge-format JSON. Challenge labels are FDI and instances
  identify teeth; gingiva is represented by zero in the challenge data.
- No ONNX export, CPU inference benchmark, fixed maximum point count, or
  independently licensed checkpoint is published in the official README.

### 3DTeethSeg'22 / Teeth3DS

- The official challenge repository is MIT for its non-data code. Its 1,800
  upper/lower intraoral scans and labels are CC BY-NC-ND 4.0.
- Labels are FDI; instances and labels are per vertex; zero is reserved for
  gingiva. This makes it technically useful for a non-production evaluation
  specification.
- The CC BY-NC-ND data terms prevent using that dataset as the basis for a
  commercially deployable training or checkpoint path without separate
  permission. The repository documents no weight artifact with separate terms.

## Sources

- MeshSegNet repository and README: <https://github.com/Tai-Hsien/MeshSegNet>
- MeshSegNet source license: <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/LICENSE>
- MeshSegNet architecture: <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/meshsegnet.py>
- MeshSegNet preprocessing: <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/Mesh_dataset.py>
- ToothGroupNetwork repository and README: <https://github.com/limhoyeon/ToothGroupNetwork>
- 3DTeethSeg challenge repository: <https://github.com/abenhamadou/3DTeethSeg_MICCAI_Challenges>
- 3DTeethSeg repository license: <https://raw.githubusercontent.com/abenhamadou/3DTeethSeg_MICCAI_Challenges/main/LICENSE>

This audit records repository documentation, not legal advice. Counsel and the
artifact rightsholder must confirm any future production use.
