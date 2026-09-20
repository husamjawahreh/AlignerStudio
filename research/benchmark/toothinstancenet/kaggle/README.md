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

The upstream README says `.stl`, `.ply`, and `.obj` are accepted and expects
`STEM_upper`/`STEM_lower` naming for FDI handling. This harness preserves the
required user-facing working names `CASE_upper.stl` and `CASE_lower.stl`; the
runner must record any upstream naming alias needed by the exact data loader
rather than silently claiming the names are equivalent.

Outputs:

- `benchmark-report.json`
- `benchmark-summary.md`
- raw upstream JSON outputs
- `*__kpt.json` landmark files when produced
- raw visualization meshes when produced

## Correspondence policy

The report compares prediction label cardinality, indices, and coordinates with
the original STL vertices/faces. It must distinguish original-vertex output
from sampled-point output. If the raw output contains sampled coordinates but
not original indices, an isolated nearest/registered vertex mapping may be
implemented in the Kaggle working directory only. No mapping is added to
AlignerStudio production.

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
