# MeshSegNet Post-Processing Feasibility

> **INTERNAL RESEARCH ONLY**  
> **NOT CLINICALLY VALIDATED**  
> **NOT APPROVED FOR COMMERCIAL DEPLOYMENT**

**Analysis date:** 2026-09-20  
**Scope:** analysis of the isolated MeshSegNet benchmark only. No production
source, API, adapter, dependency, checkpoint policy, or fail-closed behavior
was changed.

## Benchmark Evidence

The internal maxillary run produced 33 connected non-gingiva regions from a
10,000-cell decimated mesh; the mandibular run produced 29. Both runs used 14
non-gingiva class indices, but also contained small disconnected components,
including one-face regions. The source meshes had 171,139 and 139,083 cells
respectively, so neither result remained mapped to every original face.

The connected-component counter groups same-label faces sharing a vertex. A
stricter shared-edge definition would not remove the observed fragmentation and
may divide some regions further.

## 1. Why Regions Fragment

The observed fragmentation is consistent with multiple interacting technical
causes. The benchmark does not isolate a single root cause.

### Face-Level Argmax Predictions

**Status: feasible with significant engineering to smooth; unsafe as a direct
tooth-instance result.**

MeshSegNet predicts a class independently for each working mesh cell after
neural graph processing, then the published inference script takes per-cell
argmax. Argmax has no requirement that all faces with one class form one
connected component. Boundary uncertainty therefore appears as isolated labels
or small islands.

### Decimation

**Status: requires retraining or a validated correspondence design to avoid its
main limitations.**

The author inference path decimates scans over 10,000 cells before prediction.
The real scans were reduced from over 139,000 cells to 10,000 cells. This:

- changes face boundaries and adjacency;
- removes fine tooth/gingiva separation detail;
- creates a new working mesh rather than selecting a traceable subset of
  original faces; and
- prevents direct label projection back to every original face.

Deterministic cleanup cannot recover boundary detail that decimation removed.

### Adjacency and Preprocessing

**Status: feasible with significant engineering to reproduce; unsafe to change
without retraining.**

MeshSegNet receives two dense graph matrices computed from barycenter distance
thresholds in normalized feature space. These are geometric proximity graphs,
not the original mesh's shared-edge topology. They encourage local agreement,
but do not guarantee topologically connected output regions. Changing feature
normalization, distance thresholds, cell count, or graph construction changes
the model input distribution and requires retraining or at least a new,
controlled evaluation.

### Disconnected Same-Label Components

**Status: feasible to detect; unsafe to merge blindly.**

A semantic class can legitimately occur in disconnected locations after noisy
prediction, but it can also correspond to different anatomical surfaces when
class semantics are not a documented FDI contract. The one-face components are
strong evidence of noise or resampling artifacts; they are not evidence that
all same-label components should be fused.

### Mesh Topology

**Status: feasible with significant engineering to analyze; unknown for the
current results.**

The source and decimated meshes may differ in local connectivity. A component
that is separate under shared-edge connectivity may touch only at a vertex, and
decimation can remove narrow bridges. Mesh topology must be preserved and
measured at every transformation before it can be used as a merge signal.

### Confidence and Class Prediction

**Status: unsafe/unknown.**

The benchmark retained argmax labels, not calibrated per-cell probabilities or
an uncertainty threshold. No class confidence calibration, FDI mapping, or
minimum-region validity rule is published for the selected checkpoint. A
post-processing policy based on arbitrary confidence or area thresholds would
be a new unvalidated rule and must not enter production.

## 2. Can Neighboring Same-Label Faces Be Merged Safely?

**Answer: only as a research candidate-generation operation; not safely as an
automatic tooth merge.**

Faces already connected through a shared edge and assigned one label can be
represented as one candidate component. Disconnected same-label components
should not be merged solely because their class indices match. A merge would
need, at minimum:

1. preserved original/deci­mated mesh correspondence;
2. shared-edge or validated geodesic-neighborhood evidence;
3. a documented gap/area/confidence policy derived from a lawful benchmark;
4. protection against merging adjacent teeth or teeth into gingiva; and
5. reviewable provenance of every merge.

The author optional `step6_predict_with_post_processing_pygco.py` uses graph
cut refinement on the decimated mesh and then KNN/SVM upsampling. That is
useful research evidence that deterministic refinement is possible, but it is
not validation that its fixed pairwise parameters, graph-cut weights, or KNN
behavior are safe for AlignerStudio cases.

## 3. Can Components Be Clustered Into Tooth Candidates?

**Status: feasible with significant engineering, research-only.**

A deterministic candidate extractor can group connected, non-gingiva faces and
retain each as a provisional region. It can calculate area, centroid, label
histogram, boundary length, and topology findings. This can produce an
engineering candidate list.

It cannot establish that a candidate is exactly one tooth from the current
benchmark because:

- class-to-FDI semantics are not documented;
- the real results contain small islands and multiple components per class;
- the mesh is decimated; and
- no benchmark ground truth exists for the evaluated case.

Candidate clustering is therefore not a replacement for model instance
segmentation or verified tooth-instance reconstruction.

## 4. Can Predictions Be Projected Onto the Original STL?

**Status: feasible with significant engineering; current result is not
projected.**

The author optional post-processing script uses KNN or SVM to upsample labels
from the decimated mesh to a mesh that it may itself simplify to 50,000 cells.
That demonstrates a possible research technique but does not preserve labels on
the original 139k/171k face meshes in this benchmark.

A future research implementation could compare these strategies:

- decimator-provided original-to-working face provenance, if available;
- nearest triangle or barycenter label transfer;
- nearest-surface projection with normal/geodesic consistency; or
- a model run on tiled/overlapping original-resolution patches with label
  reconciliation.

Nearest-neighbor projection is deterministic but can bleed labels across narrow
interproximal gaps. It is not enough by itself to claim stable original-face
segmentation. A surface-correspondence error report and held-out labeled scans
would be mandatory.

## 5. Can This Produce Stable `ToothInstance` Geometry?

**Status: requires retraining or a separately validated reconstruction system
for reliable instances.**

It is mechanically possible to create a mesh object from each projected
component. It is not currently defensible to call those objects stable tooth
instances because the benchmark lacks:

- original-face label correspondence;
- artifact cleanup validation;
- one-tooth-per-region evidence;
- class-to-FDI semantics;
- missing-tooth behavior; and
- confidence/error criteria.

The current results can support exploratory visualization and engineering
metrics, but not a domain `ToothInstance` feeding planning.

## 6. FDI Identification After Segmentation

**Status: feasible with significant engineering after robust instances exist;
unsafe/unknown on current fragments.**

FDI can remain a separate stage. AlignerStudio's existing geometric
identification expects complete, valid tooth geometry and produces explicit
identified/uncertain/unidentified states. It could cross-check model labels in
a future research pipeline, but it must not silently overwrite contradictory
model output.

For the current benchmark, FDI remains unavailable because the MeshSegNet
checkpoint's 14 tooth classes have no published formal FDI mapping and the
fragmented candidates do not meet a stable instance contract. A learned FDI
stage would require its own lawfully sourced data, artifact, and evaluation.

## 7. Engineering Effort Estimate

These estimates are planning ranges for research engineering, excluding legal,
clinical, data-governance, and model-training work.

| Step                                       | Feasibility                                 | Estimated research work           | Main uncertainty                                             |
| ------------------------------------------ | ------------------------------------------- | --------------------------------- | ------------------------------------------------------------ |
| Reproduce published preprocessing          | Feasible                                    | 1-2 weeks                         | Version/tooling equivalence and dense-memory limits          |
| Decimated-to-original projection prototype | Feasible with significant engineering       | 2-4 weeks                         | Surface correspondence and boundary leakage                  |
| Graph-cut/KNN refinement reproduction      | Feasible with significant engineering       | 2-4 weeks                         | Unvalidated parameters and high-resolution behavior          |
| Component extraction/fragment reporting    | Feasible                                    | 1-2 weeks                         | Topology convention and candidate metrics                    |
| Deterministic component merge research     | Feasible with significant engineering       | 3-6 weeks                         | Avoiding false merges/splits without labeled validation data |
| `ToothInstance` reconstruction prototype   | Feasible with significant engineering       | 2-4 weeks                         | Original-face mapping and validity criteria                  |
| Geometric FDI cross-check integration      | Feasible with significant engineering       | 1-3 weeks                         | Robustness to incomplete/fragmented candidates               |
| Reliable segmentation-to-instance pipeline | Requires retraining or validated new system | Not estimable from this benchmark | Label/data rights, ground truth, and failure rates           |

## 8. Comparison With Finding Another Pretrained Model

A pretrained model that natively provides full-resolution, per-face or
per-vertex tooth instances, documented FDI semantics, confidence definitions,
and a supported original-mesh mapping would reduce the technical work above.
It would still require explicit checkpoint/data/deployment rights before any use.

For the current MeshSegNet path, post-processing can improve engineering
visualization and produce candidate regions, but it cannot erase the core
limitations caused by decimation, unknown FDI semantics, and unvalidated
fragment cleanup. It is therefore not a lower-risk substitute for finding an
artifact with a proper instance/FDI contract.

## Conclusion

- **Feasible:** region detection, topology metrics, visual export, and
  exploratory graph-based refinement.
- **Feasible with significant engineering:** controlled projection experiments,
  candidate extraction, and deterministic cleanup research.
- **Requires retraining or a validated new system:** reliable full-resolution
  tooth instances suitable for downstream planning.
- **Unsafe/unknown:** automatic merging of disconnected components, FDI
  assignment from current checkpoint labels, and any clinical or production use.

The production segmentation gate must remain fail-closed. No result in this
analysis authorizes MeshSegNet output to enter AlignerStudio treatment planning.

## Sources

- Internal benchmark: `docs/SEGMENTATION_INTERNAL_BENCHMARK.md`
- Author inference: <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/step5_predict.py>
- Author refinement/upsampling: <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/step6_predict_with_post_processing_pygco.py>
- Author training preprocessing: <https://raw.githubusercontent.com/Tai-Hsien/MeshSegNet/master/Mesh_dataset.py>
