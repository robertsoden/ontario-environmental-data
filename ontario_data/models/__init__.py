"""Data models for Ontario environmental data."""

from ontario_data.models.biodiversity import BiodiversityObservation
from ontario_data.models.community import CommunityWellBeing, InfrastructureProject
from ontario_data.models.fire import FirePerimeter
from ontario_data.models.health import HealthIndicator, PHUHealthProfile, PublicHealthUnit
from ontario_data.models.indigenous import ReserveBoundary, WaterAdvisory
from ontario_data.models.protected_areas import ProtectedArea

__all__ = [
    "BiodiversityObservation",
    "CommunityWellBeing",
    "FirePerimeter",
    "HealthIndicator",
    "InfrastructureProject",
    "PHUHealthProfile",
    "ProtectedArea",
    "PublicHealthUnit",
    "ReserveBoundary",
    "WaterAdvisory",
]
