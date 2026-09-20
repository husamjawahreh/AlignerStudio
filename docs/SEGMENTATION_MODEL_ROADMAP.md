# Segmentation Model Roadmap

**Research date:** 2026-09-20  
**Ranking principle:** practical path to lawful deployable segmentation, not
research accuracy. No path is authorized to change the current fail-closed
runtime until its legal and technical gates are complete.

## Ranked Paths

1. **PATH A:** acquire a commercially licensed pretrained artifact with a
   deployable inference contract.
2. **PATH B:** train an owned model from commercially licensed/consented dental
   scan data using an openly licensed architecture.
3. **PATH C:** license a commercial dental segmentation SDK/API through a vendor
   agreement.
4. **PATH D:** research-only evaluation of public academic artifacts.

## PATH A — Commercially Licensed Pretrained Artifact

**Practical rank:** 1, if a vendor can supply the complete artifact package.

- **Expected engineering work:** implement an adapter only after artifact
  acceptance. Validate STL conversion, exact tensor contract, output-to-original
  mesh mapping, instance grouping, FDI mapping, provenance, latency, and error
  modes. Prefer a local ONNX Runtime artifact, but an approved managed API can
  be considered through a separate boundary.
- **Licensing work:** obtain executed commercial deployment terms explicitly
  covering model artifact use, production inference, permitted geographies,
  model updates, audit rights, data handling, output ownership, and any
  redistribution/edge deployment.
- **Approximate implementation complexity:** medium if a stable ONNX contract
  and integration support are supplied; high if tensor/preprocessing behavior
  is undocumented or vendor-specific.
- **Required infrastructure:** vendor artifact registry or secure credential
  store, model hash/version controls, non-PHI validation corpus, monitoring,
  model-change approval process, and CPU/GPU capacity documented by vendor.
- **Must be obtained before coding:** executable license, model card, trained
  artifact, SHA-256, input/output specification, preprocessing specification,
  upper/lower behavior, FDI/instance semantics, runtime requirements, and a
  reproducible inference example.
- **Current status:** no public candidate discovered in this audit meets these
  requirements.

## PATH B — Train an Owned Model From Lawful Data

**Practical rank:** 2. This is the most controllable long-term route when a
commercially reusable dataset is available.

- **Expected engineering work:** create a data ingestion/annotation protocol
  outside production runtime; choose and train a model such as PointNet++,
  DGCNN, MeshCNN, or a more modern point-cloud architecture; define separate
  semantic FDI and tooth-instance outputs; export a validated inference
  artifact; implement an adapter; then conduct engineering and clinician review.
- **Licensing work:** secure written rights for collection, annotation, model
  training, derivative artifacts, commercial deployment, future retraining,
  retention, and de-identification. Verify every architecture dependency and
  any pretraining source separately.
- **Approximate implementation complexity:** high. It includes data governance,
  annotation quality, model development, reproducibility, export, and
  prospective validation. It is not a short-term product toggle.
- **Required infrastructure:** consent/data-use agreements, secure storage,
  annotation tools, GPU training environment, experiment tracking, artifact
  registry, evaluation corpus, and governance review.
- **Must be obtained before coding:** a data-rights agreement, a documented
  label protocol for gingiva/tooth instances/FDI, a representative lawful
  dataset, model ownership plan, and non-clinical benchmark criteria.
- **Current status:** viable in principle. No public dataset identified in this
  audit establishes the required commercial training rights.

## PATH C — Commercial Dental Segmentation SDK/API

**Practical rank:** 3. This can reduce model operations burden but depends on a
vendor's willingness to license an embedding or service integration.

- **Expected engineering work:** build a service/adapter boundary for the
  vendor's API or local SDK, translate STL/OBJ format as specified, preserve
  case identity/provenance, map vendor output to immutable tooth instances,
  and implement explicit unavailable/timeout/version-change states.
- **Licensing work:** negotiate scope of use, sublicensing/embedding,
  commercial treatment-planning use, patient-data processing, jurisdiction,
  service levels, data retention, output rights, and model updates.
- **Approximate implementation complexity:** medium to high, depending on the
  API's ability to return vertex/face-to-tooth instance mappings and FDI labels.
- **Required infrastructure:** vendor account/credentials, legal data
  processing agreement, network and audit controls, API availability handling,
  and integration test fixtures supplied by the vendor.
- **Must be obtained before coding:** written SDK/API agreement, stable versioned
  API reference, supported input formats, output schema, FDI/instance semantics,
  rate/latency limits, error behavior, and a permitted test corpus.
- **Current status:** exocad and Medit market commercial dental workflows, but
  public materials reviewed here do not establish a tooth-segmentation
  API/SDK or embedding right. Vendor inquiry is required.

## PATH D — Research-Only Fallback

**Practical rank:** 4. This is useful for technical study but cannot be a
production route.

- **Expected engineering work:** keep external research code/artifacts outside
  the product runtime; reproduce preprocessing and evaluate only on data whose
  terms permit the activity.
- **Licensing work:** honor all non-commercial and no-derivatives conditions;
  do not use results, weights, or training lineage as a shortcut to deployment.
- **Approximate implementation complexity:** low to medium for experiments, but
  it produces no deployable model.
- **Required infrastructure:** isolated research environment and clear data
  access controls.
- **Must be obtained before coding:** documented research authorization and
  project-specific approval.
- **Current status:** MeshSegNet, ToothGroupNetwork/TGNet, and
  Teeth3DS/3DTeethSeg'22 belong here until rightsholders grant adequate rights.

## Non-Negotiable Production Gate

Regardless of path, do not enable real-case segmentation until all of the
following are documented and accepted:

1. explicit commercial deployment right for the exact artifact or service;
2. explicit data provenance and training rights;
3. artifact identity, hash, version, and change-management policy;
4. tested input format, preprocessing, output classes, FDI semantics, instance
   semantics, and confidence semantics;
5. deterministic mapping from inference output to original uploaded mesh faces
   or vertices;
6. CPU/GPU and latency envelope verified on representative engineering scans;
7. failure behavior that remains fail-closed; and
8. engineering evaluation followed by the project's required clinical review
   process before any clinical claim.

The present AlignerStudio gate remains the correct behavior: when no approved
artifact contract is configured, uploaded real cases stop at `model_unavailable`
and never fall back to fixtures.
