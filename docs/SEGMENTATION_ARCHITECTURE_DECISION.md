# Segmentation Architecture Decision

**Decision date:** 2026-09-20  
**Scope:** PATH B architecture selection for a future owned model. This is not
an integration approval. No source code, checkpoint, dataset, dependency, or
runtime behavior changes are authorized by this decision.

## Decision

**Preferred future training architecture: TSegFormer, trained from scratch on
newly procured commercially usable/consented intraoral data.**

This is a conditional architecture decision, not a model selection. The public
TSegFormer code is MIT licensed and its point-label design is directly relevant
to separate upper/lower intraoral scan labeling. Its public checkpoint and data
rights are not clear and must not be used.

## 1. Strongest Candidate for an Owned Commercial Model

TSegFormer is the strongest candidate among the audited focused options because:

- its source is publicly available under MIT, unlike TSegLab and TeethNet;
- it is tooth-specific rather than a general 3D baseline;
- it consumes a jaw category and emits a 33-class tooth/gingiva point-label
  output, which is close to the needed FDI-aware semantics;
- it uses point features rather than proprietary mesh tooling, so a deterministic
  STL-to-point preprocessing pipeline can be built and audited; and
- a new checkpoint can be trained without inheriting rights from the authors'
  unreleased data or model artifact.

It is **not** selected based on reported research accuracy. The selection is
conditional on data rights, a reproducible label contract, engineering export
validation, and legal review.

## 2. Why Not TSegLab or TeethNet

- **TSegLab** is technically attractive because it describes localization,
  segmentation, and labeling, but no public reusable source/checkpoint contract
  was found. Its disclosed Teeth3DS evaluation lineage is non-commercial. It is
  a vendor/author permission path, not a PATH B implementation basis.
- **TeethNet** is a 2025 paper record with no discovered public source,
  checkpoint, dataset provenance, or reproducible I/O contract. It cannot be
  selected for engineering work.

## 3. Exact Training Data Required

Before training code is written, obtain a dataset through a written commercial
license or consent/data-use agreement that explicitly permits:

1. ingestion of upper and lower intraoral surface scans in their original form;
2. annotation, quality review, augmentation, and derivative datasets;
3. model training, fine-tuning, evaluation, and internal research;
4. ownership or licensed use of resulting checkpoints and exported artifacts;
5. commercial deployment in an orthodontic treatment-planning product;
6. model artifact distribution to permitted customer environments, if planned;
7. retention, deletion, geographic processing, and data-security obligations;
   and
8. the use of de-identified/consented samples for non-production regression
   testing.

The public Teeth3DS/3DTeethSeg'22 CC BY-NC-ND 4.0 data does not satisfy this
requirement and must not be used for commercial model training.

## 4. Exact Annotations Required

Each arch scan must have a versioned annotation record containing:

- scan identifier and explicit arch (`upper` or `lower`);
- original mesh vertices and faces, preserving a mapping to annotation indices;
- per-vertex or per-face gingiva/background label, with zero reserved by a
  documented convention;
- tooth-instance identifier for every tooth surface element;
- permanent FDI number for every tooth instance when known;
- an explicit missing-tooth/not-present representation rather than inferred
  labels;
- an explicit unknown/ambiguous/unusable annotation state;
- scan orientation, units, scanner/source metadata, and preprocessing version;
- annotator/reviewer provenance and quality-control status; and
- train/validation/test split provenance at patient level to prevent leakage.

FDI labels should be treated as labels supplied by the data protocol, not as a
clinical inference. The training specification must define which dentitions,
restorations, appliances, missing teeth, mixed dentition cases, and artifacts
are in/out of scope.

## 5. Can an Owned TSegFormer Model Feed AlignerStudio?

Yes, conditionally. A new model can produce this chain:

```text
STL mesh
  -> deterministic point/features + jaw category
  -> per-point gingiva/tooth FDI label probabilities
  -> project points back to original mesh vertices/faces
  -> connected components per non-gingiva FDI label
  -> tooth instances with source mesh references
  -> existing geometric FDI identification cross-check
  -> setup, staging, geometric validation, review, export
```

This requires a deliberate reconciliation rule between model-provided FDI labels
and the existing geometric `ToothIdentificationEngine`. The model output must
never overwrite uncertain or contradictory geometry silently. A future engine
must preserve both model provenance/confidence and identification findings.

Missing teeth must be represented by absent labeled components, then surfaced
as incomplete/uncertain identification. They must not be filled with fixture or
neighboring labels.

## 6. Eventual Adapter Changes

No adapter change is authorized now. When legal/data gates are complete,
TSegFormer would require an engine-owned, tested adapter contract different from
the current generic MeshSegNet adapter:

- input one: fixed-size point features, documented as the exact eight-feature
  order and normalization used at training;
- input two: explicit two-value arch/jaw category;
- output one: 33-class per-point scores or labels;
- output two: optional binary gingiva scores, if retained after training;
- deterministic 10,000-point sampling strategy and seed behavior;
- deterministic projection of sampled output back to original STL vertices or
  faces, including coverage/error behavior for unsampled regions;
- explicit class-to-FDI mapping; and
- model artifact hash, license, data-provenance declaration, confidence
  semantics, and preprocessing version.

The current adapter intentionally accepts a single 15-feature face tensor and
rejects adjacency-dependent contracts. It must not be loosened to accept
TSegFormer implicitly. A future dedicated point-segmentation adapter interface
would need an architecture review, tests, and fail-closed unavailable behavior.

## 7. Legal Gates Before Training Code

Obtain all of the following before writing training, preprocessing, or export
code:

1. signed commercial data license or consent/data-use agreement;
2. written permission for annotation and derivative-model creation;
3. written ownership/license terms for checkpoints and exported ONNX artifacts;
4. confirmation of permitted commercial deployment and any redistribution;
5. a reviewed inventory of every source-code dependency and its license;
6. a data-protection/PHI handling plan and permitted engineering test corpus;
7. a documented intended-use and exclusion statement; and
8. legal approval recorded in `REUSE_MATRIX.md` before any model artifact enters
   the workspace.

## 8. Technical Gates Before Production Integration

After the legal gates and before enabling real cases:

1. freeze the annotation and label contract;
2. train and reproduce an owned artifact from a controlled environment;
3. validate the artifact against a held-out, legally usable engineering corpus;
4. export and validate an ONNX artifact or justify a separately governed
   inference runtime;
5. verify output-to-original-mesh mapping, FDI mapping, missing-tooth behavior,
   and confidence semantics;
6. measure CPU/GPU latency, memory, failures, and determinism;
7. implement a dedicated adapter behind the existing engine boundary; and
8. preserve `model_unavailable` whenever the artifact, contract, or validation
   requirement is absent.

No accuracy metric alone unlocks production use. Legal ownership, reproducible
technical behavior, and compatibility with the existing treatment-planning
pipeline are all mandatory.
