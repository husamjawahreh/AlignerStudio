# FV-03 — Segmentation execution and clinical review foundation

| | |
|---|---|
| Phase | FV-03 only |
| Date | 2026-09-26 |
| Real inference | **ENVIRONMENT_BLOCKED** |
| Review contract | **PARTIAL** |
| Clinical validity | Not established |

This is not a clinical-accuracy claim. A completed job, if one is ever produced, is a segmentation candidate. It is not FDI, tooth identity, arch identity, left/right identity, or doctor verification. FV-04 was not started. Landmarks, clinical axes, roots, occlusion, setup, staging, IPR, attachments, manufacturing, and export were not implemented.

FV-03.1 keeps this blocked verdict and adds the runtime manifest, self-test, evidence seal, and review provenance in `docs/FV03_1_SEGMENTATION_RUNTIME.md`. FV-03.2 adds the real-run evidence gate and immutable preprocessing reproducibility reference in `docs/FV03_2_SEGMENTATION_EVIDENCE_GATE.md` without claiming clinical accuracy. The face-index split control from this phase is withdrawn there: split is `SPLIT_UNAVAILABLE`. The timings in this file stay the FV-03 blocked-run record.

## Architecture

A segmentation job may start only from an accepted prepared artifact. The source file and the prepared file stay immutable. The candidate stores face-index partitions that point at the prepared SHA-256. It does not replace that mesh, fill holes, or turn an open crown into a solid.

```
ACCEPTED_PREPARED_ARTIFACT
    → INPUT_GATE
    → CAPABILITY_PROBE
    → TOOTHINSTANCENET_IF_EXECUTABLE
    → CANDIDATE_OR_BLOCKER
    → TECHNICAL_VALIDATION
    → REVIEW_STATE
```

The worker is one process-local thread named `alignerstudio-segmentation`. There is no distributed queue. An equivalent active request (same case, arch, prepared SHA, and backend) returns the existing job. A different active request on that arch returns HTTP 409. A job that sees a newer preparation commit or a newer segmentation generation fails as `STALE_SEGMENTATION` and does not overwrite the newer run.

ToothInstanceNet is a backend behind that boundary. The domain record stores backend name, version, model id, and model SHA. It does not embed DentalNet tensor names as clinical fields.

## Input gate

The run is refused unless all of these hold:

- a source case and intake artifact exist
- the preparation was accepted
- readiness is `READY_FOR_SEGMENTATION` or `READY_WITH_WARNINGS`
- at least one preparation operation produced a derived mesh
- the source file exists and its SHA-256 matches provenance
- the derived file exists, is not a `*.partial`, and its SHA-256 matches the stored output
- lineage is active and complete
- no failed or cancelled preparation job is the active output
- the mesh is finite and face indices stay inside the vertex range
- the stored face count matches the reloaded face count
- the artifact is not presentation-only geometry

`PREPARED`, `NOT_PREPARED`, and `BLOCKED` cannot start a run. Accepting the untouched source cannot start a run. The prepared SHA is the segmentation input provenance. `uses_derived_hash_as_source` stays false.

## Model contract

The pinned checkpoint is `instseg_full.ckpt`, SHA-256 `100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803`.

Re-read on this host: 6 input channels, instance head width 6 (offsets and sigmas) and a seed logit, 7 identify logits per instance, instance ids from learned region clustering. The checkpoint does not encode FDI, arch, or left/right. Class names are not stored. A checkout yaml that sets `distinguish_left_right: true` is not the stored config, so that distinction stays unverified. The mapping of the seven classes is `NOT_ESTABLISHED`.

Preprocessing values are not in the checkpoint. This probe does not treat them as a measured contract and does not run them while the backend is blocked.

## Runtime states

| State | Meaning here |
|---|---|
| `AVAILABLE` | The TIN backend can execute. Not this host. |
| `DRIVER_UNAVAILABLE` | NVIDIA driver is not visible. Primary state on this host. |
| `PYTORCH_UNAVAILABLE` | PyTorch cannot be imported. Also true here. |
| `CUDA_EXTENSION_UNAVAILABLE` | `pointops` / CUDA extension is absent. Also true here. |
| `MODEL_CONTRACT_UNAVAILABLE` | The state dict does not re-derive the known tensor contract. |
| `MODEL_ARTIFACT_UNAVAILABLE` | The checkpoint file is missing or its hash does not match. |
| `INPUT_UNSUPPORTED` | The prepared artifact failed the input gate. |
| `BACKEND_ERROR` | The backend raised an unexpected failure. |

Applicable states are kept together. They are not collapsed into one vague error. ONNX is not used as a substitute. The fixture firewall still rejects fixture output on a real case. A blocked run stores the blocker, zero instances, `real_inference` false, and `clinically_segmented` false.

`ENVIRONMENT_BLOCKED` is the availability for driver, PyTorch, CUDA extension, and missing model artifacts. `NOT_AVAILABLE` is the availability when the contract or the input cannot be used. `AVAILABLE` is the only state that may call the network.

## Candidate and review

Each instance has a stable internal id (`inst-0`, not an FDI number), the run id, a face-index reference to the prepared SHA, backend provenance, the raw model class when one exists, and confidence only when the model contract actually emits it. This checkpoint path does not invent confidence. Uncertainty is omitted unless a model emits it.

Truth states used: `PREDICTED` for a model partition, `PROPOSED` for a doctor merge or split, `INVALID` for a doctor rejection. `VERIFIED` is not assigned by the pipeline or by accepting a candidate. Review authorship is `MODEL_PREDICTION`, `DOCTOR_MODIFIED`, `DOCTOR_ACCEPTED`, `DOCTOR_REJECTED`, or `REQUIRES_REVIEW`.

Review can select, inspect, hide, show, mark for review, accept, reject, and merge disjoint instances of the same prepared mesh. Undo, redo, and reset restore recorded operations. The model snapshot is not rewritten. FV-03.1 marks split `SPLIT_UNAVAILABLE` because the form cannot pick a safe face partition. A rejected instance is not merged.

Before a run is reviewable, deterministic checks cover input provenance, output references, finite geometry, unique instance ids, face-index range, lineage, backend provenance, and the ban on fabricated FDI, confidence, and automatic verification. That check is not clinical validation. A blocked run is not reviewable.

## Performance on this host

The same FV-02 scan: 8,557,034 bytes, 513,417 vertices, 171,139 faces, SHA-256 `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48`. The original file was only read. A copy was oriented, accepted, and gated. Readiness was `READY_WITH_WARNINGS`. Library: trimesh 5.1.0. Report: `.research/tmp/fv03_report.json`.

| Step | Result |
|---|---|
| Prepared mesh load | 145.5 ms |
| Input gate | 326.3 ms, accepted |
| Capability detection | 1511.3 ms |
| Inference | not attempted |

Primary blocker: `DRIVER_UNAVAILABLE`. Also applicable: `PYTORCH_UNAVAILABLE`, `CUDA_EXTENSION_UNAVAILABLE`. Availability: `ENVIRONMENT_BLOCKED`. `inference_ms` is null. Model SHA matched the pin. Input channels 6. Identify logits 7. `fdi_encoded` false.

RSS before these three steps was 447.0 MB, after the orientation commit in the same process. RSS after the probe was 516.2 MB. Peak RSS (`VmHWM`) was 529.3 MB. That peak includes the preparation commit already performed in the process. It is not a GPU memory sample and it is not an inference measurement.

## Browser verification

Live, not skipped. Playwright `tests/e2e/fv03_segmentation.spec.ts` passed in 46.4 s against `http://127.0.0.1:5177` and `http://127.0.0.1:8000`.

The test created a case, uploaded the 8,557,034-byte STL, ran Rotate 90° Z to completion, accepted the prepared mesh (`READY_WITH_WARNINGS`), and started segmentation. The stored run is `blocked` with `DRIVER_UNAVAILABLE` and availability `ENVIRONMENT_BLOCKED`. Semantic identity is `NOT_ESTABLISHED`. `real_inference`, `fdi_assigned`, and `clinically_segmented` are false. The review region is visible and contains no instances. No screenshot suite was added.

The web server in this session was Vite on port 5177. The spec default is 5173, so the run set `P8_WEB_URL`.

## Tests

`tests/python/test_fv03_segmentation.py` covers the input gate, raw and stale rejection, the mock contract, review edits, merge and split, stale jobs, cancellation, duplicate suppression, fixture rejection, the live capability probe, and this measurement. The mock backend is named `deterministic_mock` with `inference_kind` `mock_contract`. Those tests are not real inference.

Frontend: `SegmentationReviewForm.test.tsx` and the inspector test. Playwright: `tests/e2e/fv03_segmentation.spec.ts`.

## Boundary

Segmentation success would mean the backend executed and the technical validation passed. Clinical validity would require a reviewed identity method, which this checkpoint does not provide. Neither is claimed. `READY_FOR_SEGMENTATION` on the preparation record remains a technical preparation state, not a segmented tooth.
