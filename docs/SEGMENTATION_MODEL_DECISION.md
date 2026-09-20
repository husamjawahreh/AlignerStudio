# Segmentation Model Decision

**Decision date:** 2026-09-20  
**Decision:** No investigated pretrained segmentation model is approved for
integration.

## 1. Candidates Investigated

1. MeshSegNet: mesh-based dental surface labeling model.
2. ToothGroupNetwork / TGNet: point-cloud/mesh challenge-winning pipeline.
3. 3DTeethSeg'22 reference algorithm and Teeth3DS dataset materials.
4. TSegNet, PointNet, PointNet++, DGCNN, and PointTransformer variants exposed
   by the ToothGroupNetwork training/inference repository.

See [SEGMENTATION_MODEL_AUDIT.md](SEGMENTATION_MODEL_AUDIT.md) for source
links and the full comparison.

## 2. Candidates Rejected

### MeshSegNet

Rejected for a production integration now because pretrained-weight rights are
not explicitly published. The MIT source license does not establish rights to
pretrained weights or to the undisclosed training data. It is also not a drop-in
ONNX fit: published inference needs fixed sampled cells and short/long adjacency
matrices in addition to 15 mesh features.

### ToothGroupNetwork / TGNet

Rejected because the audited repository has no root source-code license, the
Google Drive checkpoints have no explicit license or redistribution terms, and
the disclosed 3DTeethSeg'22 training dataset is CC BY-NC-ND 4.0. Its published
PyTorch/CUDA custom-operator inference path is also unsuitable for the current
CPU-oriented ONNX Runtime boundary without a separately verified export.

### 3DTeethSeg'22 Reference Algorithm / Teeth3DS

Rejected as a model source for commercial production because the dataset is CC
BY-NC-ND 4.0 and no separately licensed pretrained artifact is documented. It
remains useful as an evaluation-format reference because it defines separate
upper/lower scans, FDI labels, tooth instances, and gingiva label zero.

### ToothGroupNetwork-Distributed Baselines

Rejected for the same unresolved checkpoint rights and non-commercial dataset
lineage. Their model-specific dependencies and preprocessing do not change the
legal result.

## 3. Technically Viable Candidates

No candidate is technically viable for immediate integration.

MeshSegNet is a possible future technical candidate only after its model
contract is reproduced from a cleared artifact. That work would need an adapter
contract for three ONNX inputs, deterministic sampling/remapping from original
STL faces, and a documented mapping from model class labels to tooth-instance
semantics. It is not compatible with the current single-input, adjacency-free
adapter contract.

## 4. Legally Viable Candidates

None identified. No audited pretrained artifact has explicit commercial-use and
redistribution rights that also cover its data provenance.

## 5. Candidates Requiring Permission

- MeshSegNet: obtain written permission/terms from the checkpoint rightsholder
  covering commercial deployment, redistribution (if applicable), and the
  training-data-derived artifact.
- ToothGroupNetwork / TGNet: obtain written source-code, checkpoint, and
  commercial-data-lineage permissions from the project rightsholder(s).
- Any checkpoint trained with Teeth3DS/3DTeethSeg'22: obtain a separate rights
  grant from the relevant data rightsholder; the published CC BY-NC-ND 4.0 terms
  are not sufficient.

## 6. Recommended Next Step

Do not integrate an external checkpoint. Procure either:

1. a commercially licensed dental segmentation artifact with an accompanying
   model card and complete artifact contract; or
2. a training-data license that explicitly permits commercial training and
   deployment, followed by an internally trained model with documented
   provenance, evaluation, and ownership.

Before any code change, legal review must approve the model and data rights.
Technical review must validate the supplied artifact against the required
contract below using a PHI-free/consented engineering corpus.

## 7. Exact Artifact / Weights Required

A future candidate must provide all of the following outside this repository:

- an immutable model artifact (preferably ONNX) and SHA-256 digest;
- artifact name, semantic version, producer, and release date;
- explicit commercial-use and redistribution license for the artifact;
- documented training-data provenance and commercial-use terms;
- model card describing intended use, exclusions, limitations, and evaluation;
- separate upper/lower behavior or documented single-model arch handling;
- a reproducible inference example using non-PHI data;
- written confirmation whether artifact outputs may be used in treatment
  planning workflows; and
- performance evidence on representative intraoral scans, without interpreting
  it as clinical validation.

## 8. Exact Model Contract Required

The existing fail-closed configuration requires a verified contract sidecar
before inference. A future approved artifact must document:

```json
{
  "input_name": "verified input tensor name",
  "input_layout": "batch_face_features",
  "feature_count": 15,
  "requires_adjacency": false,
  "output_mode": "face_labels or face_scores",
  "background_label": 0,
  "confidence_semantics": "documented per-face confidence meaning",
  "license_verified": true,
  "model_sha256": "artifact SHA-256"
}
```

This is the current adapter's accepted contract. If a cleared candidate requires
adjacency matrices, multiple input tensors, point sampling, or another layout,
it must receive a new engine-owned adapter interface and tests. That is a future
architecture review, not a silent relaxation of the present fail-closed rule.

No candidate is selected on accuracy alone. Legal rights and a verified
technical contract are both mandatory.
