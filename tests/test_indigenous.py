"""Tests for Indigenous data source clients."""

import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from ontario_data.sources.indigenous import (
    StatisticsCanadaWFSClient,
    WaterAdvisoriesClient,
)


class TestWaterAdvisoriesClient:
    """Tests for WaterAdvisoriesClient."""

    @pytest.fixture
    def sample_csv_data(self, tmp_path):
        """Create a sample CSV file for testing."""
        csv_content = """Advisory ID,Community,First Nation,Region,Province,Advisory Type,Advisory Date,Lift Date,Reason,Water System,Population,Latitude,Longitude
1,Curve Lake,Curve Lake First Nation,Central,ON,Boil Water Advisory,2024-01-15,,Equipment Failure,Main System,1200,44.5319,-78.2289
2,Alderville,Alderville First Nation,Central,ON,Do Not Consume,2023-06-01,2024-01-10,High Contaminants,South System,800,44.1194,-78.0753
3,Test Community,Test Nation,North,ON,Boil Water Advisory,2024-11-01,,Testing,Test System,500,45.0,-79.0
"""
        csv_path = tmp_path / "test_advisories.csv"
        csv_path.write_text(csv_content)
        return csv_path

    @pytest.mark.asyncio
    async def test_fetch_from_csv_success(self, sample_csv_data):
        """Test successful CSV loading and parsing."""
        client = WaterAdvisoriesClient()
        advisories = await client.fetch_from_csv(sample_csv_data)

        assert len(advisories) == 3
        assert advisories[0]["community_name"] == "Curve Lake"
        assert advisories[0]["first_nation"] == "Curve Lake First Nation"
        assert advisories[0]["province"] == "ON"
        assert advisories[0]["latitude"] == 44.5319
        assert advisories[0]["longitude"] == -78.2289

    @pytest.mark.asyncio
    async def test_fetch_from_csv_province_filter(self, sample_csv_data):
        """Test province filtering."""
        client = WaterAdvisoriesClient()
        advisories = await client.fetch_from_csv(sample_csv_data, province="ON")

        assert len(advisories) == 3
        assert all(adv["province"] == "ON" for adv in advisories)

    @pytest.mark.asyncio
    async def test_fetch_from_csv_missing_file(self):
        """Test error handling for missing CSV file."""
        client = WaterAdvisoriesClient()

        with pytest.raises(FileNotFoundError):
            await client.fetch_from_csv("nonexistent.csv")

    @pytest.mark.asyncio
    async def test_fetch_requires_csv_path(self):
        """Test that fetch() requires csv_path parameter."""
        client = WaterAdvisoriesClient()

        with pytest.raises(ValueError, match="csv_path is required"):
            await client.fetch()

    def test_transform_row_active_advisory(self):
        """Test transforming a row with active advisory."""
        client = WaterAdvisoriesClient()
        row = pd.Series({
            "Advisory ID": "1",
            "Community": "Test Community",
            "First Nation": "Test Nation",
            "Region": "Central",
            "Province": "ON",
            "Advisory Type": "Boil Water Advisory",
            "Advisory Date": "2024-01-15",
            "Lift Date": pd.NaT,
            "Reason": "Equipment Failure",
            "Water System": "Main System",
            "Population": 1200,
            "Latitude": 44.5,
            "Longitude": -78.5,
        })

        result = client._transform_row(row)

        assert result["community_name"] == "Test Community"
        assert result["first_nation"] == "Test Nation"
        assert result["advisory_type"] == "Boil Water Advisory"
        assert result["is_active"] is True
        assert result["lift_date"] is None
        assert result["latitude"] == 44.5
        assert result["longitude"] == -78.5

    def test_transform_row_lifted_advisory(self):
        """Test transforming a row with lifted advisory."""
        client = WaterAdvisoriesClient()
        row = pd.Series({
            "Advisory ID": "2",
            "Community": "Test Community",
            "First Nation": "Test Nation",
            "Region": "Central",
            "Province": "ON",
            "Advisory Type": "Do Not Consume",
            "Advisory Date": "2023-06-01",
            "Lift Date": "2024-01-10",
            "Reason": "High Contaminants",
            "Water System": "Main System",
            "Population": 800,
            "Latitude": 44.1,
            "Longitude": -78.0,
        })

        result = client._transform_row(row)

        assert result["is_active"] is False
        assert result["lift_date"] is not None
        assert result["duration_days"] is not None
        assert result["duration_days"] > 0

    def test_to_geodataframe(self, sample_csv_data):
        """Test conversion to GeoDataFrame."""
        advisories = [
            {
                "community_name": "Test",
                "first_nation": "Test Nation",
                "latitude": 44.5,
                "longitude": -78.5,
                "advisory_type": "Boil Water",
                "is_active": True,
            }
        ]
        client = WaterAdvisoriesClient()
        gdf = client.to_geodataframe(advisories)

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) == 1
        assert gdf.crs == "EPSG:4326"
        assert isinstance(gdf.geometry[0], Point)

    def test_to_geodataframe_empty(self):
        """Test conversion of empty list to GeoDataFrame."""
        client = WaterAdvisoriesClient()
        gdf = client.to_geodataframe([])

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) == 0


class TestStatisticsCanadaWFSClient:
    """Tests for StatisticsCanadaWFSClient."""

    @pytest.fixture
    def mock_wfs_response(self):
        """Create mock WFS GeoJSON response."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "IRNAME": "Curve Lake First Nation",
                        "PRCODE": "ON",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-78.2289, 44.5319]
                    }
                },
                {
                    "type": "Feature",
                    "properties": {
                        "IRNAME": "Alderville First Nation",
                        "PRCODE": "ON",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-78.0753, 44.1194]
                    }
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_get_reserve_boundaries_success(self, mock_wfs_response):
        """Test successful WFS request for reserve boundaries."""
        client = StatisticsCanadaWFSClient()

        # Mock the aiohttp session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_wfs_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            gdf = await client.get_reserve_boundaries(province="ON")

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 2
            assert gdf.crs == "EPSG:4326"

    @pytest.mark.asyncio
    async def test_get_reserve_boundaries_with_filter(self, mock_wfs_response):
        """Test WFS request with First Nation name filter."""
        client = StatisticsCanadaWFSClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_wfs_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            first_nations = ["Curve Lake First Nation"]
            gdf = await client.get_reserve_boundaries(
                province="ON",
                first_nations=first_nations
            )

            assert isinstance(gdf, gpd.GeoDataFrame)

    @pytest.mark.asyncio
    async def test_get_reserve_boundaries_http_error(self):
        """Test handling of HTTP error from WFS."""
        client = StatisticsCanadaWFSClient()

        mock_response = AsyncMock()
        mock_response.status = 500

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            with pytest.raises(Exception):  # Should raise DataSourceError
                await client.get_reserve_boundaries()

    @pytest.mark.asyncio
    async def test_fetch_returns_list_of_dicts(self, mock_wfs_response):
        """Test that fetch() returns list of dictionaries."""
        client = StatisticsCanadaWFSClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_wfs_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            reserves = await client.fetch(province="ON")

            assert isinstance(reserves, list)
            assert len(reserves) == 2
            assert all(isinstance(r, dict) for r in reserves)
            assert "reserve_name" in reserves[0]
            assert "first_nation" in reserves[0]
            assert "geometry" in reserves[0]

    def test_create_williams_treaty_data(self):
        """Test Williams Treaty fallback data creation."""
        client = StatisticsCanadaWFSClient()
        gdf = client.create_williams_treaty_data()

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) == 7  # 7 Williams Treaty First Nations
        assert gdf.crs == "EPSG:4326"
        assert "first_nation" in gdf.columns
        assert "reserve_name" in gdf.columns
        assert "treaty" in gdf.columns
        assert all(gdf["province"] == "ON")

    def test_williams_treaty_data_content(self):
        """Test Williams Treaty data has expected nations."""
        client = StatisticsCanadaWFSClient()
        gdf = client.create_williams_treaty_data()

        expected_nations = {
            "Alderville First Nation",
            "Curve Lake First Nation",
            "Hiawatha First Nation",
            "Mississaugas of Scugog Island First Nation",
            "Chippewas of Beausoleil First Nation",
            "Chippewas of Georgina Island First Nation",
            "Chippewas of Rama First Nation",
        }

        actual_nations = set(gdf["first_nation"])
        assert actual_nations == expected_nations
