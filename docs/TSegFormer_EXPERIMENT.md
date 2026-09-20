# TSegFormer Internal Engineering Evaluation

**Status:** `CHECKPOINT_UNAVAILABLE`  
**Decision date:** 2026-09-20  
**Scope:** internal engineering evaluation only. This document does not approve
commercial use, clinical use, production deployment, or model integration.

## Result

The official TSegFormer repository does **not** publish a downloadable
pretrained checkpoint.

The repository README calls `best_model.t7` a pretrained model for evaluation,
but its documented workflow first trains it with:

```text
python main.py --epochs 200 --num_points 10000
```

and saves it under `./outputs/exp/models`. The official GitHub repository
contents contain only `LICENSE`, `README.md`, `data.py`, `main.py`, `model.py`,
`pipeline.png`, and `util.py`. The official releases API returns an empty list.
No official release asset, Git LFS artifact, model hub entry, or checkpoint
download URL was found in the audited official materials.

Therefore no checkpoint was downloaded, no SHA-256 exists to record, and no
experimental inference script was created. An unverified third-party checkpoint
must not be substituted.

## Exact Source Version

- **Repository:** <https://github.com/huiminxiong/TSegFormer>
- **Audited branch:** `main`
- **Audited commit:** `7784e0c9c5a434b31be32b65e24ca625d4d50612`
- **Source license:** MIT, repository `LICENSE`
- **Checkpoint source:** unavailable
- **Checkpoint SHA-256:** unavailable; no artifact was obtained
- **Checkpoint license:** `WEIGHTS_NOT_CLEAR_FOR_INTEGRATION`
- **Training-data provenance/license:** not documented by the repository beyond
  the phrase "IOS dataset"; commercial rights are not established

## Available Source Contract

### Architecture

The public source is a PyTorch geometry-guided point transformer. It exposes:

- a seven-channel point-feature model input in `model.py`;
- a second two-value jaw-category input;
- a 33-class per-point tooth/gingiva segmentation head; and
- a binary gingiva auxiliary head.

The training source uses a geometry-guided curvature loss and local point
sampling/grouping. It is not an ONNX artifact and no official ONNX export is
provided.

### Input and Preprocessing

`data.py` expects preprocessed per-scan JSON, not STL/OBJ/PLY directly:

```text
{
  "feature": [[8 values per point], ...],
  "label": [integer label per point, ...],
  "category": [two jaw-category values]
}
```

The documented workflow randomly samples exactly 10,000 points without
replacement. `main.py` interprets feature values as an eight-channel point
representation and uses feature index 7 as curvature. The public repository
does not include a raw STL-to-feature conversion specification, alignment
contract, normalization recipe, or input dataset.

### Output and Tooth Labels

The source uses 33 segmentation classes and reserves zero for gingiva. It uses
a two-value jaw category and offsets positive predictions by 16 for one jaw in
its standalone inference function. This indicates jaw-conditioned tooth labels,
but the repository does not publish a formal class-to-FDI mapping or a missing-
tooth policy. It also does not provide a contract for mapping sampled point
predictions back to original STL faces.

## Inference Evaluation

| Measure                    | Result                                                                                                                                           |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Input case                 | Not run; no legitimate checkpoint                                                                                                                |
| Inference success/failure  | Not run; `CHECKPOINT_UNAVAILABLE`                                                                                                                |
| Runtime                    | Not measured                                                                                                                                     |
| GPU/CPU requirements       | Official source documents Python 3.7.11, PyTorch 1.9.0 + CUDA 11.1; train/test code uses CUDA/DataParallel paths. CPU behavior is not validated. |
| Detected tooth regions     | Not measured                                                                                                                                     |
| Segmentation quality       | Not measured                                                                                                                                     |
| Direct FDI identity        | Not validated; formal mapping unavailable                                                                                                        |
| `ToothInstance` conversion | Not implemented or validated                                                                                                                     |

No local PHI-free engineering scan was processed. No production endpoint,
SegmentationEngine, adapter, dependency, or fail-closed behavior was changed.

## Conversion Requirements for a Future Experiment

Before an evaluation checkpoint could be tested, the experiment would need:

1. a rightsholder-provided official checkpoint URL and explicit engineering-use
   terms;
2. recorded artifact SHA-256, source commit, license, and data provenance;
3. a deterministic STL/OBJ/PLY to aligned eight-feature point conversion;
4. deterministic 10,000-point sampling and a mapping from sampled points to
   original mesh vertices/faces;
5. a verified jaw-category convention;
6. an explicit class-to-FDI table and zero/gingiva behavior;
7. a connected-component/point-projection design to construct immutable
   `ToothInstance` meshes; and
8. CPU/GPU reproducibility and output-equivalence tests.

## Estimated Work for Production Integration

No estimate is valid until an artifact and complete label/preprocessing contract
exist. After those gates, the likely work is substantial: an experimental
preprocessor, dedicated multi-input point-model adapter, sampled-output
projection, FDI/instance reconciliation, artifact validation, non-production
benchmarking, and a separate architecture review. The existing production
single-input ONNX segmentation adapter must not be repurposed implicitly.

## Sources

- Repository contents API: <https://api.github.com/repos/huiminxiong/TSegFormer/contents>
- Releases API: <https://api.github.com/repos/huiminxiong/TSegFormer/releases>
- Main commit reference: <https://api.github.com/repos/huiminxiong/TSegFormer/git/refs/heads/main>
- README: <https://raw.githubusercontent.com/huiminxiong/TSegFormer/main/README.md>
- MIT license: <https://raw.githubusercontent.com/huiminxiong/TSegFormer/main/LICENSE>

This record is for internal research governance and is not legal advice.
