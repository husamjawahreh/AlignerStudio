#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../../../../" && pwd)"
source_dir="${ALIGNERSTUDIO_TOOTHINSTANCENET_SOURCE:?Set this to the exact local 3dteethland checkout}"
expected='424252e3d94a1565c8c2090eb5bb456b76386b93'
actual="$(git -C "$source_dir" rev-parse HEAD)"
if [[ "$actual" != "$expected" ]]; then
  echo "source revision mismatch: $actual != $expected" >&2
  exit 2
fi

context="$(mktemp -d)"
trap 'rm -rf "$context"' EXIT
cp "$repo_root/research/benchmark/toothinstancenet/runtime/Dockerfile" "$context/Dockerfile"
cp "$repo_root/research/benchmark/toothinstancenet/runtime/requirements-runtime.txt" "$context/requirements-runtime.txt"
cp "$repo_root/research/benchmark/toothinstancenet/runtime/runtime-manifest.py" "$context/runtime-manifest.py"
cp "$repo_root/research/benchmark/toothinstancenet/run_acceptance.py" "$context/run_acceptance.py"
cp -a "$repo_root/adapters" "$context/adapters"
cp -a "$repo_root/domain" "$context/domain"
cp -a "$repo_root/engines" "$context/engines"
cp -a "$source_dir" "$context/source"

cd "$context"
echo 'Executing: docker build -t alignerstudio-toothinstancenet:validated .'
docker build -t alignerstudio-toothinstancenet:validated .
