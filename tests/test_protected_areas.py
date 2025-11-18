"""Tests for protected areas data source clients."""

import json
from unittest.mock import AsyncMock, patch

import geopandas as gpd
import pytest

from ontario_data.sources.protected_areas import OntarioGeoHubClient


class TestOntarioGeoHubClient:
    """Tests for OntarioGeoHubClient (Ontario GeoHub / LIO)."""

    @pytest.fixture
    def mock_parks_response(self):
        """Create mock ArcGIS REST API response for parks."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "PARK_NAME": "Kawartha Highlands Provincial Park",
                        "OFFICIAL_NAME": "Kawartha Highlands Provincial Park",
                        "ONT_PARK_ID": "123",
                        "REGULATION": "Provincial Park",
                        "AREA_HA": 37595.0,
                        "MANAGEMENT_UNIT": "Ontario Parks",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-78.3, 44.8],
                            [-78.1, 44.8],
                            [-78.1, 44.9],
                            [-78.3, 44.9],
                            [-78.3, 44.8]
                        ]]
                    }
                },
                {
                    "type": "Feature",
                    "properties": {
                        "PARK_NAME": "Silent Lake Provincial Park",
                        "OFFICIAL_NAME": "Silent Lake Provincial Park",
                        "ONT_PARK_ID": "456",
                        "REGULATION": "Provincial Park",
                        "AREA_HA": 1627.0,
                        "MANAGEMENT_UNIT": "Ontario Parks",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-78.2, 44.9],
                            [-78.0, 44.9],
                            [-78.0, 45.0],
                            [-78.2, 45.0],
                            [-78.2, 44.9]
                        ]]
                    }
                }
            ]
        }

    @pytest.fixture
    def mock_conservation_response(self):
        """Create mock ArcGIS REST API response for conservation authorities."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "CA_NAME": "Kawartha Conservation",
                        "CA_AUTHORITY": "Kawartha Region Conservation Authority",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-78.5, 44.5],
                            [-78.0, 44.5],
                            [-78.0, 45.0],
                            [-78.5, 45.0],
                            [-78.5, 44.5]
                        ]]
                    }
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_get_provincial_parks_success(self, mock_parks_response):
        """Test successful provincial parks fetching."""
        client = OntarioGeoHubClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_parks_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            gdf = await client.get_provincial_parks()

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 2
            assert gdf.crs == "EPSG:4326"
            assert "name" in gdf.columns
            assert "official_name" in gdf.columns
            assert "designation" in gdf.columns

    @pytest.mark.asyncio
    async def test_get_provincial_parks_with_bounds(self, mock_parks_response):
        """Test parks fetching with bounding box filter."""
        client = OntarioGeoHubClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_parks_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            gdf = await client.get_provincial_parks(bounds=bounds)

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 2

    @pytest.mark.asyncio
    async def test_get_provincial_parks_standardizes_columns(self, mock_parks_response):
        """Test that column names are standardized."""
        client = OntarioGeoHubClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_parks_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            gdf = await client.get_provincial_parks()

            # Check standardized column names
            assert "name" in gdf.columns
            assert "official_name" in gdf.columns
            assert "designation" in gdf.columns
            assert "managing_authority" in gdf.columns

    @pytest.mark.asyncio
    async def test_get_provincial_parks_http_error(self):
        """Test handling of HTTP errors."""
        client = OntarioGeoHubClient()

        mock_response = AsyncMock()
        mock_response.status = 500

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            with pytest.raises(Exception):  # Should raise DataSourceError
                await client.get_provincial_parks()

    @pytest.mark.asyncio
    async def test_get_conservation_authorities_success(self, mock_conservation_response):
        """Test successful conservation authorities fetching."""
        client = OntarioGeoHubClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_conservation_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            gdf = await client.get_conservation_authorities()

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 1
            assert gdf.crs == "EPSG:4326"

    @pytest.mark.asyncio
    async def test_get_conservation_authorities_with_bounds(self, mock_conservation_response):
        """Test conservation authorities fetching with bounding box."""
        client = OntarioGeoHubClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_conservation_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            gdf = await client.get_conservation_authorities(bounds=bounds)

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 1

    @pytest.mark.asyncio
    async def test_fetch_parks_returns_list_of_dicts(self, mock_parks_response):
        """Test that fetch() with dataset='parks' returns list of dictionaries."""
        client = OntarioGeoHubClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_parks_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            parks = await client.fetch(dataset="parks")

            assert isinstance(parks, list)
            assert len(parks) == 2
            assert all(isinstance(p, dict) for p in parks)
            assert "geometry" in parks[0]
            assert "name" in parks[0]

    @pytest.mark.asyncio
    async def test_fetch_conservation_authorities_returns_list_of_dicts(self, mock_conservation_response):
        """Test that fetch() with dataset='conservation_authorities' returns list of dictionaries."""
        client = OntarioGeoHubClient()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_conservation_response))

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            authorities = await client.fetch(dataset="conservation_authorities")

            assert isinstance(authorities, list)
            assert len(authorities) == 1
            assert all(isinstance(a, dict) for a in authorities)
            assert "geometry" in authorities[0]

    @pytest.mark.asyncio
    async def test_fetch_unknown_dataset_raises_error(self):
        """Test that fetch() with unknown dataset raises ValueError."""
        client = OntarioGeoHubClient()

        with pytest.raises(ValueError, match="Unknown dataset"):
            await client.fetch(dataset="invalid_dataset")

    def test_client_initialization(self):
        """Test client initialization with default rate limit."""
        client = OntarioGeoHubClient()
        assert client is not None

    def test_client_custom_rate_limit(self):
        """Test client initialization with custom rate limit."""
        client = OntarioGeoHubClient(rate_limit=30)
        assert client is not None
