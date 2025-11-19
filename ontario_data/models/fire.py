"""Pydantic models for fire data."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class FirePerimeter(BaseModel):
    """Historical fire perimeter."""

    fire_id: str = Field(..., description="Fire identifier")
    fire_year: int = Field(..., description="Year of fire")
    fire_number: Optional[str] = Field(None, description="Fire number")
    area_hectares: float = Field(..., description="Burned area in hectares", ge=0)
    cause: Optional[str] = Field(None, description="Cause of fire")
    start_date: Optional[str] = Field(None, description="Fire start date")
    end_date: Optional[str] = Field(None, description="Fire end date")
    fire_type: Optional[str] = Field(None, description="Fire type")
    geometry: Dict = Field(
        ..., description="GeoJSON geometry (Polygon or MultiPolygon)"
    )
    data_source: str = Field(default="CWFIS", description="Data source")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "fire_id": "ON2024001",
                "fire_year": 2024,
                "area_hectares": 1500.0,
                "cause": "Lightning",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [-78.5, 44.5],
                            [-78.4, 44.5],
                            [-78.4, 44.6],
                            [-78.5, 44.6],
                            [-78.5, 44.5],
                        ]
                    ],
                },
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
                "fire_id": self.fire_id,
                "fire_year": self.fire_year,
                "fire_number": self.fire_number,
                "area_hectares": self.area_hectares,
                "cause": self.cause,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "fire_type": self.fire_type,
                "data_source": self.data_source,
            },
        }
