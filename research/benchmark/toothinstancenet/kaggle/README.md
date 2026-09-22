# ToothInstanceNet Kaggle FREE-GPU Benchmark

Research-only harness for `3dteethland` / ToothInstanceNet. It does not modify
AlignerStudio production code, the clinical pipeline, the `model_unavailable`
fail-closed behavior, adapters, or canonical STL files. It runs inference only,
does not train, and does not call any external VLM or API.

## Kaggle datasets

Attach two Kaggle datasets:

1. `alignerstudio-real-case`, containing:
   - `upper.stl`
   - `lower.stl`
2. `toothinstancenet-checkpoints`, containing the already verified:
   - `align.ckpt`
   - `instseg_full.ckpt`
   - `landmarks_full.ckpt`

The notebook expects these at `/kaggle/input/alignerstudio-real-case/` and
`/kaggle/input/toothinstancenet-checkpoints/`. Do not upload production source
or secrets. The checkpoint hashes are recorded in the prior benchmark record
and rechecked by the notebook.

Canonical input hashes:

```text
upper.stl  60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48
lower.stl  dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b
```

## Upstream source

The notebook clones:

```text
https://github.com/nnistelrooij/3dteethland
commit 424252e3d94a1565c8c2090eb5bb456b76386b93
```

It installs the upstream package with `pip install -v -e .`, which builds the
required CUDA kernels. The upstream README documents Python 3.10, PyTorch 2.3.0,
CUDA 12.1, PyTorch Lightning 2.3.3, and compiled pointops-related extensions.
Kaggle's preinstalled CUDA/PyTorch must be compatible; the harness does not
change the architecture or substitute CPU implementations.

## Run

Open `benchmark_toothinstancenet.ipynb`, enable a Kaggle GPU accelerator, attach
the two datasets, and run cells in order. The notebook uses working copies only
and writes results under:

```text
/kaggle/working/toothinstancenet-benchmark/
```

The standalone equivalent is:

```bash
python run_benchmark.py \
  --repo /kaggle/working/3dteethland \
  --input-dir /kaggle/input/alignerstudio-real-case \
  --checkpoints /kaggle/input/toothinstancenet-checkpoints \
  --work-dir /kaggle/working/toothinstancenet-benchmark
```

The runner invokes the audited upstream instance pipeline exactly as:

```bash
python infer.py instances --devices 1 --config <temporary-research-config>
```

This is the primary segmentation stage. It loads `align.ckpt` for the optional
alignment stage, `instseg_full.ckpt` for instance embeddings/cluster masks and
FDI classification, and `landmarks_full.ckpt` for the secondary landmark head
used by the full model path. The runner hard-fails if the output does not
contain both per-vertex `instances` and `labels` arrays.

The upstream README says `.stl`, `.ply`, and `.obj` are accepted and expects
`STEM_upper`/`STEM_lower` naming for FDI handling. This harness preserves the
required user-facing working names `CASE_upper.stl` and `CASE_lower.stl`, and
creates separate `STEM_*` research aliases for the upstream filename-based
jaw detection. Raw outputs are copied to the requested `CASE_*` names.

Outputs:

- `benchmark-report.json`
- `benchmark-summary.md`
- raw upstream JSON outputs
- `*__kpt.json` landmark files when produced
- raw visualization meshes when produced

## Correspondence policy

The report treats the upstream representation as original-mesh vertex index
space only when the exact source path is present: `TeethSegDataset` loads all
mesh vertices, `UniformDensityDownsample(inplace=False)` keeps the full point
tensor, and `FullNet.single_tooth_stage` interpolates predictions back to `x`
before `save_segmentation` writes `instances` and `labels`. It also checks both
array lengths and emitted mesh topology. A nearest/registered mapping is not
used unless a future raw output contradicts this proof; then it must remain a
clearly labeled research fallback in the Kaggle working directory.

## Blockers and safety

A CUDA, kernel, dependency, checkpoint, or input-contract failure is recorded
in `FAILURES` and stops interpretation. Do not alter the model architecture,
install CUDA into production, use a VLM/API, train, or claim clinical validity.

After a benchmark, run the existing local production checks from the repository
root:

```bash
source services/api/.venv/bin/activate
pytest -q
pnpm -r test
sha256sum data/benchmark/real-case/upper.stl data/benchmark/real-case/lower.stl
```

Expected current suite: 86 Python tests and 22 TypeScript tests. The final hash
check must match the canonical values above.

## Real-case artifact generation

The current developer environment does not contain the validated real-case
artifact and must not fabricate one. In the validated Kaggle GPU environment,
run the existing real inference runner first, then generate the package only
from its raw `CASE_upper.json`/`CASE_lower.json` outputs and actual upstream
correspondence NPZ files:

```bash
python research/benchmark/toothinstancenet/kaggle/generate_real_case_artifact.py \
   --input-dir /kaggle/input/datasets/husamjawahreh/alignerstudio-real-case \
   --prediction-dir /kaggle/working/toothinstancenet-benchmark \
   --output-dir /kaggle/working/toothinstancenet-real-case-artifact \
   --checkpoint /kaggle/input/datasets/husamjawahreh/toothinstancenet-checkpoints/instseg_full.ckpt \
   --source /kaggle/working/3dteethland \
   --selected-mapping /kaggle/working/toothinstancenet-benchmark/selected_to_original_vertex_mapping.npz \
   --instseg-coordinates /kaggle/working/toothinstancenet-benchmark/exact_instseg_coordinates.npz
```

Audit independently:

```bash
python research/benchmark/toothinstancenet/kaggle/audit_real_case_artifact.py \
   --artifact-dir /kaggle/working/toothinstancenet-real-case-artifact \
   --input-dir /kaggle/input/datasets/husamjawahreh/alignerstudio-real-case \
   --checkpoint-sha256 100c68a9b120402cc75539eff6347bd998bce8b1d4f01550638f471797d70803
```

Package only after the independent audit passes:

```bash
bash research/benchmark/toothinstancenet/kaggle/package_real_case_artifact.sh \
   /kaggle/working/toothinstancenet-real-case-artifact \
   /kaggle/working/toothinstancenet-real-case-artifact.zip
```

Use the unpacked artifact in development only through the explicit
`ALIGNERSTUDIO_SEGMENTATION_BACKEND=toothinstancenet_fixture` and
`ALIGNERSTUDIO_TOOTHINSTANCENET_VALIDATED_FIXTURE_DIR` settings. No automatic
matching or fallback is permitted.
