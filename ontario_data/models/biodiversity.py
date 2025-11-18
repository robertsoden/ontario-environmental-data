"""Pydantic models for biodiversity observations."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class Taxonomy(BaseModel):
    """Taxonomic information for an observed species."""

    rank: str = Field(..., description="Taxonomic rank (species, genus, etc.)")
    iconic_taxon: Optional[str] = Field(None, description="Iconic taxon group")
    taxon_id: int = Field(..., description="Taxon identifier")


class GeoJSONPoint(BaseModel):
    """GeoJSON Point geometry."""

    type: str = Field(default="Point", description="Geometry type")
    coordinates: List[float] = Field(
        ..., description="Coordinates [longitude, latitude]"
    )

    @field_validator("coordinates")
    def validate_coordinates(cls, v):
        """Validate coordinates are valid lon, lat."""
        if len(v) != 2:
            raise ValueError("Coordinates must be [longitude, latitude]")
        lon, lat = v
        if not (-180 <= lon <= 180):
            raise ValueError(f"Invalid longitude: {lon}")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Invalid latitude: {lat}")
        return v


class BiodiversityObservation(BaseModel):
    """Standardized biodiversity observation from any source."""

    source: str = Field(..., description="Data source (iNaturalist, eBird, GBIF)")
    observation_id: str = Field(..., description="Unique observation identifier")
    species_name: Optional[str] = Field(None, description="Species name")
    common_name: Optional[str] = Field(None, description="Common name")
    scientific_name: str = Field(..., description="Scientific name")
    observation_date: Optional[str] = Field(None, description="Observation date")
    observation_datetime: Optional[str] = Field(
        None, description="Observation datetime"
    )
    location: GeoJSONPoint = Field(..., description="Observation location")
    place_name: Optional[str] = Field(None, description="Place name")
    observer: Optional[str] = Field(None, description="Observer username/ID")
    url: Optional[str] = Field(None, description="URL to observation")

    # Source-specific fields stored in metadata
    taxonomy: Optional[Taxonomy] = Field(None, description="Taxonomic information")
    quality_grade: Optional[str] = Field(None, description="Quality grade/validation")
    photos: Optional[List[str]] = Field(default=[], description="Photo URLs")
    accuracy_meters: Optional[float] = Field(
        None, description="Positional accuracy in meters"
    )
    count: Optional[int] = Field(None, description="Number of individuals observed")
    species_code: Optional[str] = Field(None, description="Species code (eBird)")
    license: Optional[str] = Field(None, description="Data license")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "source": "iNaturalist",
                "observation_id": "123456789",
                "species_name": "Pileated Woodpecker",
                "common_name": "Pileated Woodpecker",
                "scientific_name": "Dryocopus pileatus",
                "observation_date": "2024-11-01",
                "location": {
                    "type": "Point",
                    "coordinates": [-78.3, 44.3],
                },
                "place_name": "Peterborough, Ontario",
                "observer": "naturalist123",
                "quality_grade": "research",
            }
        }

    def to_geojson_feature(self) -> Dict:
        """Convert observation to GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        return {
            "type": "Feature",
            "geometry": self.location.model_dump(),
            "properties": {
                "source": self.source,
                "observation_id": self.observation_id,
                "species_name": self.species_name,
                "common_name": self.common_name,
                "scientific_name": self.scientific_name,
                "observation_date": self.observation_date,
                "observation_datetime": self.observation_datetime,
                "place_name": self.place_name,
                "observer": self.observer,
                "url": self.url,
                "quality_grade": self.quality_grade,
                "count": self.count,
            },
        }
