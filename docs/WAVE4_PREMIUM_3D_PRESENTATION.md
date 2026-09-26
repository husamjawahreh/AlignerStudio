# Wave 4 — Premium 3D presentation

**Date:** 2026-09-26  
**Verdict:** PASS WITH BLOCKER  
**Live ToothInstanceNet inference:** no. This host remains **BLOCKED_BY_ENVIRONMENT**.

This document describes the viewport presentation layer. It is visualization only. It does not claim enamel physics, patient gingiva, clinical numbering, or an approved treatment.

## Visual language

The viewport reads in this order:

1. Tooth and arch geometry
2. Selection and hover
3. Workflow context (current arch, fixture or blocked status)
4. Technical metadata only in the inspector or an opened unavailable list

The studio background is a single neutral gray, `#243038`. There is no fog and no per-step background change. Effects exist for selection, hover, current versus target, validation severity, arch separation, and camera framing. There is no bloom, neon outline, or flashing.

## Material architecture

One profile object, `dentalMaterialProfiles`, feeds every tooth and gingiva material. Profiles contain only material fields. They do not contain vertices, faces, or movement.

Current enamel is warm ivory, roughness about 0.40–0.46, metalness 0.02, and environment intensity about 0.42–0.50. That keeps mesh shading without a plastic highlight. Upper enamel is slightly warmer than lower enamel so the arches separate. These values are not a measurement of enamel.

Selected teeth use a warmer ivory and an emissive intensity of 0.18. Hover keeps the base color and uses emissive intensity 0.05. Multi-selection uses the selected profile at 0.7 of that emissive intensity. Validation fail and warning tint the emissive channel only. They do not replace the tooth color with a status wash.

Target geometry uses a cool gray-blue at opacity 0.68. Current geometry stays opaque ivory. The cool color is not a pass or an approval. The ghost comparison overlay uses the same cool family at opacity 0.55. If no treatment target is stored, the overlay is not drawn.

## Lighting

`installDentalStudioLighting` builds the lights once, in scene space:

- Hemisphere, intensity 0.72, warm sky and mid ground
- Key directional, intensity 1.28, soft shadow map
- Fill, rim, and bounce at 0.52, 0.26, and 0.20

Orbit does not move the lights. Fit recenters the key shadow frustum on the case bounds so the shadow stays on the geometry. Tone mapping is ACES at exposure 1. A RoomEnvironment map is still used, at low material intensity, so reflections stay controlled. Browser lighting is not used.

Occlusal, upper, and lower directions stay off the world-up axis (`stableViewDirection`). A camera placed exactly on +Y with the default up vector rolls and hides the occlusal plane.

## Gingiva

`resolveGingivaPresentation` prefers usable real gingiva meshes. Otherwise it builds a synthetic cervical band. Every mesh from that module has `presentationOnly: true` and `clinicalGeometry: false` on the Three.js object. Synthetic gingiva is not copied into clinical payloads.

The synthetic material is a muted rose, roughness 0.76, opacity 0.82, with polygon offset so the band does not z-fight the crowns. It is a spatial cue. It is not patient anatomy. Crown-only meshes are not given roots.

## Labels

Modes cycle: selected, arch, all, off. The default is selected.

Priority is selected, then hovered, then multi-selected, then other visible teeth only in arch or all mode. Arch mode labels the visible teeth only when one arch is isolated. Above 16 visible teeth, non-priority labels stay hidden.

Text comes from `toothReviewLabel`. FDI is shown only when `fdiIsAuthoritative` is true. Fixture and experimental identity stay on `tooth_ref`, with a dashed unresolved chip. Labels are anchored to the tooth centroid and sit above it. Label mode changes DOM visibility only. It does not rebuild geometry or the BVH.

## Selection and camera

Hover is a light preselection. Selection is the stronger persistent state. Multi-selection uses the same warm family. Ordinary selection does not move the camera. Fit case, fit arch, fit selection, presets, and reset are explicit commands.

Framing uses the vertical field of view. At 42°, case fill 0.74, arch fill 0.78, and selection fill 0.86. The bounding sphere stays inside the frame with a margin. Case fit uses visible meshes, so a hidden arch does not inflate the frame. Reset fits the case. It does not jump to a fixed world position.

The scene graph remains `createCaseSceneHierarchy`: CaseRoot, upper, lower, treatment, occlusion, validation, measurement, and reference. Wave 4 does not add a second graph.

## Overlays

Validation and measurement capabilities stay unavailable in `WORKSPACE_OVERLAY_CAPABILITIES`. `validationOverlayPresentation` does not draw when the capability or the finding is absent, and `impliesApproval` is always false. A fail or warning may draw only when a finding is actually stored. `measurementOverlayPresentation` draws only when a measurement exists. Units are shown when known; otherwise the label is `model-space units (unverified)`. No distances, IPR, attachments, or axes are invented.

## Rendering-only preprocessing

Vertex normals are computed on a `BufferGeometry` built from a copied position buffer. Source vertex arrays are not written. Gingiva materials set `polygonOffset` so the cervical band does not flicker against teeth. Offsets are not written back to geometry and do not enter validation, collision, or treatment.

## Performance

Selection, hover, arch visibility, and label mode update materials, group visibility, or DOM. They do not rebuild `BufferGeometry` or the BVH, and they do not recompute vertex positions. Lighting is created with the scene. Two thousand style, label, and framing resolutions stay under 80 ms in the Wave 4 unit test. The existing WP-12 probe still reports arch-filter application at about 0.36 ms for 8 fixture teeth, with no geometry rebuild. Browser notes in `.research/tmp/wave4_browser_qa/evidence.json` include Playwright settle time and the camera transition. They are script timings, not scene-update timings.

## Browser evidence

Playwright screenshots and `evidence.json` are in `.research/tmp/wave4_browser_qa/`. Viewports are 1366×768 and 1600×1000.

Those images are presentation evidence. Fixture crowns are generated test meshes. Blocked shots have no canvas and are not a tooth count of zero. No patient STL was loaded. None of the images are clinical segmentation validation.

## Known limitations

- Live ToothInstanceNet inference did not run. The runtime blocker is unchanged: no NVIDIA driver, torch, or pointops on this host.
- No persisted patient scan was available for the browser pass, so 3D shots use fixture crowns.
- Current versus target comparison is implemented in the material profiles and is not drawn when no treatment target is stored.
- 3D validation and measurement overlays stay unavailable. Absence is not shown as safe.
- Synthetic gingiva follows the cervical band of the meshes it is given. On simple fixture crowns that band is a presentation envelope, not anatomy.
- WP-14 and WP-15 were not started. Wave 5 and later were not started.
