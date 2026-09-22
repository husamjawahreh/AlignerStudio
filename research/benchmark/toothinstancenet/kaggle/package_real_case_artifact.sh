#!/usr/bin/env bash
set -euo pipefail

artifact_dir="${1:?usage: package_real_case_artifact.sh ARTIFACT_DIR OUTPUT_ZIP}"
output_zip="${2:?usage: package_real_case_artifact.sh ARTIFACT_DIR OUTPUT_ZIP}"

case "$artifact_dir" in
  */toothinstancenet-real-case-artifact|*/toothinstancenet-real-case-artifact/)
    ;;
  *)
    echo "Refusing to package an unrecognized artifact directory: $artifact_dir" >&2
    exit 2
    ;;
esac

for required in artifact-manifest.json instance_fdi_mapping.json final_instance_audit.json mesh_manifest.json selected_to_original_vertex_mapping.npz exact_instseg_coordinates.npz alignerstudio_toothinstancenet_integration_spec.json alignerstudio_toothinstancenet_implementation_contract.json upper.json lower.json upper/CASE_upper.json lower/CASE_lower.json; do
  test -f "$artifact_dir/$required" || { echo "missing artifact file: $required" >&2; exit 2; }
done

mkdir -p "$(dirname "$output_zip")"
rm -f "$output_zip"
(cd "$artifact_dir/.." && zip -qr "$output_zip" "$(basename "$artifact_dir")")
echo "$output_zip"
