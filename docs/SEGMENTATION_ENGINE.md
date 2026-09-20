# Real Tooth Segmentation Engine

**Phase 13 status:** The pipeline has a fail-closed external-model
configuration gate. No legally cleared, technically verified model artifact
was available in this workspace, so no real model has been connected.

## Scope

Phase 3 replaces the production path's static FDI fixture with a real,
geometry-only segmentation pipeline:

```
STL/mesh path
  → mesh validation
  → deterministic normalization
  → per-face inference features
  → external ONNX Runtime adapter
  → output parsing
  → connected per-tooth instance extraction
  → deterministic instance ordering
  → confidence + provenance metadata
```

Tooth identification is deliberately not part of this engine. A segmentation
instance contains geometry and a stable `instance_id`, not an FDI number. FDI
assignment must be implemented as a separate future engine after segmentation.

## Modules

- `domain/tooth/segmentation.py`
  - `ToothInstance`: original triangle indices, original vertex indices,
    extracted local vertices/faces, centroid, confidence, provenance, fixture
    flag, notes.
  - `SegmentationMetadata`: engine/model/version, input/output counts,
    confidence min/mean/max, provenance, fixture flag, notes.
  - `ToothSegmentationResult`: ordered instances + metadata + source mesh path;
    validates contiguous deterministic instance IDs.
- `engines/segmentation/preprocessing.py`
  - loads a triangle mesh with `trimesh`;
  - re-centers vertices and scales them by maximum radial extent;
  - builds 15-value per-face features: 9 normalized face-vertex coordinates,
    3 unit-normal values, and 3 normalized face-centroid values;
  - exposes engineering-only triangle-count limits through
    `MeshPreprocessingConfig`.
- `adapters/meshsegnet/onnx_adapter.py`
  - lazy imports `onnxruntime` only when inference is requested;
  - accepts a configurable external model path;
  - supports dependency injection of a session for tests;
  - raises `SegmentationModelUnavailableError` when the path, runtime, or
    model input contract is unavailable.
- `engines/segmentation/onnx_engine.py`
  - composes preprocessing, adapter inference, parsing, and extraction;
  - defaults output provenance to `experimental`;
  - never creates a fixture or fake segmentation result.
- `engines/segmentation/output.py`
  - accepts face labels + confidences or class-score tensors;
  - treats label `0` as background/gingiva, never as a tooth identity;
  - splits each non-background label into connected face components;
  - sorts components by their first/original minimum triangle index;
  - remaps each component into a self-contained local mesh.

## Model Configuration and Contract Gate

No model path is hard-coded and no model file is committed. A future service
composition root should construct the adapter from configuration, for example:

```python
OnnxRuntimeSegmentationAdapter(model_path=os.environ["ALIGNERSTUDIO_SEGMENTATION_MODEL"])
```

The API reads external configuration only; no path or model is committed:

```bash
export ALIGNERSTUDIO_SEGMENTATION_MODEL=/secure/path/model.onnx
export ALIGNERSTUDIO_SEGMENTATION_CONTRACT=/secure/path/model-contract.json
export ALIGNERSTUDIO_SEGMENTATION_MODEL_NAME=cleared-model-name
export ALIGNERSTUDIO_SEGMENTATION_MODEL_VERSION=verified-version
```

The required contract sidecar must contain `input_name`,
`input_layout: "batch_face_features"`, `feature_count: 15`,
`requires_adjacency: false`, `output_mode`, `background_label: 0`, documented
confidence semantics, `license_verified: true`, and the artifact
`model_sha256`. The loader hashes the configured artifact before inference.

The optional Python dependency is installed with:

```bash
pip install -e "services/api[ml-seg]"
```

The model artifact must be supplied by the deployer and must have a separately
verified license. MeshSegNet's repository code is MIT, but its pretrained
weights have no documented redistribution/commercial-use license. The current
adapter is prepared for a legally-cleared MeshSegNet-to-ONNX artifact, but it
does not claim that the artifact exists or that its I/O contract has been
verified.

## Provenance

- `real`: measured source mesh data only.
- `generated`: deterministic algorithmic output that is not clinician-reviewed.
- `experimental`: output from this external model adapter while its quality is
  under evaluation. This is the default for ONNX segmentation.
- `fixture`: deterministic engineering/test data only.
- `clinically_reviewed`: reserved for explicit future review workflows; this
  engine never emits it.

Every instance and the result metadata carry provenance. `fixture` is a
separate enum value rather than a hidden fallback state. Missing models raise
an error and stop the pipeline.

## Output Contract

The adapter returns raw model outputs. The engine accepts either:

1. a label vector shaped `(face_count,)`, optionally followed by a confidence
   vector shaped `(face_count,)`; or
2. a score/logit matrix shaped `(face_count, class_count)`.

The engine validates lengths, label non-negativity, finite confidence values,
and confidence range `[0, 1]`. It does not infer FDI labels from class order.
The model's class IDs are used only to form connected segmentation regions.

## Engineering Fixture

`tests/fixtures/synthetic_segmentation_arch.obj` contains two disconnected
tetrahedra. It is deterministic engineering data only: not a dental scan,
not clinical data, not a model weight, and not a treatment result. Tests lower
the engineering minimum triangle count explicitly for this fixture.

## Current Limitations

- No legally-cleared pretrained model or weights are bundled.
- No actual ONNX input/output metadata was available to audit. The contract
  remains unverified until a legally cleared artifact and its contract sidecar
  are supplied.
- The supported adapter shape is exactly `(1, face_count, 15)`: nine ordered
  normalized face-vertex coordinates, three unit-normal values, then three
  normalized face-centroid values. Faces retain original mesh indexing and
  instances retain original triangle indices. Models requiring decimation,
  adjacency tensors, alternate feature ordering, or other output semantics are
  rejected rather than guessed.
- Connected components are formed by shared mesh vertices and are not a
  clinical tooth-identification algorithm.
- No FDI identification, arch analysis, coordinate frames, planning, staging,
  collision checks, UI wiring, or clinical-case benchmarking is included.
