"""Occlusion representation — honest availability, never invented contacts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.case.provenance import DataProvenance


class OcclusionAvailability(str, Enum):
    UNAVAILABLE = "unavailable"
    REQUIRES_REVIEW = "requires_review"
    COMPUTED = "computed"


@dataclass(frozen=True)
class OcclusionRepresentation:
    """Upper/lower registration and bite relationship when source data supports it.

    Dual-arch STL crowns alone do not establish occlusion, bite records, or
    occlusal contacts. Those fields stay UNAVAILABLE until genuine registration
    or bite evidence is present.
    """

    availability: OcclusionAvailability
    upper_lower_registration: OcclusionAvailability
    occlusal_relationship: OcclusionAvailability
    bite_record: OcclusionAvailability
    occlusal_contacts: OcclusionAvailability
    contact_count: int | None
    notes: tuple[str, ...]
    provenance: DataProvenance
    fixture: bool = False

    def payload(self) -> dict:
        return {
            "availability": self.availability.value,
            "upper_lower_registration": self.upper_lower_registration.value,
            "occlusal_relationship": self.occlusal_relationship.value,
            "bite_record": self.bite_record.value,
            "occlusal_contacts": self.occlusal_contacts.value,
            "contact_count": self.contact_count,
            "notes": list(self.notes),
            "provenance": self.provenance.value,
            "fixture": self.fixture,
        }


def unavailable_occlusion(
    *,
    provenance: DataProvenance = DataProvenance.EXPERIMENTAL,
    fixture: bool = False,
    reason: str = (
        "Occlusal registration, bite record, and occlusal contacts are not "
        "provided by crown-only STL analysis."
    ),
) -> OcclusionRepresentation:
    """Honest occlusion stub — does not invent contacts from crown meshes."""
    return OcclusionRepresentation(
        availability=OcclusionAvailability.UNAVAILABLE,
        upper_lower_registration=OcclusionAvailability.UNAVAILABLE,
        occlusal_relationship=OcclusionAvailability.UNAVAILABLE,
        bite_record=OcclusionAvailability.UNAVAILABLE,
        occlusal_contacts=OcclusionAvailability.UNAVAILABLE,
        contact_count=None,
        notes=(reason,),
        provenance=provenance,
        fixture=fixture,
    )
