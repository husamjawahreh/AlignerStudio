# Segmentation Model Options

**Research date:** 2026-09-20  
**Scope:** second-pass research only. No checkpoint, dataset, dependency, or
application change was downloaded or added.

## Reading This Assessment

`CLEAR` means public materials establish the relevant code right only, or all
rights needed for the stated artifact are public. It does **not** make a general
3D model tooth-capable. `NEEDS_PERMISSION` means an obtainable commercial path
may exist but public terms are insufficient. `NOT_CLEAR` means a missing model,
weight, or data right blocks use. `REJECTED` means the candidate conflicts with
known non-commercial terms or is not a usable tooth-segmentation artifact.

No candidate below is approved for production deployment. A model may proceed
only after legal review verifies the final artifact, its training-data lineage,
and a deployment agreement.

## Options

### PointNet++ (yanx27 PyTorch implementation)

- **Name:** PointNet / PointNet++ PyTorch implementation
- **URL:** <https://github.com/yanx27/Pointnet_Pointnet2_pytorch>
- **Type:** trainable architecture
- **Code license:** MIT.
- **Weight/model license:** Repository includes non-dental example weights; no
  dental checkpoint or explicit dental-weight license exists.
- **Dataset license/provenance:** Non-dental ModelNet/ShapeNet/S3DIS examples;
  no intraoral training data is supplied.
- **Commercial use:** Code is commercially usable under MIT. A dental model
  requires independently cleared training data and model ownership.
- **Redistribution/deployment:** MIT code may be redistributed with notices;
  trained dental artifact rights depend on its data and contracts.
- **Input:** sampled point cloud, optional normals; STL must be converted to a
  deterministic point representation.
- **Output:** task-configured semantic or part labels; no dental/FDI defaults.
- **Upper/lower:** no dental concept; train/serve arch-specific or arch-aware
  configuration explicitly.
- **FDI support:** none; requires dental labels and an output mapping.
- **Instance segmentation:** not built in; requires an instance head or a
  deterministic post-processing design.
- **Local inference:** yes after training; CPU mode is documented, practical
  runtime must be benchmarked on target mesh sizes.
- **GPU/CPU:** PyTorch; CUDA documented for development; CPU option documented.
- **ONNX/TensorRT/PyTorch:** PyTorch provided; ONNX/TensorRT export is not an
  official dental contract and requires validation.
- **Model/checkpoint availability:** only non-dental example models.
- **Maintenance/activity:** public repository, latest visible update 2021.
- **Evidence:** general point-cloud segmentation, not intraoral scan evidence.
- **Legal status:** NEEDS_PERMISSION for a dental product because cleared
  dental data is required.
- **Technical status:** TRAINING_REQUIRED.
- **Recommended next action:** use only after procuring a commercial/consented
  intraoral dataset and defining instance/FDI output labels.

### DGCNN (official implementation)

- **Name:** Dynamic Graph CNN
- **URL:** <https://github.com/WangYueFt/dgcnn>
- **Type:** trainable architecture
- **Code license:** MIT.
- **Weight/model license:** no dental pretrained checkpoint is published.
- **Dataset license/provenance:** repository demonstrations are non-dental.
- **Commercial use:** MIT code is usable; a new dental model needs cleared data.
- **Redistribution/deployment:** code is redistributable under MIT; artifact
  rights depend on the future data/license chain.
- **Input:** point cloud with dynamic k-nearest-neighbor graph construction.
- **Output:** task-configured semantic/part labels; no FDI default.
- **Upper/lower:** no dental handling.
- **FDI support:** none.
- **Instance segmentation:** no tooth-specific instance head; needs a designed
  instance path.
- **Local inference:** yes after training.
- **GPU/CPU:** PyTorch/TensorFlow implementations; GPU is practical for
  training, deployment benchmark required.
- **ONNX/TensorRT/PyTorch:** PyTorch/TensorFlow provided; dynamic graph/export
  compatibility needs a technical spike.
- **Model/checkpoint availability:** general-task code only.
- **Maintenance/activity:** visible repository update approximately 2021.
- **Evidence:** general point-cloud segmentation, not intraoral scans.
- **Legal status:** NEEDS_PERMISSION for a dental product because cleared
  training data is required.
- **Technical status:** TRAINING_REQUIRED.
- **Recommended next action:** lower-priority architecture baseline only after
  lawful data procurement.

### MeshCNN

- **Name:** MeshCNN
- **URL:** <https://github.com/ranahanocka/MeshCNN>
- **Type:** trainable mesh architecture
- **Code license:** MIT.
- **Weight/model license:** example weights are for non-dental tasks; no dental
  checkpoint is published.
- **Dataset license/provenance:** example human/shape datasets; no intraoral
  data is supplied.
- **Commercial use:** source can be used under MIT; dental model requires
  separately cleared data and rights.
- **Redistribution/deployment:** code under MIT; future model artifact depends
  on data and contract terms.
- **Input:** triangular mesh with mesh-edge topology; STL can be converted but
  topology/normalization requirements must be fixed and validated.
- **Output:** mesh-edge segmentation labels; no FDI or tooth instances.
- **Upper/lower:** no dental support.
- **FDI support:** none.
- **Instance segmentation:** not tooth-specific; needs output/post-processing
  work.
- **Local inference:** yes after training.
- **GPU/CPU:** legacy PyTorch environment is documented; deployment benchmark
  required.
- **ONNX/TensorRT/PyTorch:** PyTorch only in official materials; mesh pooling
  makes standard ONNX export uncertain.
- **Model/checkpoint availability:** non-dental examples only.
- **Maintenance/activity:** visible repository update approximately 2021.
- **Evidence:** general triangular-mesh segmentation, not intraoral scans.
- **Legal status:** NEEDS_PERMISSION for a dental product because cleared
  training data is required.
- **Technical status:** TRAINING_REQUIRED.
- **Recommended next action:** consider only if mesh-native representation is
  preferred after a lawful dental dataset is acquired.

### Point Transformer V3 / Pointcept

- **Name:** Point Transformer V3 / Pointcept
- **URL:** <https://github.com/Pointcept/PointTransformerV3> and
  <https://github.com/Pointcept/Pointcept>
- **Type:** trainable architecture/framework
- **Code license:** MIT.
- **Weight/model license:** released weights target non-dental scene datasets;
  README states some released PTv3 weights are temporarily invalid after model
  changes. No dental checkpoint is published.
- **Dataset license/provenance:** supported benchmarks are non-dental and have
  their own terms; no cleared intraoral dataset is provided.
- **Commercial use:** source code license permits use, subject to included
  third-party components; dental artifact needs separate lawful data.
- **Redistribution/deployment:** future artifact rights depend on its data and
  all dependency licenses.
- **Input:** sparse/voxelized point clouds with coordinates and optional
  features; STL requires sampling/conversion.
- **Output:** configurable semantic/instance outputs; no dental classes/FDI.
- **Upper/lower:** no dental handling.
- **FDI support:** none.
- **Instance segmentation:** framework includes generic PointGroup support,
  not tooth-specific semantics.
- **Local inference:** yes, but not on the current lightweight API runtime.
- **GPU/CPU:** CUDA/PyTorch/custom CUDA operations are central; documented
  configurations use multi-GPU training.
- **ONNX/TensorRT/PyTorch:** PyTorch/CUDA framework; no official ONNX/TensorRT
  deployment contract.
- **Model/checkpoint availability:** non-dental experiment records/weights;
  no dental artifact.
- **Maintenance/activity:** active, visible repository activity in 2026.
- **Evidence:** strong general 3D research framework, no intraoral evidence.
- **Legal status:** NEEDS_PERMISSION for dental data; code license alone is not
  enough.
- **Technical status:** TRAINING_REQUIRED.
- **Recommended next action:** use only as a future GPU training research stack,
  not as the production inference dependency.

### exocad DentalCAD / exocad ART

- **Name:** exocad DentalCAD / ART
- **URL:** <https://www.exocad.com/our-products/dentalcad/>
- **Type:** commercial dental software/vendor path
- **Code license:** proprietary commercial product; public page describes
  commercial licensing, not source rights.
- **Weight/model license:** not publicly documented.
- **Dataset license/provenance:** not publicly documented.
- **Commercial use:** a commercial product license exists, but public material
  does not grant embedding a tooth-segmentation model in AlignerStudio.
- **Redistribution/deployment:** not publicly documented.
- **Input:** public product information states compatibility with intraoral
  scan data; a programmatic segmentation input contract is not public.
- **Output:** no public tooth-instance/FDI API contract.
- **Upper/lower:** not publicly documented as a segmentation API contract.
- **FDI support:** not publicly documented.
- **Instance segmentation:** not publicly documented.
- **Local inference:** not publicly documented.
- **GPU/CPU:** not publicly documented.
- **ONNX/TensorRT/PyTorch:** not publicly documented.
- **Model/checkpoint availability:** none publicly offered for embedding.
- **Maintenance/activity:** active commercial product.
- **Evidence:** commercial CAD product page; no public segmentation SDK/API.
- **Legal status:** NEEDS_PERMISSION.
- **Technical status:** INCOMPATIBLE until vendor supplies an SDK/API contract.
- **Recommended next action:** submit a vendor business-development inquiry for
  an OEM/API license that expressly grants tooth instance/label outputs.

### Medit Link / Medit Open Integration

- **Name:** Medit Link
- **URL:** <https://www.medit.com/medit-link/>
- **Type:** commercial platform/vendor path
- **Code license:** proprietary service/product.
- **Weight/model license:** not publicly documented.
- **Dataset license/provenance:** not publicly documented.
- **Commercial use:** Medit markets integrations and 3D data sharing, but public
  material does not grant use of a segmentation model inside another product.
- **Redistribution/deployment:** not publicly documented.
- **Input:** 3D dental data sharing is described; no public segmentation API
  input specification.
- **Output:** no public FDI/instance segmentation API contract.
- **Upper/lower:** not publicly documented.
- **FDI support:** not publicly documented.
- **Instance segmentation:** not publicly documented.
- **Local inference:** not publicly documented.
- **GPU/CPU:** not publicly documented.
- **ONNX/TensorRT/PyTorch:** not publicly documented.
- **Model/checkpoint availability:** none publicly documented for embedding.
- **Maintenance/activity:** active commercial platform.
- **Evidence:** official page describes open integration and 3D data sharing,
  not an inference SDK.
- **Legal status:** NEEDS_PERMISSION.
- **Technical status:** INCOMPATIBLE until vendor supplies an API/SDK contract.
- **Recommended next action:** request current OEM/API documentation and a
  commercial deployment agreement; do not infer capabilities from marketing.

### TSegFormer

- **Name:** TSegFormer: 3D Tooth Segmentation in Intraoral Scans with Geometry
  Guided Transformer
- **URL:** <https://github.com/huiminxiong/TSegFormer>
- **Type:** trainable tooth-segmentation architecture.
- **Code license:** MIT; architecture source is publicly available.
- **Weight/model license:** `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`. The repository
  documents a `best_model.t7` produced by training but does not publish a
  checkpoint artifact, model-card terms, or pretrained-weight license.
- **Dataset license/provenance:** the README says only "IOS dataset"; it does
  not identify its source, rights, or commercial terms.
- **Commercial training rights:** not established for the authors' dataset.
  Training a new model on independently procured commercial/consented data is
  legally separable and technically possible under the MIT source terms.
- **Commercial deployment rights:** MIT source permits commercial code reuse;
  an owned artifact requires a complete lawful data/provenance chain.
- **Checkpoint redistribution rights:** not established; no released
  checkpoint is audited.
- **Architecture reuse rights:** MIT, subject to retaining required notices.
- **Input:** preprocessed JSON containing an 8-value point feature and a
  two-value jaw category. The source samples exactly 10,000 points without
  replacement; it does not accept raw STL directly.
- **Output:** 33-class point labels plus a binary gingiva head. Source labels
  use zero for gingiva and jaw-conditioned tooth label groups.
- **Segmentation type:** per-point semantic tooth/gingiva segmentation with a
  geometry-guided curvature loss; output can be grouped into tooth instances
  only after a deterministic point-to-mesh projection/grouping design.
- **Tooth identification / FDI mapping:** source encodes a two-category jaw
  input and offsets positive predictions by 16 for one jaw. This suggests
  jaw-specific permanent-tooth labels, but formal FDI label semantics are not
  documented in the audited README/source; they must be validated against a
  cleared label specification before use.
- **Upper/lower:** explicit two-value jaw category; upper/lower are handled by
  the category input, not separate model files.
- **Missing-tooth handling:** no explicit missing-tooth policy is published.
  A class absent from per-point output may represent absence, but this must not
  be treated as a clinical or identification rule without validation.
- **Inference requirements:** PyTorch 1.9/CUDA 11.1 documented; training/test
  code hard-codes CUDA/DataParallel paths. Inference source conditionally picks
  CPU/GPU but requires a refactor and benchmark before CPU support is claimed.
- **GPU/CPU:** GPU-oriented; two CUDA device IDs are hard-coded in train/test.
- **ONNX/TensorRT/PyTorch:** PyTorch only. ONNX is technically plausible after
  a controlled export spike, but requires two inputs, fixed-point sampling,
  custom preprocessing, and output equivalence tests; no official ONNX or
  TensorRT artifact exists.
- **Preprocessing:** externally generated aligned JSON, 8 point features,
  random 10,000-point sampling, curvature feature, and jaw category. The
  repository does not include an STL-to-JSON preprocessing contract.
- **Number of points/faces:** 10,000 sampled points; face topology is not an
  model input.
- **STL adaptation:** realistic through deterministic STL mesh sampling and
  feature generation, but that conversion and point-to-original-face mapping
  must be designed/tested; it is not supplied.
- **Maintenance/activity:** public repository's visible latest commit is from
  approximately 2023.
- **Source/weights availability:** source available; no released, licensed
  pretrained checkpoint found.
- **Evidence:** official repository, MIT `LICENSE`, and MICCAI 2023 project
  description. Reported research results are not commercial validation.
- **Legal status:** NOT_CLEAR for pretrained use; CLEAR for architecture reuse
  with independent lawful data.
- **Technical status:** TRAINING_REQUIRED and ADAPTER_REQUIRED.
- **Recommended next action:** leading architecture candidate for PATH B only
  after lawful training data and a written FDI/instance label protocol exist.

### TSegLab

- **Name:** TSegLab: Multi-stage 3D dental scan segmentation and labeling
- **URL:** <https://crns-smartvision.github.io/tseglab> and
  <https://doi.org/10.1016/j.compbiomed.2024.109535>
- **Type:** research method and hosted demonstration; a public reusable model
  package was not found.
- **Code license:** no public model source repository or source-code license
  was found in the audited project/publication materials.
- **Weight/model license:** `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`; no public
  checkpoint or terms were found.
- **Dataset license/provenance:** project states evaluation on Teeth3DS, whose
  public data terms are CC BY-NC-ND 4.0.
- **Commercial training rights:** not established; the disclosed benchmark is
  non-commercial.
- **Commercial deployment rights:** not established. The project links a demo
  login, not an SDK/API license.
- **Checkpoint redistribution rights:** not established.
- **Architecture reuse rights:** NEEDS_PERMISSION because implementation source
  is unavailable; paper concepts alone do not grant source/artifact rights.
- **Input:** public method description renders a three-channel 2D scan
  representation for Mask R-CNN candidate detection, then uses harmonic
  parameter-space segmentation. Exact STL/OBJ preprocessing contract is not
  public.
- **Output:** visible-tooth localization, crown segmentation, and GNN labeling
  stages. Project claims 3D tooth labeling but publishes no machine-readable
  output schema.
- **Segmentation type:** multi-stage detection, instance/crown segmentation,
  and graph-based labeling.
- **Tooth identification / FDI mapping:** intended labeling is described and
  Teeth3DS labels are FDI; exact public output mapping cannot be verified.
- **Upper/lower / missing teeth:** Teeth3DS has separate arches, but the public
  project materials do not document production arch or missing-tooth behavior.
- **Inference requirements / GPU/CPU / ONNX/TensorRT/PyTorch:** not public.
- **Preprocessing / number of points/faces / STL adaptation:** not public.
- **Maintenance/activity:** project page and 2025 journal publication exist;
  no source release cadence is available.
- **Source/weights availability:** no public source or checkpoint identified.
- **Evidence:** official project page describes Mask R-CNN, harmonic
  segmentation, and GNN stages; publication copyright record is not a software
  deployment grant.
- **Legal status:** NEEDS_PERMISSION.
- **Technical status:** INCOMPATIBLE until a licensed SDK/source/artifact and
  complete contract are supplied.
- **Recommended next action:** contact the project/rightsholder only for a
  written commercial SDK/API or artifact license; do not implement from the
  publication alone.

### TeethNet

- **Name:** TeethNet: Dual-Stream Attention Network for 3D Tooth Segmentation
- **URL:** <https://doi.org/10.1145/3747227.3747252>
- **Type:** research paper.
- **Code license:** no public source repository or code license found in the
  DOI metadata and public GitHub repository search performed for this audit.
- **Weight/model license:** `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`; no public
  checkpoint artifact or terms found.
- **Dataset license/provenance:** not disclosed in the audited Crossref
  metadata. It must be obtained directly from the authors/rightsholder.
- **Commercial training rights / deployment rights / checkpoint redistribution:**
  not established.
- **Architecture reuse rights:** NEEDS_PERMISSION for implementation artifacts;
  an independent clean-room implementation of paper concepts would still need
  lawful training data and a separate architecture/IP review.
- **Input / output / segmentation type / FDI / upper-lower / missing teeth:**
  the title establishes 3D tooth segmentation and dual-stream attention, but
  the audited public metadata does not establish a reproducible contract for
  these fields. Do not infer them from the title.
- **Inference requirements / GPU/CPU / ONNX/TensorRT/PyTorch / preprocessing /
  point or face count / STL adaptation:** not publicly specified in audited
  materials.
- **Maintenance/activity:** publication record only; no project maintenance
  signal or public implementation found.
- **Source/weights availability:** no public source or weight artifact found.
- **Evidence:** ACM proceedings metadata via Crossref, published 2025.
- **Legal status:** NOT_CLEAR.
- **Technical status:** INCOMPATIBLE until authors provide a licensed,
  reproducible artifact or implementation contract.
- **Recommended next action:** request source, artifact, data provenance,
  commercial deployment terms, and a complete I/O contract from the authors;
  otherwise retain as literature only.

## Commercially Usable Data Finding

This pass found no public intraoral tooth-instance/FDI dataset with clearly
commercial training rights. The prior Teeth3DS/3DTeethSeg'22 dataset remains CC
BY-NC-ND 4.0 and is excluded. The realistic training-data source is a newly
procured dataset under a written agreement covering collection, annotation,
model training, artifact ownership, internal deployment, redistribution if
needed, and retention/deletion obligations.

## Sources

- PointNet++: <https://github.com/yanx27/Pointnet_Pointnet2_pytorch>
- DGCNN: <https://github.com/WangYueFt/dgcnn>
- MeshCNN: <https://github.com/ranahanocka/MeshCNN>
- Point Transformer V3: <https://github.com/Pointcept/PointTransformerV3>
- Pointcept: <https://github.com/Pointcept/Pointcept>
- exocad DentalCAD: <https://www.exocad.com/our-products/dentalcad/>
- Medit Link: <https://www.medit.com/medit-link/>
- TSegFormer: <https://github.com/huiminxiong/TSegFormer>
- TSegLab: <https://crns-smartvision.github.io/tseglab>
- TSegLab publication: <https://doi.org/10.1016/j.compbiomed.2024.109535>
- TeethNet metadata: <https://doi.org/10.1145/3747227.3747252>
- 3DTeethSeg licensing context: <https://github.com/abenhamadou/3DTeethSeg_MICCAI_Challenges>

This is a technical research record, not legal advice. Final licensing must be
confirmed by counsel and the relevant rightsholder before acquisition or coding.
