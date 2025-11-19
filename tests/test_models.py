"""Tests for data models."""

from datetime import date

import pytest
from pydantic import ValidationError

from ontario_data.models.fire import FirePerimeter
from ontario_data.models.indigenous import ReserveBoundary, WaterAdvisory
from ontario_data.models.protected_areas import ProtectedArea


class TestWaterAdvisory:
    """Tests for WaterAdvisory model."""

    def test_create_valid_advisory(self):
        """Test creating a valid water advisory."""
        advisory = WaterAdvisory(
            community_name="Curve Lake First Nation",
            first_nation="Curve Lake First Nation",
            advisory_type="Boil Water Advisory",
            latitude=44.5319,
            longitude=-78.2289,
        )

        assert advisory.community_name == "Curve Lake First Nation"
        assert advisory.first_nation == "Curve Lake First Nation"
        assert advisory.advisory_type == "Boil Water Advisory"
        assert advisory.latitude == 44.5319
        assert advisory.longitude == -78.2289
        assert advisory.province == "ON"  # Default value
        assert advisory.is_active is True  # Default value

    def test_create_advisory_with_all_fields(self):
        """Test creating advisory with all optional fields."""
        advisory = WaterAdvisory(
            advisory_id="1234",
            community_name="Test Community",
            first_nation="Test Nation",
            region="Central",
            province="ON",
            advisory_type="Do Not Consume",
            advisory_date=date(2024, 1, 15),
            lift_date=date(2024, 6, 1),
            duration_days=137,
            is_active=False,
            reason="High contaminants",
            water_system_name="Main System",
            population_affected=1200,
            latitude=44.5,
            longitude=-78.5,
            data_source="Indigenous Services Canada",
            source_url="https://example.com",
        )

        assert advisory.advisory_id == "1234"
        assert advisory.region == "Central"
        assert advisory.advisory_date == date(2024, 1, 15)
        assert advisory.lift_date == date(2024, 6, 1)
        assert advisory.duration_days == 137
        assert advisory.is_active is False
        assert advisory.reason == "High contaminants"
        assert advisory.population_affected == 1200

    def test_invalid_latitude(self):
        """Test that invalid latitude raises ValidationError."""
        with pytest.raises(ValidationError):
            WaterAdvisory(
                community_name="Test",
                first_nation="Test Nation",
                advisory_type="Boil Water",
                latitude=100.0,  # Invalid: > 90
                longitude=-78.5,
            )

    def test_invalid_longitude(self):
        """Test that invalid longitude raises ValidationError."""
        with pytest.raises(ValidationError):
            WaterAdvisory(
                community_name="Test",
                first_nation="Test Nation",
                advisory_type="Boil Water",
                latitude=44.5,
                longitude=-200.0,  # Invalid: < -180
            )

    def test_to_geojson_feature(self):
        """Test conversion to GeoJSON feature."""
        advisory = WaterAdvisory(
            advisory_id="1234",
            community_name="Test Community",
            first_nation="Test Nation",
            advisory_type="Boil Water Advisory",
            latitude=44.5,
            longitude=-78.5,
            is_active=True,
        )

        feature = advisory.to_geojson_feature()

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [-78.5, 44.5]
        assert feature["properties"]["community_name"] == "Test Community"
        assert feature["properties"]["first_nation"] == "Test Nation"
        assert feature["properties"]["advisory_type"] == "Boil Water Advisory"
        assert feature["properties"]["is_active"] is True

    def test_to_geojson_feature_with_dates(self):
        """Test GeoJSON feature conversion with dates."""
        advisory = WaterAdvisory(
            community_name="Test",
            first_nation="Test Nation",
            advisory_type="Boil Water",
            advisory_date=date(2024, 1, 15),
            lift_date=date(2024, 6, 1),
            latitude=44.5,
            longitude=-78.5,
        )

        feature = advisory.to_geojson_feature()

        assert feature["properties"]["advisory_date"] == "2024-01-15"
        assert feature["properties"]["lift_date"] == "2024-06-01"


class TestReserveBoundary:
    """Tests for ReserveBoundary model."""

    def test_create_valid_reserve(self):
        """Test creating a valid reserve boundary."""
        reserve = ReserveBoundary(
            reserve_name="Curve Lake 35",
            first_nation="Curve Lake First Nation",
            geometry={"type": "Point", "coordinates": [-78.2289, 44.5319]},
        )

        assert reserve.reserve_name == "Curve Lake 35"
        assert reserve.first_nation == "Curve Lake First Nation"
        assert reserve.province == "ON"  # Default
        assert reserve.geometry["type"] == "Point"

    def test_create_reserve_with_all_fields(self):
        """Test creating reserve with all optional fields."""
        reserve = ReserveBoundary(
            reserve_name="Curve Lake 35",
            first_nation="Curve Lake First Nation",
            province="ON",
            treaty="Williams Treaty (1923)",
            treaty_date="1923-10-31",
            area_hectares=800.0,
            population=2200,
            website="https://www.curvelakefirstnation.ca",
            traditional_territory="Kawartha Lakes region",
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [
                        [-78.3, 44.5],
                        [-78.1, 44.5],
                        [-78.1, 44.6],
                        [-78.3, 44.6],
                        [-78.3, 44.5],
                    ]
                ],
            },
            data_source="Statistics Canada",
        )

        assert reserve.treaty == "Williams Treaty (1923)"
        assert reserve.treaty_date == "1923-10-31"
        assert reserve.area_hectares == 800.0
        assert reserve.population == 2200
        assert reserve.website == "https://www.curvelakefirstnation.ca"
        assert reserve.traditional_territory == "Kawartha Lakes region"
        assert reserve.geometry["type"] == "Polygon"

    def test_to_geojson_feature(self):
        """Test conversion to GeoJSON feature."""
        reserve = ReserveBoundary(
            reserve_name="Test Reserve",
            first_nation="Test Nation",
            treaty="Test Treaty",
            area_hectares=500.0,
            geometry={"type": "Point", "coordinates": [-78.0, 44.0]},
        )

        feature = reserve.to_geojson_feature()

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [-78.0, 44.0]
        assert feature["properties"]["reserve_name"] == "Test Reserve"
        assert feature["properties"]["first_nation"] == "Test Nation"
        assert feature["properties"]["treaty"] == "Test Treaty"
        assert feature["properties"]["area_hectares"] == 500.0


class TestFirePerimeter:
    """Tests for FirePerimeter model."""

    def test_create_valid_fire_perimeter(self):
        """Test creating a valid fire perimeter."""
        fire = FirePerimeter(
            fire_id="ON2024001",
            fire_year=2024,
            area_hectares=1500.0,
            geometry={
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
        )

        assert fire.fire_id == "ON2024001"
        assert fire.fire_year == 2024
        assert fire.area_hectares == 1500.0
        assert fire.geometry["type"] == "Polygon"
        assert fire.data_source == "CWFIS"  # Default

    def test_create_fire_with_all_fields(self):
        """Test creating fire perimeter with all optional fields."""
        fire = FirePerimeter(
            fire_id="ON2024001",
            fire_year=2024,
            fire_number="001",
            area_hectares=2300.5,
            cause="Lightning",
            start_date="2024-06-15",
            end_date="2024-06-20",
            fire_type="Wildfire",
            geometry={
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
            data_source="CWFIS/NBAC",
        )

        assert fire.fire_number == "001"
        assert fire.cause == "Lightning"
        assert fire.start_date == "2024-06-15"
        assert fire.end_date == "2024-06-20"
        assert fire.fire_type == "Wildfire"
        assert fire.data_source == "CWFIS/NBAC"

    def test_invalid_negative_area(self):
        """Test that negative area raises ValidationError."""
        with pytest.raises(ValidationError):
            FirePerimeter(
                fire_id="TEST",
                fire_year=2024,
                area_hectares=-100.0,  # Invalid: negative
                geometry={"type": "Point", "coordinates": [-78.0, 44.0]},
            )

    def test_to_geojson_feature(self):
        """Test conversion to GeoJSON feature."""
        fire = FirePerimeter(
            fire_id="ON2024001",
            fire_year=2024,
            area_hectares=1500.0,
            cause="Lightning",
            geometry={
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
        )

        feature = fire.to_geojson_feature()

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Polygon"
        assert feature["properties"]["fire_id"] == "ON2024001"
        assert feature["properties"]["fire_year"] == 2024
        assert feature["properties"]["area_hectares"] == 1500.0
        assert feature["properties"]["cause"] == "Lightning"


class TestProtectedArea:
    """Tests for ProtectedArea model."""

    def test_create_valid_protected_area(self):
        """Test creating a valid protected area."""
        area = ProtectedArea(
            name="Kawartha Highlands Provincial Park",
            designation="Provincial Park",
            managing_authority="Ontario Parks",
            geometry={"type": "Point", "coordinates": [-78.2, 44.85]},
        )

        assert area.name == "Kawartha Highlands Provincial Park"
        assert area.designation == "Provincial Park"
        assert area.managing_authority == "Ontario Parks"
        assert area.geometry["type"] == "Point"
        assert area.data_source == "Ontario GeoHub"  # Default

    def test_create_area_with_all_fields(self):
        """Test creating protected area with all optional fields."""
        area = ProtectedArea(
            park_id="123",
            name="Test Park",
            official_name="Test Provincial Park",
            designation="Provincial Park",
            managing_authority="Ontario Parks",
            hectares=37595.0,
            park_class="Natural Environment",
            zone_class="Wilderness",
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [
                        [-78.3, 44.8],
                        [-78.1, 44.8],
                        [-78.1, 44.9],
                        [-78.3, 44.9],
                        [-78.3, 44.8],
                    ]
                ],
            },
            data_source="Ontario GeoHub",
        )

        assert area.park_id == "123"
        assert area.official_name == "Test Provincial Park"
        assert area.hectares == 37595.0
        assert area.park_class == "Natural Environment"
        assert area.zone_class == "Wilderness"
        assert area.geometry["type"] == "Polygon"

    def test_invalid_negative_hectares(self):
        """Test that negative hectares raises ValidationError."""
        with pytest.raises(ValidationError):
            ProtectedArea(
                name="Test Park",
                designation="Provincial Park",
                managing_authority="Ontario Parks",
                hectares=-100.0,  # Invalid: negative
                geometry={"type": "Point", "coordinates": [-78.0, 44.0]},
            )

    def test_to_geojson_feature(self):
        """Test conversion to GeoJSON feature."""
        area = ProtectedArea(
            park_id="123",
            name="Test Park",
            official_name="Test Provincial Park",
            designation="Provincial Park",
            managing_authority="Ontario Parks",
            hectares=1000.0,
            geometry={"type": "Point", "coordinates": [-78.2, 44.85]},
        )

        feature = area.to_geojson_feature()

        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [-78.2, 44.85]
        assert feature["properties"]["park_id"] == "123"
        assert feature["properties"]["name"] == "Test Park"
        assert feature["properties"]["official_name"] == "Test Provincial Park"
        assert feature["properties"]["designation"] == "Provincial Park"
        assert feature["properties"]["managing_authority"] == "Ontario Parks"
        assert feature["properties"]["hectares"] == 1000.0

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        area = ProtectedArea(
            name="Test Park",
            designation="Provincial Park",
            managing_authority="Ontario Parks",
            geometry={"type": "Point", "coordinates": [-78.0, 44.0]},
        )

        assert area.park_id is None
        assert area.official_name is None
        assert area.hectares is None
        assert area.park_class is None
        assert area.zone_class is None
