"""Pydantic models for protected areas (parks, conservation areas)."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class ProtectedArea(BaseModel):
    """Protected area (park, conservation area, etc.)."""

    park_id: Optional[str] = Field(None, description="Park/area identifier")
    name: str = Field(..., description="Area name")
    official_name: Optional[str] = Field(None, description="Official name")
    designation: str = Field(..., description="Designation type")
    managing_authority: str = Field(..., description="Managing authority")
    hectares: Optional[float] = Field(None, description="Area in hectares", ge=0)
    park_class: Optional[str] = Field(None, description="Park classification")
    zone_class: Optional[str] = Field(None, description="Zone classification")
    geometry: Dict = Field(..., description="GeoJSON geometry (Point or Polygon)")
    data_source: str = Field(default="Ontario GeoHub", description="Data source")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Kawartha Highlands Provincial Park",
                "official_name": "Kawartha Highlands Provincial Park",
                "designation": "Provincial Park",
                "managing_authority": "Ontario Parks",
                "hectares": 37595.0,
                "geometry": {"type": "Point", "coordinates": [-78.2, 44.85]},
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
                "park_id": self.park_id,
                "name": self.name,
                "official_name": self.official_name,
                "designation": self.designation,
                "managing_authority": self.managing_authority,
                "hectares": self.hectares,
                "park_class": self.park_class,
                "zone_class": self.zone_class,
                "data_source": self.data_source,
            },
        }
