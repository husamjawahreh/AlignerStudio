from domain.case.models import Case, CaseStatus, MeshAsset


def test_new_case_starts_created() -> None:
    case = Case(patient_reference="P-001")
    assert case.status == CaseStatus.CREATED
    assert case.meshes == []


def test_add_mesh_transitions_to_uploaded_and_replaces_same_arch() -> None:
    case = Case()
    case.add_mesh(MeshAsset(arch="upper", file_path="/tmp/a.stl", original_filename="a.stl"))
    assert case.status == CaseStatus.MESH_UPLOADED
    assert len(case.meshes) == 1

    case.add_mesh(MeshAsset(arch="upper", file_path="/tmp/b.stl", original_filename="b.stl"))
    assert len(case.meshes) == 1
    assert case.meshes[0].file_path == "/tmp/b.stl"

    case.add_mesh(MeshAsset(arch="lower", file_path="/tmp/c.stl", original_filename="c.stl"))
    assert len(case.meshes) == 2


def test_status_transitions() -> None:
    case = Case()
    case.mark_validated()
    assert case.status == CaseStatus.MESH_VALIDATED
    case.mark_rejected()
    assert case.status == CaseStatus.MESH_REJECTED
    case.mark_plan_generated()
    assert case.status == CaseStatus.PLAN_GENERATED
