"""Pydantic models for Indigenous data."""

from datetime import date
from typing import Dict, Optional

from pydantic import BaseModel, Field


class WaterAdvisory(BaseModel):
    """First Nations drinking water advisory."""

    advisory_id: Optional[str] = Field(None, description="Advisory identifier")
    community_name: str = Field(..., description="Community name")
    first_nation: str = Field(..., description="First Nation name")
    region: Optional[str] = Field(None, description="Region")
    province: str = Field(default="ON", description="Province")
    advisory_type: str = Field(..., description="Type of advisory")
    advisory_date: Optional[date] = Field(None, description="Date advisory issued")
    lift_date: Optional[date] = Field(None, description="Date advisory lifted")
    duration_days: Optional[int] = Field(None, description="Duration in days")
    is_active: bool = Field(default=True, description="Whether advisory is active")
    reason: Optional[str] = Field(None, description="Reason for advisory")
    water_system_name: Optional[str] = Field(None, description="Water system name")
    population_affected: Optional[int] = Field(None, description="Population affected")
    latitude: float = Field(..., description="Latitude", ge=-90, le=90)
    longitude: float = Field(..., description="Longitude", ge=-180, le=180)
    data_source: str = Field(
        default="Indigenous Services Canada", description="Data source"
    )
    source_url: Optional[str] = Field(None, description="Source URL")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "community_name": "Curve Lake First Nation",
                "first_nation": "Curve Lake First Nation",
                "advisory_type": "Boil Water Advisory",
                "advisory_date": "2024-01-15",
                "is_active": True,
                "latitude": 44.5319,
                "longitude": -78.2289,
            }
        }

    def to_geojson_feature(self) -> Dict:
        """Convert to GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude],
            },
            "properties": {
                "advisory_id": self.advisory_id,
                "community_name": self.community_name,
                "first_nation": self.first_nation,
                "region": self.region,
                "province": self.province,
                "advisory_type": self.advisory_type,
                "advisory_date": (
                    self.advisory_date.isoformat() if self.advisory_date else None
                ),
                "lift_date": self.lift_date.isoformat() if self.lift_date else None,
                "duration_days": self.duration_days,
                "is_active": self.is_active,
                "reason": self.reason,
                "water_system_name": self.water_system_name,
                "population_affected": self.population_affected,
                "data_source": self.data_source,
                "source_url": self.source_url,
            },
        }


class ReserveBoundary(BaseModel):
    """First Nations reserve boundary."""

    reserve_name: str = Field(..., description="Reserve name")
    first_nation: str = Field(..., description="First Nation name")
    province: str = Field(default="ON", description="Province")
    treaty: Optional[str] = Field(None, description="Treaty name")
    treaty_date: Optional[str] = Field(None, description="Treaty date")
    area_hectares: Optional[float] = Field(None, description="Area in hectares")
    population: Optional[int] = Field(None, description="Population")
    website: Optional[str] = Field(None, description="First Nation website")
    traditional_territory: Optional[str] = Field(
        None, description="Traditional territory description"
    )
    geometry: Dict = Field(..., description="GeoJSON geometry (Point or Polygon)")
    data_source: str = Field(default="Statistics Canada", description="Data source")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "reserve_name": "Curve Lake 35",
                "first_nation": "Curve Lake First Nation",
                "treaty": "Williams Treaty (1923)",
                "treaty_date": "1923-10-31",
                "geometry": {"type": "Point", "coordinates": [-78.2289, 44.5319]},
            }
        }

    def to_geojson_feature(self) -> Dict:
        """Convert to GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        return {
            "type": "Feature",
            "geometry": self.geometry,
            "properties": {
                "reserve_name": self.reserve_name,
                "first_nation": self.first_nation,
                "province": self.province,
                "treaty": self.treaty,
                "treaty_date": self.treaty_date,
                "area_hectares": self.area_hectares,
                "population": self.population,
                "website": self.website,
                "traditional_territory": self.traditional_territory,
                "data_source": self.data_source,
            },
        }
