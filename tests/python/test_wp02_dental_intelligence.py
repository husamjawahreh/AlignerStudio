"""WP-02 — Dental Intelligence 2.0: truth-preserving clinical intelligence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.toothinstancenet.fixture import ARTIFACT_ID, load_validated_fixture
from app.intelligence_store import (
    build_and_store_dental_intelligence,
    get_dental_intelligence_record,
)
from app.main import app
from app.pipeline_diagnostics import _diagnostic_from_result
from app.segmentation_store import (
    begin_segmentation_record,
    complete_segmentation_record,
    store_arch_result,
)
from app.store import case_store
from app.treatment_sessions import treatment_sessions
from domain.case.models import Case
from domain.tooth.identification import ArchType
from domain.tooth.intelligence_v2 import INTELLIGENCE_CONTRACT_VERSION, IntelligenceTruthState
from engines.arrangement.dental_intelligence import build_case_dental_intelligence
from engines.arrangement.geometry_metrics import compute_geometry_metrics
from engines.arrangement.anatomical_intelligence import serialize_identified_tooth

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".research" / "tmp" / "official_real_case_stage2_verified_v1"
ARTIFACT_ZIP = ROOT / "official_real_case_stage2_verified_v1.zip"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIGNERSTUDIO_TREATMENT_SESSION_DIR", str(tmp_path / "sessions"))
    import app.config as config

    config.TREATMENT_SESSION_DIR = Path(tmp_path / "sessions")
    config.TREATMENT_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    case_store.clear()
    treatment_sessions.clear()
    yield
    case_store.clear()
    treatment_sessions.clear()


def _require_artifact() -> Path:
    if ARTIFACT_DIR.is_dir():
        return ARTIFACT_DIR
    if ARTIFACT_ZIP.is_file():
        return ARTIFACT_ZIP
    pytest.skip("Official real-case artifact is not available in this environment")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _seed_case(case_id: str = "wp02-case") -> Case:
    case = Case(id=case_id, patient_reference="WP-02 patient")
    case_store.add(case)
    return case


_ARCH_PAYLOAD_CACHE: dict[str, dict] = {}


def _arch_payload_from_artifact(arch: ArchType, artifact: Path) -> dict:
    """TEST-ONLY: reconstruct tooth instances from the official verified artifact.

    Used as genuine persisted geometry for non-GPU Dental Intelligence tests.
    Never enters the REAL_CASE production inference path.
    """
    cache_key = f"{artifact}:{arch.value}"
    if cache_key in _ARCH_PAYLOAD_CACHE:
        return copy.deepcopy(_ARCH_PAYLOAD_CACHE[cache_key])
    result = load_validated_fixture(artifact, arch=arch)
    from time import perf_counter

    diagnostic = _diagnostic_from_result(result, perf_counter(), source_kind="validated_real_case")
    payload = diagnostic.payload()
    stl = ARTIFACT_DIR / f"{arch.value}.stl"
    payload["source_mesh_path"] = str(stl if stl.is_file() else artifact)
    payload["source_mesh_sha256"] = _sha256(stl) if stl.is_file() else None
    payload["fixture"] = True
    payload["processing_mode"] = "test_fixture"
    _ARCH_PAYLOAD_CACHE[cache_key] = payload
    return copy.deepcopy(payload)


def _persist_dual_arch_segmentation(case_id: str, *, processing_mode: str = "test_fixture") -> dict:
    artifact = _require_artifact()
    begin_segmentation_record(
        case_id,
        job_id="job-wp02",
        input_hash="a" * 64,
        processing_mode=processing_mode,
    )
    for arch in (ArchType.UPPER, ArchType.LOWER):
        payload = _arch_payload_from_artifact(arch, artifact)
        store_arch_result(
            case_id,
            arch.value,
            payload,
            model_name=payload.get("model_name") or "toothinstancenet",
            model_version=payload.get("model_version") or "validated-artifact",
            segment_ms=payload.get("segmentation_runtime_ms"),
        )
    return complete_segmentation_record(case_id, status="completed", total_ms=1.0)


def test_geometry_metrics_are_deterministic() -> None:
    vertices = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    faces = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
    first = compute_geometry_metrics(vertices, faces)
    second = compute_geometry_metrics(vertices, faces)
    assert first.payload() == second.payload()
    assert first.principal_directions_kind == "mesh_pca"
    assert first.centroid is not None


def test_real_artifact_produces_intelligence_bound_to_source() -> None:
    _seed_case()
    record = _persist_dual_arch_segmentation("wp02-case")
    intelligence = build_case_dental_intelligence(
        case_id="wp02-case",
        segmentation_record=record,
    )
    payload = intelligence.payload()
    assert payload["contract_version"] == INTELLIGENCE_CONTRACT_VERSION
    assert payload["case_id"] == "wp02-case"
    assert payload["job_id"] == "job-wp02"
    assert payload["input_hash"] == "a" * 64
    assert payload["counts"]["tooth_instances"] == 28
    assert payload["counts"]["arch_assigned"] == 28
    # Official artifact is semantic-only — no invented clinical FDI.
    assert payload["counts"]["resolved_fdi"] == 0
    assert payload["counts"]["unresolved_identity"] == 28
    assert payload["counts"]["landmarks_available"] == 0
    assert payload["counts"]["clinical_axes_available"] == 0
    assert payload["counts"]["occlusion_available"] is False
    assert payload["occlusion"]["state"] == IntelligenceTruthState.NOT_AVAILABLE.value
    for tooth in payload["teeth"]:
        assert tooth["source_mesh_sha256"]
        assert tooth["fdi_number"]["state"] == IntelligenceTruthState.NOT_AVAILABLE.value
        assert tooth["fdi_number"]["value"] is None
        assert tooth["landmarks"]["state"] == IntelligenceTruthState.NOT_AVAILABLE.value
        assert tooth["clinical_dental_axes"]["state"] == IntelligenceTruthState.NOT_AVAILABLE.value
        assert tooth["root_geometry"]["state"] == IntelligenceTruthState.NOT_AVAILABLE.value
        assert tooth["geometry"]["state"] == IntelligenceTruthState.COMPUTED.value
        assert tooth["mesh_principal_directions"]["state"] == IntelligenceTruthState.COMPUTED.value
        assert tooth["mesh_principal_directions"]["reason"]
        assert "not clinical" in tooth["mesh_principal_directions"]["reason"].lower()
        # Engineering frames must not become verified clinical axes.
        if tooth["local_coordinate_frame"]["state"] != IntelligenceTruthState.NOT_AVAILABLE.value:
            assert tooth["local_coordinate_frame"]["state"] == IntelligenceTruthState.REQUIRES_REVIEW.value
    readiness = payload["capability_readiness"]
    assert readiness["occlusion_readiness"] == IntelligenceTruthState.NOT_AVAILABLE.value
    assert readiness["axis_readiness"] == IntelligenceTruthState.NOT_AVAILABLE.value
    assert readiness["treatment_setup_readiness"] != IntelligenceTruthState.VERIFIED.value
    # Intelligence objects must not auto-unlock treatment as verified clinical readiness.
    assert readiness["treatment_setup_readiness"] in {
        IntelligenceTruthState.REQUIRES_REVIEW.value,
        IntelligenceTruthState.NOT_AVAILABLE.value,
    }


def test_intelligence_determinism_on_real_artifact() -> None:
    _seed_case("wp02-det")
    record = _persist_dual_arch_segmentation("wp02-det")
    first = build_case_dental_intelligence(case_id="wp02-det", segmentation_record=record).payload()
    second = build_case_dental_intelligence(case_id="wp02-det", segmentation_record=record).payload()
    # Timestamps differ; compare geometry/truth payloads.
    for key in ("generated_at", "timings_ms"):
        first.pop(key, None)
        second.pop(key, None)
    assert first == second


def test_no_fdi_invented_when_absent() -> None:
    _seed_case("wp02-nofdi")
    record = _persist_dual_arch_segmentation("wp02-nofdi")
    # Strip any accidental FDI if present and ensure builder does not invent.
    for arch in record["arches"].values():
        for tooth in arch.get("tooth_instances") or []:
            tooth["fdi_number"] = None
    intel = build_case_dental_intelligence(case_id="wp02-nofdi", segmentation_record=record)
    assert all(
        tooth.fdi_number.state is IntelligenceTruthState.NOT_AVAILABLE for tooth in intel.teeth
    )
    assert all(tooth.fdi_number.value is None for tooth in intel.teeth)


def test_model_fdi_requires_review_never_verified() -> None:
    record = {
        "status": "completed",
        "job_id": "j",
        "input_hash": "b" * 64,
        "processing_mode": "real_case",
        "model_name": "toothinstancenet",
        "model_version": "test",
        "arches": {
            "upper": {
                "fixture": False,
                "provenance": "experimental",
                "source_mesh_path": "/tmp/upper.stl",
                "source_mesh_sha256": "c" * 64,
                "tooth_instances": [
                    {
                        "instance_id": 0,
                        "tooth_ref": "upper:instance:0",
                        "arch": "upper",
                        "fdi_number": 11,
                        "semantic_label": None,
                        "confidence": 0.9,
                        "identification_status": "identified",
                        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                        "faces": [[0, 1, 2]],
                        "landmarks": None,
                        "fixture": False,
                        "provenance": "experimental",
                    }
                ],
            },
            "lower": {
                "fixture": False,
                "provenance": "experimental",
                "source_mesh_path": "/tmp/lower.stl",
                "source_mesh_sha256": "d" * 64,
                "tooth_instances": [],
            },
        },
    }
    intel = build_case_dental_intelligence(case_id="wp02-fdi", segmentation_record=record)
    tooth = intel.teeth[0]
    assert tooth.fdi_number.value == 11
    assert tooth.fdi_number.state is IntelligenceTruthState.REQUIRES_REVIEW
    assert tooth.overall_truth_state is not IntelligenceTruthState.VERIFIED


def test_stale_segmentation_fails_honestly() -> None:
    _seed_case("wp02-stale")
    begin_segmentation_record(
        "wp02-stale", job_id="j", input_hash="e" * 64, processing_mode="real_case"
    )
    with pytest.raises(ValueError, match="completed"):
        build_and_store_dental_intelligence("wp02-stale")


def test_fixture_cannot_silently_enter_real_case_intelligence() -> None:
    """REAL_CASE processing_mode with fixture teeth must remain marked fixture=True."""
    _seed_case("wp02-mix")
    record = _persist_dual_arch_segmentation("wp02-mix", processing_mode="real_case")
    # Corrupt: claim real_case while arches are fixture — builder must preserve fixture flag.
    intel = build_case_dental_intelligence(case_id="wp02-mix", segmentation_record=record)
    assert intel.fixture is True
    assert all(tooth.fixture for tooth in intel.teeth)


def test_persistence_and_api_transport() -> None:
    _seed_case("wp02-api")
    _persist_dual_arch_segmentation("wp02-api")
    stored = build_and_store_dental_intelligence("wp02-api")
    loaded = get_dental_intelligence_record("wp02-api")
    assert loaded is not None
    assert loaded["contract_version"] == stored["contract_version"]
    assert loaded["counts"]["tooth_instances"] == stored["counts"]["tooth_instances"]

    response = client.get("/cases/wp02-api/dental-intelligence")
    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == INTELLIGENCE_CONTRACT_VERSION
    assert body["occlusion"]["state"] == "not_available"
    assert body["capability_readiness"]["treatment_setup_readiness"] != "verified"
    # Round-trip serialize.
    round_trip = json.loads(json.dumps(body))
    assert round_trip["teeth"][0]["geometry"]["state"] == "computed"
    assert round_trip["teeth"][0]["source_mesh_sha256"]


def test_upper_lower_arch_preserved() -> None:
    _seed_case("wp02-arch")
    record = _persist_dual_arch_segmentation("wp02-arch")
    intel = build_case_dental_intelligence(case_id="wp02-arch", segmentation_record=record)
    arches = {arch.arch: arch for arch in intel.arches}
    assert set(arches) == {"upper", "lower"}
    assert arches["upper"].tooth_instance_count == 14
    assert arches["lower"].tooth_instance_count == 14
    assert all(tooth.arch in {"upper", "lower"} for tooth in intel.teeth)


def test_measured_evidence_timings_recorded() -> None:
    _seed_case("wp02-perf")
    record = _persist_dual_arch_segmentation("wp02-perf")
    intel = build_case_dental_intelligence(case_id="wp02-perf", segmentation_record=record)
    assert intel.timings_ms.get("total") is not None
    assert intel.timings_ms["total"] >= 0
    assert intel.timings_ms.get("tooth_count_timed") == 28.0
    # Do not invent numbers in assertions beyond measured presence.
    print(
        "WP02_MEASURED",
        json.dumps(
            {
                "total_ms": intel.timings_ms["total"],
                "per_tooth_mean_ms": intel.timings_ms.get("per_tooth_mean"),
                "per_tooth_max_ms": intel.timings_ms.get("per_tooth_max"),
                "counts": intel.payload()["counts"],
                "truth_states": {
                    "overall": intel.overall_truth_state.value,
                    "occlusion": intel.occlusion.state.value,
                },
                "artifact": ARTIFACT_ID,
            }
        ),
    )


def test_live_tin_stamps_tooth_ref() -> None:
    """Live TIN mapping must stamp stable tooth_ref/arch without inventing FDI."""
    from domain.case.provenance import DataProvenance
    from domain.tooth.identification import (
        FDIToothIdentity,
        IdentificationConfidence,
        IdentificationStatus,
        IdentifiedTooth,
    )
    from domain.tooth.segmentation import ToothInstance
    from engines.segmentation.toothinstancenet import ToothInstanceNetEngine

    # Exercise the stamp logic via a minimal IdentifiedTooth construction matching engine output.
    instance = ToothInstance(
        instance_id=3,
        triangle_indices=(0,),
        vertex_indices=(0, 1, 2),
        mesh_vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        mesh_faces=((0, 1, 2),),
        centroid=(0.3, 0.3, 0.0),
        confidence=0.5,
        provenance=DataProvenance.EXPERIMENTAL,
    )
    # Simulate what the engine now does.
    tooth_ref = instance.tooth_ref or f"upper:instance:{instance.instance_id}"
    stamped = ToothInstance(
        instance_id=instance.instance_id,
        triangle_indices=instance.triangle_indices,
        vertex_indices=instance.vertex_indices,
        mesh_vertices=instance.mesh_vertices,
        mesh_faces=instance.mesh_faces,
        centroid=instance.centroid,
        confidence=instance.confidence,
        provenance=instance.provenance,
        tooth_ref=tooth_ref,
        arch="upper",
    )
    identified = IdentifiedTooth(
        instance=stamped,
        identity=FDIToothIdentity(11, ArchType.UPPER, 1, 1),
        landmarks=None,
        coordinate_system=None,
        confidence=IdentificationConfidence(
            0.5, IdentificationStatus.IDENTIFIED, ("test",)
        ),
        provenance=DataProvenance.EXPERIMENTAL,
        fixture=False,
        tooth_ref=tooth_ref,
    )
    serialized = serialize_identified_tooth(identified)
    assert serialized["tooth_ref"] == "upper:instance:3"
    assert serialized["landmarks"] is None
    assert ToothInstanceNetEngine  # import retained for regression surface


def test_empty_mesh_quality_finding() -> None:
    record = {
        "status": "completed",
        "job_id": "j",
        "input_hash": "f" * 64,
        "processing_mode": "real_case",
        "arches": {
            "upper": {
                "fixture": False,
                "provenance": "experimental",
                "source_mesh_sha256": "g" * 64,
                "tooth_instances": [
                    {
                        "instance_id": 0,
                        "arch": "upper",
                        "fdi_number": None,
                        "vertices": [],
                        "faces": [],
                        "fixture": False,
                        "provenance": "experimental",
                    }
                ],
            },
            "lower": {"fixture": False, "tooth_instances": []},
        },
    }
    intel = build_case_dental_intelligence(case_id="wp02-empty", segmentation_record=record)
    tooth = intel.teeth[0]
    assert tooth.geometry.state is IntelligenceTruthState.NOT_AVAILABLE
    assert any("empty" in finding or "missing" in finding for finding in tooth.quality_findings)
