"""Production CAD geometry backends — isolated behind ProductionGeometryAdapter.

Third-party mesh types must not leak into clinical domain models.
"""

from engines.geometry.production_geometry.adapter import (
    ProductionGeometryAdapter,
    get_production_geometry_adapter,
)
from engines.geometry.production_geometry.types import (
    GeometryBackendInfo,
    GeometryOperationResult,
    MeshBuffers,
)

__all__ = [
    "GeometryBackendInfo",
    "GeometryOperationResult",
    "MeshBuffers",
    "ProductionGeometryAdapter",
    "get_production_geometry_adapter",
]
