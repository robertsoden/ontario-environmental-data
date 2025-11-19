"""Pydantic models for community socioeconomic data."""

from typing import Dict, Optional

from pydantic import BaseModel, Field


class CommunityWellBeing(BaseModel):
    """Community Well-Being Index data for a community."""

    csd_code: str = Field(..., description="Census Subdivision code")
    csd_name: str = Field(..., description="Census Subdivision name")
    community_type: Optional[str] = Field(None, description="Community type")
    population: Optional[int] = Field(None, description="Population count", ge=0)
    income_score: Optional[float] = Field(
        None, description="Income component score", ge=0, le=100
    )
    education_score: Optional[float] = Field(
        None, description="Education component score", ge=0, le=100
    )
    housing_score: Optional[float] = Field(
        None, description="Housing component score", ge=0, le=100
    )
    labour_force_score: Optional[float] = Field(
        None, description="Labour force activity score", ge=0, le=100
    )
    cwb_score: Optional[float] = Field(
        None, description="Overall CWB score", ge=0, le=100
    )
    year: int = Field(default=2021, description="Census year")
    geometry: Optional[Dict] = Field(
        None, description="GeoJSON geometry (Point or Polygon)"
    )
    data_source: str = Field(default="Statistics Canada", description="Data source")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "csd_code": "3515014",
                "csd_name": "Curve Lake First Nation",
                "community_type": "First Nation",
                "population": 900,
                "income_score": 45.2,
                "education_score": 38.7,
                "housing_score": 52.1,
                "labour_force_score": 48.9,
                "cwb_score": 46.2,
                "year": 2021,
            }
        }

    def to_geojson_feature(self) -> Dict:
        """Convert to GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        return {
            "type": "Feature",
            "geometry": self.geometry
            or {"type": "Point", "coordinates": [0, 0]},  # Placeholder if no geometry
            "properties": {
                "csd_code": self.csd_code,
                "csd_name": self.csd_name,
                "community_type": self.community_type,
                "population": self.population,
                "income_score": self.income_score,
                "education_score": self.education_score,
                "housing_score": self.housing_score,
                "labour_force_score": self.labour_force_score,
                "cwb_score": self.cwb_score,
                "year": self.year,
                "data_source": self.data_source,
            },
        }


class InfrastructureProject(BaseModel):
    """Indigenous infrastructure project data."""

    community_name: str = Field(..., description="Community name")
    community_number: Optional[str] = Field(None, description="Community number")
    project_name: str = Field(..., description="Project name")
    project_description: Optional[str] = Field(None, description="Project description")
    infrastructure_category: str = Field(..., description="Infrastructure category")
    project_status: Optional[str] = Field(None, description="Project status")
    investment_amount: Optional[float] = Field(
        None, description="Investment amount (CAD)", ge=0
    )
    latitude: float = Field(..., description="Latitude", ge=-90, le=90)
    longitude: float = Field(..., description="Longitude", ge=-180, le=180)
    province: Optional[str] = Field(None, description="Province")
    data_source: str = Field(
        default="Indigenous Services Canada ICIM", description="Data source"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "community_name": "Curve Lake First Nation",
                "community_number": "470",
                "project_name": "Water Treatment Plant Upgrade",
                "project_description": "Upgrade to water treatment facility",
                "infrastructure_category": "Water and Wastewater",
                "project_status": "Completed",
                "investment_amount": 2500000.00,
                "latitude": 44.5319,
                "longitude": -78.2289,
                "province": "ON",
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
                "community_name": self.community_name,
                "community_number": self.community_number,
                "project_name": self.project_name,
                "project_description": self.project_description,
                "infrastructure_category": self.infrastructure_category,
                "project_status": self.project_status,
                "investment_amount": self.investment_amount,
                "province": self.province,
                "data_source": self.data_source,
            },
        }
