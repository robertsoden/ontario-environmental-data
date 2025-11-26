"""Pydantic models for public health data."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PublicHealthUnit(BaseModel):
    """Ontario Public Health Unit boundary and metadata."""

    phu_id: Optional[str] = Field(None, description="Public Health Unit ID")
    name: str = Field(..., description="PHU name (English)")
    name_fr: Optional[str] = Field(None, description="PHU name (French)")
    office_name: Optional[str] = Field(None, description="MOH office name")
    area_sq_km: Optional[float] = Field(None, description="Area in square kilometers")
    population: Optional[int] = Field(None, description="Population served")
    geometry: Optional[Dict] = Field(None, description="GeoJSON geometry (Polygon)")
    data_source: str = Field(
        default="Ontario GeoHub", description="Data source"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "phu_id": "3895",
                "name": "Peterborough Public Health",
                "name_fr": "Santé publique de Peterborough",
                "area_sq_km": 3847.5,
                "population": 146000,
            }
        }

    def to_geojson_feature(self) -> Dict:
        """Convert to GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        return {
            "type": "Feature",
            "geometry": self.geometry or {"type": "Polygon", "coordinates": []},
            "properties": {
                "phu_id": self.phu_id,
                "name": self.name,
                "name_fr": self.name_fr,
                "office_name": self.office_name,
                "area_sq_km": self.area_sq_km,
                "population": self.population,
                "data_source": self.data_source,
            },
        }


class HealthIndicator(BaseModel):
    """A single health indicator value for a geographic region."""

    indicator_name: str = Field(..., description="Name of the health indicator")
    indicator_category: str = Field(
        ..., description="Category (chronic_disease, mental_health, mortality, etc.)"
    )
    value: float = Field(..., description="Indicator value")
    unit: str = Field(
        default="rate_per_100k",
        description="Unit of measurement (rate_per_100k, percent, count, years)",
    )
    year: Optional[int] = Field(None, description="Year of the data")
    confidence_interval_low: Optional[float] = Field(
        None, description="95% CI lower bound"
    )
    confidence_interval_high: Optional[float] = Field(
        None, description="95% CI upper bound"
    )
    data_source: str = Field(default="OCHPP", description="Data source")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "indicator_name": "diabetes_rate",
                "indicator_category": "chronic_disease",
                "value": 9.8,
                "unit": "percent",
                "year": 2022,
                "confidence_interval_low": 9.2,
                "confidence_interval_high": 10.4,
            }
        }


class PHUHealthProfile(BaseModel):
    """Complete health profile for a Public Health Unit.

    Combines PHU boundary data with multiple health indicators.
    """

    phu_id: Optional[str] = Field(None, description="Public Health Unit ID")
    phu_name: str = Field(..., description="PHU name")
    population: Optional[int] = Field(None, description="Population served")

    # Chronic disease indicators
    diabetes_rate: Optional[float] = Field(
        None, description="Diabetes prevalence (%)", ge=0, le=100
    )
    hypertension_rate: Optional[float] = Field(
        None, description="Hypertension prevalence (%)", ge=0, le=100
    )
    copd_rate: Optional[float] = Field(
        None, description="COPD prevalence (%)", ge=0, le=100
    )
    asthma_rate: Optional[float] = Field(
        None, description="Asthma prevalence (%)", ge=0, le=100
    )

    # Mental health indicators
    mental_health_ed_rate: Optional[float] = Field(
        None, description="Mental health ED visit rate per 100,000"
    )
    self_reported_mental_health_good: Optional[float] = Field(
        None, description="% reporting good/excellent mental health", ge=0, le=100
    )

    # Mortality indicators
    all_cause_mortality_rate: Optional[float] = Field(
        None, description="All-cause mortality rate per 100,000"
    )
    premature_mortality_rate: Optional[float] = Field(
        None, description="Premature mortality rate (age <75) per 100,000"
    )
    life_expectancy: Optional[float] = Field(
        None, description="Life expectancy at birth (years)"
    )
    infant_mortality_rate: Optional[float] = Field(
        None, description="Infant mortality rate per 1,000 live births"
    )

    # Access to care indicators
    primary_care_attachment: Optional[float] = Field(
        None, description="% with regular healthcare provider", ge=0, le=100
    )
    cancer_screening_rate: Optional[float] = Field(
        None, description="Cancer screening participation (%)", ge=0, le=100
    )

    # Socioeconomic factors
    low_income_rate: Optional[float] = Field(
        None, description="% population in low income", ge=0, le=100
    )

    # Metadata
    data_year: Optional[int] = Field(None, description="Primary data year")
    geometry: Optional[Dict] = Field(None, description="GeoJSON geometry")
    data_source: str = Field(default="OCHPP", description="Data source")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "phu_id": "3895",
                "phu_name": "Peterborough Public Health",
                "population": 146000,
                "diabetes_rate": 9.8,
                "hypertension_rate": 24.5,
                "life_expectancy": 81.2,
                "primary_care_attachment": 89.5,
                "data_year": 2022,
            }
        }

    def to_geojson_feature(self) -> Dict:
        """Convert to GeoJSON Feature.

        Returns:
            GeoJSON Feature dictionary
        """
        properties = {
            "phu_id": self.phu_id,
            "phu_name": self.phu_name,
            "population": self.population,
            "diabetes_rate": self.diabetes_rate,
            "hypertension_rate": self.hypertension_rate,
            "copd_rate": self.copd_rate,
            "asthma_rate": self.asthma_rate,
            "mental_health_ed_rate": self.mental_health_ed_rate,
            "self_reported_mental_health_good": self.self_reported_mental_health_good,
            "all_cause_mortality_rate": self.all_cause_mortality_rate,
            "premature_mortality_rate": self.premature_mortality_rate,
            "life_expectancy": self.life_expectancy,
            "infant_mortality_rate": self.infant_mortality_rate,
            "primary_care_attachment": self.primary_care_attachment,
            "cancer_screening_rate": self.cancer_screening_rate,
            "low_income_rate": self.low_income_rate,
            "data_year": self.data_year,
            "data_source": self.data_source,
        }
        # Remove None values for cleaner output
        properties = {k: v for k, v in properties.items() if v is not None}

        return {
            "type": "Feature",
            "geometry": self.geometry or {"type": "Polygon", "coordinates": []},
            "properties": properties,
        }

    def get_indicators(self) -> List[HealthIndicator]:
        """Extract individual health indicators from this profile.

        Returns:
            List of HealthIndicator objects
        """
        indicators = []
        indicator_mapping = [
            ("diabetes_rate", "chronic_disease", "percent"),
            ("hypertension_rate", "chronic_disease", "percent"),
            ("copd_rate", "chronic_disease", "percent"),
            ("asthma_rate", "chronic_disease", "percent"),
            ("mental_health_ed_rate", "mental_health", "rate_per_100k"),
            ("self_reported_mental_health_good", "mental_health", "percent"),
            ("all_cause_mortality_rate", "mortality", "rate_per_100k"),
            ("premature_mortality_rate", "mortality", "rate_per_100k"),
            ("life_expectancy", "mortality", "years"),
            ("infant_mortality_rate", "mortality", "rate_per_1k"),
            ("primary_care_attachment", "access_to_care", "percent"),
            ("cancer_screening_rate", "access_to_care", "percent"),
            ("low_income_rate", "socioeconomic", "percent"),
        ]

        for attr_name, category, unit in indicator_mapping:
            value = getattr(self, attr_name, None)
            if value is not None:
                indicators.append(
                    HealthIndicator(
                        indicator_name=attr_name,
                        indicator_category=category,
                        value=value,
                        unit=unit,
                        year=self.data_year,
                        data_source=self.data_source,
                    )
                )

        return indicators
