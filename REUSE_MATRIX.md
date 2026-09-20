# External Reuse Matrix

This matrix must be reviewed **before** any external code/model is
integrated. Nothing below is integrated as a model or shipped with weights.
The MeshSegNet adapter boundary now contains an ONNX Runtime wrapper only;
it contains no external source code or model artifact.

| Component         | Repository                                                                 | Algorithm / Model                                                        | Purpose                                                             | License                                            | Direct Integration Allowed?                                                                   | Usage in AlignerStudio                                                 | Adapter Required                                                                     |
| ----------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| MeshSegNet        | https://github.com/Tai-Hsien/MeshSegNet                                    | Graph-constrained learning + point-based CNN for tooth mesh segmentation | Automatic per-tooth segmentation of intraoral scans                 | MIT code; weights license undocumented             | Adapter boundary prepared; model/weights still blocked pending legal + technical verification | Reference/model target only; no weights bundled                        | `adapters/meshsegnet` ONNX Runtime wrapper, no vendor source or weights              |
| ToothGroupNetwork | https://github.com/limhoyeon/ToothGroupNetwork                             | Point-cloud instance segmentation for individual teeth                   | Alternative/competing tooth segmentation approach                   | To be verified per current repo LICENSE before use | To be verified before integration; **not integrated in Phase 1**                              | Reference only for now                                                 | `adapters/toothgroupnet` (interface exists, implementation pending)                  |
| TANet             | (research reference — exact repository to be confirmed before integration) | Tooth arrangement / automatic setup network                              | Automatic tooth arrangement / setup generation                      | To be verified before integration                  | To be verified before integration; **not integrated in Phase 1**                              | Reference only for now                                                 | `adapters/tanet` (interface exists, implementation pending)                          |
| OpenSourceOrtho   | (research reference — exact repository to be confirmed before integration) | Various orthodontic planning utilities                                   | Potential reference for arch analysis / staging conventions         | To be verified before integration                  | To be verified before integration                                                             | Reference only for now                                                 | Not yet mapped to a specific adapter                                                 |
| Open3D            | https://github.com/isl-org/Open3D                                          | Mesh I/O, geometry processing                                            | Mesh validation/repair primitives                                   | MIT                                                | Yes, as a library dependency of `engines/geometry` (not a model, low IP risk)                 | Used directly (not behind an ML adapter) as a geometry utility library | N/A — used as a standard library dependency, wrapped by `engines/geometry` functions |
| trimesh           | https://github.com/mikedh/trimesh                                          | Mesh loading/analysis                                                    | Mesh validation (triangle counts, watertightness, degenerate faces) | MIT                                                | Yes, as a library dependency                                                                  | Used directly in Phase 1 `engines/geometry/mesh_validation.py`         | N/A — same as above                                                                  |

## Process for Adding a New External Component

1. Add a row to this table **before** writing any integration code.
2. Confirm the license explicitly (re-check the live repository; do not
   assume a license from memory).
3. Decide: reference-only vs. direct dependency vs. adapter-wrapped model.
4. If it touches domain logic or produces clinical output, it **must** go
   through an `adapters/*` package implementing an interface owned by the
   relevant `engines/*` package — never imported directly into `domain/` or
   `services/api`.
5. Never copy source files from an external repository into this codebase.
   Depend on it as a package/submodule/vendored-with-attribution artifact
   only after legal/license review.
