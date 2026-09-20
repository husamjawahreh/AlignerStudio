# TGNet / ToothGroupNetwork Checkpoint and Rights Gate

**Research only. No inference was run. No CUDA was installed.**

## 1. Repository

- Official repository: <https://github.com/limhoyeon/ToothGroupNetwork>
- Exact audited commit: `d7e16a4b8fca811975c3a4c7c1429bb0a51b3083`
- External checkout: `~/.cache/alignerstudio-research/model-discovery/ToothGroupNetwork`
- Repository license: no `LICENSE` file and GitHub license metadata is `null`.
- Production repository was not used for the checkout or checkpoint.

## 2. Official Checkpoint Source

The README at the audited commit says:

> All of the checkpoint files for each model are in the Google Drive folder.
> Download `ckpts(new).zip` and unzip all of the checkpoints.

Official folder:

<https://drive.google.com/drive/folders/15oP0CZM_O_-Bir18VbSM8wRUEzoyLXby?usp=sharing>

The folder metadata identifies:

- filename: `ckpts(new).zip`
- Google Drive file ID: `1Xpw9vYbDVwoafVohqY0aMen2iMCx053-`
- resolved download URL:
  `https://drive.usercontent.google.com/download?id=1Xpw9vYbDVwoafVohqY0aMen2iMCx053-&export=download&confirm=t`

The archive was downloaded only to:

```text
~/.cache/alignerstudio-research/toothgroupnetwork/ckpts(new).zip
```

Archive facts:

- size: `156,866,803` bytes
- SHA-256:
  `c1db3f163791b017be7559039c774d7d4fc11fb0367106cb0625ff6e82bf5c36`

## 3. Extracted Checkpoints

Extracted only under:

```text
~/.cache/alignerstudio-research/toothgroupnetwork/extracted/
```

| File | Size | SHA-256 | Role |
| --- | ---: | --- | --- |
| `tgnet_fps.h5` | 64,037,327 | `024f585f20924c08eafced8fdc633015b0cc8bba04301d585b4cf7a0c02206b6` | TGNet FPS stage |
| `tgnet_bdl.h5` | 511,103 | `5ec7780d7d645af522c6f2888093e5ca8e11c631d0e13798d208ba2a157554d1` | TGNet boundary stage |
| `dgcnn.h5` | 3,980,231 | `28f2c752755c543afd7642288a0f916c6663889a32caa847704522a07331e713` | DGCNN |
| `pointnet.h5` | 37,216,127 | `04a8089df2a473de4907895c67b3226b15a1a92720e22044dfc10ece0b4ad4be` | PointNet |
| `pointnetpp.h5` | 35,963,823 | `09d2f8b14e97584a2baf56a7680290e7723ea4956433c0eebd0c9023c5a15de2` | PointNet++ |
| `pointtransformer.h5` | 32,024,895 | `0aa9909b04ac9783e63b27b330e8e2480de4afb345c3b300e60b720c1e943a87` | PointTransformer |
| `tsegnet.h5` | 9,720,607 | `f0201fe1856187adf92ee621b07e574cb5ffa648d228f152414daa104aab0622` | TSegNet |
| `tsegnet_centroid.h5` | 3,405,743 | `2f7ced72d573db8447e6caa972f211ca65e1e4834cebbd68a44a5bd40ef2620f` | TSegNet centroid stage |

## 4. Configuration Compatibility

The official TGNet inference entry point is `start_inference.py`. The
corresponding command shape is:

```text
python start_inference.py \
  --input_dir_path <OBJ_PARENT> \
  --split_txt_path <TEST_SPLIT> \
  --save_path <OUTPUT> \
  --model_name tgnet \
  --checkpoint_path <PATH_WITHOUT_.h5> \
  --checkpoint_path_bdl <PATH_WITHOUT_.h5>
```

The exact-commit loader appends `.h5`, so the extracted files correspond to:

```text
--checkpoint_path ~/.cache/alignerstudio-research/toothgroupnetwork/extracted/tgnet_fps
--checkpoint_path_bdl ~/.cache/alignerstudio-research/toothgroupnetwork/extracted/tgnet_bdl
```

The documented TGNet configuration is:

- FPS stage: `input_feat=6`, `stride=[1,4,4,4,4]`,
  `nsample=[36,24,24,24,24]`, `blocks=[2,3,4,6,3]`,
  `planes=[32,64,128,256,512]`, `crop_sample_size=3072`;
- boundary stage: `input_feat=6`, `stride=[1,1]`, `nsample=[36,24]`,
  `blocks=[2,3]`, `planes=[16,32]`, `crop_sample_size=3072`;
- boundary sampling: `num_of_bdl_points=20000`,
  `num_of_all_points=24000`.

**Compatibility result:**

- filename-level compatibility: **confirmed**;
- README/inference-path compatibility: **confirmed**;
- tensor-level `load_state_dict` compatibility: **not tested** because the
  current research environment has no PyTorch and CUDA installation is
  prohibited by this gate;
- architecture was not modified to force a load.

## 5. Rights and Usage Review

### ToothGroupNetwork

No repository license file or GitHub license metadata was found. The README
contains usage instructions but no commercial, model-weight, or redistribution
grant.

### Checkpoint archive

The archive is author-linked through the official README and Google Drive
folder. No explicit checkpoint license, commercial permission, or redistribution
terms were visible in the repository or folder metadata. The archive is not
being redistributed and remains in the external research cache.

### Referenced 3DTeethSeg / Teeth3DS data

The referenced challenge repository is:

<https://github.com/abenhamadou/3DTeethSeg22_challenge>

Its audited repository commit was `d03b8c644239980bbc779c6cb58b42fb02204916`.
The repository states:

- dataset: **CC BY-NC-ND 4.0**;
- non-data repository code: **MIT**.

The dataset’s non-commercial/no-derivatives terms are separate from the
repository code and separate from TGNet checkpoint rights. Dataset access does
not establish commercial model-weight rights.

**Usage classification: `RESEARCH_ONLY`**

This classification permits retaining the artifact for the requested isolated
engineering benchmark, subject to the rightsholder’s terms. It does not clear
commercial deployment, redistribution, or training on the referenced dataset.

## 6. Canonical Input Compatibility

Canonical files remain unmodified:

| Jaw | Path | SHA-256 | Size |
| --- | --- | --- | ---: |
| Upper | `data/benchmark/real-case/upper.stl` | `60aaafed87818b7cffd904056c4055748692bc280069af16325bff3b446e5a48` | 8,557,034 |
| Lower | `data/benchmark/real-case/lower.stl` | `dc4f8b0d4e8d1c21ab45ee0e69457eb575b869bcd895fbda36de9fcb4387037b` | 6,954,234 |

The official input contract requires:

- OBJ, not documented direct STL;
- `casename_upper.obj` and `casename_lower.obj` naming;
- Y axis pointing toward the back;
- same Z direction convention for upper and lower jaws;
- research preprocessing to create farthest-point sampled vertices;
- TGNet inference path using 24,000 total points, with 20,000 boundary
  points and 3,072-point crop processing.

No STL conversion was performed. A future benchmark must create external
working OBJ copies, preserve a source-to-OBJ mapping, and verify axis
orientation before inference.

### Sampling and correspondence

The TGNet inference code:

1. loads and de-duplicates the OBJ mesh;
2. normalizes coordinates;
3. subdivides meshes below the relevant point count for the boundary stage;
4. samples 24,000 points with FPS;
5. predicts instance and semantic labels on sampled points;
6. transfers labels to original vertices with nearest-neighbor lookup; and
7. asserts that the returned label arrays have the original vertex count.

This makes deterministic original-vertex label reconstruction plausible. It
does not yet prove that challenge JSON indexes, source faces, or mixed-label
faces can be reconstructed without ambiguity. That requires a future isolated
run. No conversion or inference was started here.

## 7. Hardware Feasibility

Current host:

- NVIDIA driver: unavailable (`nvidia-smi` fails);
- NVIDIA GPU: unavailable;
- `nvcc`: not found;
- PyTorch/CUDA/pointops: not installed.

Current-machine execution is therefore **BLOCKED**.

The README documents a PyTorch 1.7.1 CUDA 11.0 environment, custom pointops,
Open3D, and batch size one with a minimum 11 GB GPU RAM. It also warns about
RTX40-series issues.

| Target | Assessment | Basis |
| --- | --- | --- |
| Current machine | **BLOCKED** | No GPU, driver, nvcc, or CUDA stack |
| Cloud GPU, 16 GB | **POSSIBLE** | Exceeds documented 11 GB minimum; CUDA 11.0 and pointops compatibility remain prerequisites |
| Cloud GPU, 24 GB | **POSSIBLE** | More headroom than documented minimum; older CUDA-compatible GPU may reduce RTX40 compatibility risk |

No environment was installed and no cloud resource was created.

## 8. Remaining Blockers Before Inference

1. Tensor-level checkpoint load validation on a compatible isolated CUDA
   environment.
2. Rights review for the checkpoint archive and any planned use beyond the
   internal research benchmark.
3. External STL-to-OBJ working-copy conversion with auditable correspondence.
4. Axis/orientation validation against the TGNet convention.
5. Empirical validation of JSON index semantics and original-face mapping.
6. No inference, training, adapter creation, production modification, or gate
   change is authorized by this checkpoint gate.

## Final Gate Result

CHECKPOINT:
available

CHECKPOINT HASH:
c1db3f163791b017be7559039c774d7d4fc11fb0367106cb0625ff6e82bf5c36

USAGE STATUS:
RESEARCH_ONLY

INFERENCE READY:
NO

CURRENT MACHINE:
BLOCKED

CLOUD GPU:
POSSIBLE

RECOMMENDATION:
PROCEED TO ISOLATED BENCHMARK

Machine-readable record:
[research/benchmark/toothgroupnetwork/checkpoint-gate.json](../research/benchmark/toothgroupnetwork/checkpoint-gate.json)
