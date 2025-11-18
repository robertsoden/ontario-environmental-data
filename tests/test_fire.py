"""Tests for fire data source clients."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import geopandas as gpd
import pytest

from ontario_data.sources.fire import CWFISClient


class TestCWFISClient:
    """Tests for CWFISClient (Canadian Wildland Fire Information System)."""

    @pytest.fixture
    def mock_fire_response(self):
        """Create mock CWFIS WFS GeoJSON response."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "FIRE_ID": "ON2024001",
                        "AREA_HA": 1500.5,
                        "CAUSE": "Lightning",
                    },
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
                },
                {
                    "type": "Feature",
                    "properties": {
                        "FIRE_ID": "ON2024002",
                        "AREA_HA": 2300.0,
                        "CAUSE": "Human",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-78.3, 44.3],
                                [-78.2, 44.3],
                                [-78.2, 44.4],
                                [-78.3, 44.4],
                                [-78.3, 44.3],
                            ]
                        ],
                    },
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_get_fire_perimeters_success(self, mock_fire_response):
        """Test successful fire perimeter fetching."""
        client = CWFISClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_fire_response))

        with patch("aiohttp.ClientSession") as mock_session:
            # Properly configure the async context manager
            mock_get_context = AsyncMock()
            mock_get_context.__aenter__.return_value = mock_response
            mock_get_context.__aexit__.return_value = None

            # Make get() return the async context manager (use MagicMock, not AsyncMock)
            mock_session_instance = mock_session.return_value.__aenter__.return_value
            mock_session_instance.get = MagicMock(return_value=mock_get_context)

            gdf = await client.get_fire_perimeters(
                bounds=bounds, start_year=2024, end_year=2024
            )

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 2
            assert gdf.crs == "EPSG:4326"
            assert "year" in gdf.columns
            assert all(gdf["year"] == 2024)

    @pytest.mark.asyncio
    async def test_get_fire_perimeters_multiple_years(self, mock_fire_response):
        """Test fetching fire perimeters across multiple years."""
        client = CWFISClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_fire_response))

        with patch("aiohttp.ClientSession") as mock_session:
            # Properly configure the async context manager
            mock_get_context = AsyncMock()
            mock_get_context.__aenter__.return_value = mock_response
            mock_get_context.__aexit__.return_value = None

            # Make get() return the async context manager (use MagicMock, not AsyncMock)
            mock_session_instance = mock_session.return_value.__aenter__.return_value
            mock_session_instance.get = MagicMock(return_value=mock_get_context)

            gdf = await client.get_fire_perimeters(
                bounds=bounds, start_year=2022, end_year=2024
            )

            # Should aggregate across 3 years (2022, 2023, 2024)
            assert isinstance(gdf, gpd.GeoDataFrame)
            # Each year returns 2 features, so 3 years = 6 total
            assert len(gdf) == 6

    @pytest.mark.asyncio
    async def test_get_fire_perimeters_no_data(self):
        """Test handling when no fire data is found."""
        client = CWFISClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        # Empty FeatureCollection
        empty_response = {"type": "FeatureCollection", "features": []}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(empty_response))

        with patch("aiohttp.ClientSession") as mock_session:
            # Properly configure the async context manager
            mock_get_context = AsyncMock()
            mock_get_context.__aenter__.return_value = mock_response
            mock_get_context.__aexit__.return_value = None

            # Make get() return the async context manager (use MagicMock, not AsyncMock)
            mock_session_instance = mock_session.return_value.__aenter__.return_value
            mock_session_instance.get = MagicMock(return_value=mock_get_context)

            gdf = await client.get_fire_perimeters(
                bounds=bounds, start_year=2024, end_year=2024
            )

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 0

    @pytest.mark.asyncio
    async def test_get_fire_perimeters_http_error(self):
        """Test handling of HTTP errors."""
        client = CWFISClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        mock_response = AsyncMock()
        mock_response.status = 500

        with patch("aiohttp.ClientSession") as mock_session:
            # Properly configure the async context manager
            mock_get_context = AsyncMock()
            mock_get_context.__aenter__.return_value = mock_response
            mock_get_context.__aexit__.return_value = None

            # Make get() return the async context manager (use MagicMock, not AsyncMock)
            mock_session_instance = mock_session.return_value.__aenter__.return_value
            mock_session_instance.get = MagicMock(return_value=mock_get_context)

            # Should handle error gracefully and return empty GeoDataFrame
            gdf = await client.get_fire_perimeters(
                bounds=bounds, start_year=2024, end_year=2024
            )

            assert isinstance(gdf, gpd.GeoDataFrame)
            assert len(gdf) == 0

    @pytest.mark.asyncio
    async def test_get_current_fire_danger(self):
        """Test current fire danger method (stub implementation)."""
        client = CWFISClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        result = await client.get_current_fire_danger(bounds)

        assert isinstance(result, dict)
        assert "bounds" in result
        assert result["bounds"] == bounds
        assert "note" in result or "source_url" in result

    @pytest.mark.asyncio
    async def test_fetch_returns_list_of_dicts(self, mock_fire_response):
        """Test that fetch() returns list of dictionaries."""
        client = CWFISClient()
        bounds = (44.0, -79.0, 45.0, -78.0)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(mock_fire_response))

        with patch("aiohttp.ClientSession") as mock_session:
            # Properly configure the async context manager
            mock_get_context = AsyncMock()
            mock_get_context.__aenter__.return_value = mock_response
            mock_get_context.__aexit__.return_value = None

            # Make get() return the async context manager (use MagicMock, not AsyncMock)
            mock_session_instance = mock_session.return_value.__aenter__.return_value
            mock_session_instance.get = MagicMock(return_value=mock_get_context)

            fires = await client.fetch(bounds=bounds, start_year=2024, end_year=2024)

            assert isinstance(fires, list)
            assert len(fires) == 2
            assert all(isinstance(f, dict) for f in fires)
            assert "fire_id" in fires[0]
            assert "fire_year" in fires[0]
            assert "geometry" in fires[0]

    def test_client_initialization(self):
        """Test client initialization with default rate limit."""
        client = CWFISClient()
        assert client is not None

    def test_client_custom_rate_limit(self):
        """Test client initialization with custom rate limit."""
        client = CWFISClient(rate_limit=30)
        assert client is not None
