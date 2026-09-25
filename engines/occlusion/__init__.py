"""WP-08 occlusion + advanced anatomy engines."""

from engines.occlusion.capability_engine import (
    build_advanced_anatomy_report,
    build_occlusion_anatomy_plan,
    build_occlusion_result,
    compute_geometric_contact_candidates,
    intelligence_truth_for_occlusion,
    parse_registration_evidence,
)

__all__ = [
    "build_advanced_anatomy_report",
    "build_occlusion_anatomy_plan",
    "build_occlusion_result",
    "compute_geometric_contact_candidates",
    "intelligence_truth_for_occlusion",
    "parse_registration_evidence",
]
