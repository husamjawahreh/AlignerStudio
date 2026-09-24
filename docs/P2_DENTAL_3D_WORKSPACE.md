# P2 Professional Dental 3D Workspace

## Scene graph

The existing review state now produces one `DentalSceneGraph` containing:

- original uploaded STL buffers by arch;
- the current segmented/proposed `ReviewStage`; and
- the authoritative `SceneLayerRegistry`.

The graph is passed to the existing `StageViewer`; no second renderer or case
store was introduced.

## Real-case geometry

Validated uploaded STL files are captured at the upload boundary and rendered
as their own Original Scan layer with Three.js `STLLoader`. Segmented
ToothInstanceNet meshes remain separate selectable meshes. Original geometry is
never synthesized from segmented teeth and is never silently substituted for a
missing model.

## Interaction and camera

The viewer supports orbit, pan, zoom, fit, reset, and occlusal/front/back/
left/right/upper/lower camera presets. Raycasting targets only segmented tooth
meshes. Selection updates material/emissive state and labels through refs, so
selection does not rebuild the scene graph.

## Visual states

Upper/lower materials are distinct, selected teeth receive an emissive gold
highlight, and original scans use translucent arch-specific materials with an
opacity control. Experimental and fixture provenance remains visible outside
clinical claims.

## Performance decisions

No BVH dependency was added in P2. Three.js raycasting remains the current
implementation because the real-case interaction path is now explicit and
should be profiled before adding spatial acceleration. Replaced geometries and
materials are disposed during viewer cleanup. STL parsing occurs only when the
scene graph or original-layer inputs change, not in the animation loop.

## Known limits

- Gingiva/base, proposed setup overlays, contacts, collisions, attachments,
  and measurements remain unavailable until their API geometry contracts exist.
- The original scan buffer is kept in frontend state for the active case; a
  future API scene endpoint should replace this with a streamed/cacheable
  asset path for very large scans.
- ToothInstanceNet remains behind its existing adapter and its validated
  artifact remains experimental, not clinically validated.
