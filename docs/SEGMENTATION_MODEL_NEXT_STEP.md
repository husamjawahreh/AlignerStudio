# Segmentation Model Next Step

**Selected internal benchmark candidate:** ToothInstanceNet / `3dteethland`

## Selection

ToothInstanceNet is the single most promising technical candidate for the next
internal benchmark. This is not a commercial, clinical, or production approval.

It wins the shortlist on output-contract completeness, not reported accuracy:

1. It explicitly accepts STL, PLY, and OBJ scan inputs.
2. It explicitly handles upper/lower by filename convention.
3. It explicitly produces tooth-instance JSON and landmark JSON.
4. It explicitly describes FDI-correct labeling based on jaw naming.
5. Its output is written beside the source scan, making original-scan
   correspondence more plausible than MeshSegNet's 10,000-cell decimation path.
6. It has an author-linked public checkpoint location and an executable inference
   entry point.

## Required Benchmark

Use the existing anonymized AlignerStudio upper/lower pair:

```text
data/uploads/50d34180-53b5-4eb9-8164-f73b0b96650e-upper-38f5de61c3ac42d788fcee7f453318ce.stl
data/uploads/50d34180-53b5-4eb9-8164-f73b0b96650e-lower-8bd6d9913fc44977997e307c337d585b.stl
```

The benchmark should:

- copy or reference the original scans without mutation;
- rename only benchmark working copies to the required upper/lower convention;
- obtain the author-linked checkpoint without committing it;
- record repository commit, checkpoint filename, URL, SHA-256, and license/status;
- run both jaws through the official inference path;
- preserve raw JSON and landmark outputs outside production;
- count instance IDs and FDI labels;
- validate that instance labels cover original points/vertices as claimed;
- reconstruct provisional meshes only in the research area;
- measure runtime, GPU memory, missing/partial tooth behavior, and failures; and
- compare output fields directly against the AlignerStudio `ToothInstance`
  requirements without implementing the adapter.

## Gates Before Benchmarking

1. Confirm the exact Google Drive checkpoint files and download permissions.
2. Record checkpoint SHA-256 after download.
3. Review the repository MIT license and all checkpoint/data usage terms.
4. Verify the required CUDA kernels and GPU availability.
5. Verify the exact JSON schema for `instances`, FDI labels, landmarks, and jaw.
6. Confirm whether the model outputs original-vertex labels or only sampled-point
   results.

If any gate fails, mark the benchmark `BLOCKED` and do not substitute another
checkpoint.

## Expected AlignerStudio Mapping

A successful research result would still require an eventual adapter-only
mapping:

```text
instance JSON + source mesh
  -> one mesh per instance ID
  -> FDI/jaw from verified label fields
  -> centroid and landmarks from source geometry
  -> confidence only if the model exposes a documented confidence field
  -> immutable ToothInstance with experimental provenance
```

The mapping must preserve unknown/missing/ambiguous teeth as explicit states.
It must not infer or shift FDI labels silently. No production adapter should be
written until the benchmark validates these assumptions.

## Alternatives Kept in Reserve

- **3DTeethSAM:** benchmark only if ToothInstanceNet cannot run or its instance
  JSON contract fails validation. It has a public checkpoint folder and a
  compelling instance-segmentation description, but requires SAM2 weights,
  multi-view preprocessing, PyTorch3D, and GPU infrastructure; its public FDI
  contract is less explicit.
- **CrossTooth CVPR2025:** reserve as a semantic-mask baseline. Its public
  checkpoint and PLY inference are useful, but it lacks a documented instance,
  FDI, and upper/lower output contract.
- **MeshSegNet:** retain as an already measured research baseline only. Do not
  invest in production post-processing around it at this stage.

## Non-Production Boundary

This next step remains entirely under an isolated research benchmark area. No
candidate will be connected to FastAPI, React, the production segmentation
adapter, treatment planning, export, or the `model_unavailable` behavior.
