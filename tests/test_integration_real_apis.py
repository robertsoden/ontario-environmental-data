"""Integration tests that make real API calls to validate data sources.

These tests actually call the real APIs to ensure they're working correctly.
They use small data requests to avoid rate limiting and long test times.

These tests may fail if:
- Network is unavailable
- API is down or changed
- Rate limits are hit
- Data format changes

Run with: pytest tests/test_integration_real_apis.py -v
Skip with: pytest tests/ -v -m "not integration"
"""

import os

import pytest

from ontario_data import (
    CWFISClient,
    INaturalistClient,
    OntarioGeoHubClient,
    StatisticsCanadaWFSClient,
)

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


# Small test bounds for faster tests
TEST_BOUNDS = (44.0, -79.0, 44.5, -78.5)  # Small area around Peterborough


@pytest.mark.asyncio
async def test_inaturalist_real_api():
    """Test real iNaturalist API call."""
    client = INaturalistClient()

    observations = await client.fetch(
        bounds=TEST_BOUNDS,
        quality_grade="research",
        per_page=10,  # Small request
    )

    # Basic validation
    assert isinstance(observations, list), "Should return a list"
    # Note: May return 0 observations for some bounds
    if len(observations) > 0:
        obs = observations[0]
        assert "scientific_name" in obs, "Should have scientific_name"
        assert "observation_date" in obs, "Should have observation_date"
        assert "location" in obs, "Should have location"


@pytest.mark.asyncio
async def test_cwfis_real_api():
    """Test real CWFIS API call."""
    client = CWFISClient()

    # Request recent year only
    gdf = await client.get_fire_perimeters(
        bounds=TEST_BOUNDS,
        start_year=2023,
        end_year=2023,
    )

    # Basic validation
    assert gdf is not None, "Should return a GeoDataFrame"
    assert hasattr(gdf, "geometry"), "Should have geometry column"
    # Note: May return empty GeoDataFrame if no fires in bounds
    if len(gdf) > 0:
        assert "year" in gdf.columns, "Should have year column"
        assert gdf["year"].iloc[0] == 2023, "Should return correct year"


@pytest.mark.asyncio
async def test_ontario_geohub_real_api_parks():
    """Test real Ontario GeoHub API call for provincial parks."""
    client = OntarioGeoHubClient()

    gdf = await client.get_provincial_parks(bounds=TEST_BOUNDS)

    # Basic validation
    assert gdf is not None, "Should return a GeoDataFrame"
    assert hasattr(gdf, "geometry"), "Should have geometry column"
    # Note: May return empty GeoDataFrame if no parks in small test bounds
    if len(gdf) > 0:
        assert "name" in gdf.columns, "Should have name column"


@pytest.mark.asyncio
async def test_statscan_wfs_williams_treaty_data():
    """Test Williams Treaty data creation (uses local data, not API)."""
    client = StatisticsCanadaWFSClient()

    gdf = client.create_williams_treaty_data()

    # This should always work as it uses local data
    assert gdf is not None, "Should return a GeoDataFrame"
    assert len(gdf) == 7, "Should have 7 Williams Treaty First Nations"
    assert "first_nation" in gdf.columns, "Should have first_nation column"
    assert "reserve_name" in gdf.columns, "Should have reserve_name column"
    assert all(gdf["province"] == "ON"), "All should be in Ontario"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_SLOW_TESTS"),
    reason="Slow test - set RUN_SLOW_TESTS=1 to run",
)
async def test_statscan_wfs_real_api():
    """Test real Statistics Canada WFS API call.

    This test is slow and may fail due to network issues.
    Only run when explicitly requested.
    """
    client = StatisticsCanadaWFSClient()

    # Try to fetch actual reserve boundaries
    gdf = await client.get_reserve_boundaries(
        province="ON",
        max_features=5,  # Small request
    )

    # Basic validation
    assert gdf is not None, "Should return a GeoDataFrame"
    assert hasattr(gdf, "geometry"), "Should have geometry column"
    # May return empty if service is down
    if len(gdf) > 0:
        assert "reserve_name" in gdf.columns, "Should have reserve_name column"
        assert "first_nation" in gdf.columns, "Should have first_nation column"


class TestDataSourceAvailability:
    """Tests that verify data sources are accessible and returning data."""

    @pytest.mark.asyncio
    async def test_all_critical_apis_accessible(self):
        """Verify all critical data sources are accessible.

        This is the key test that should fail if any critical API is broken.
        """
        results = {}

        # Test iNaturalist
        try:
            client = INaturalistClient()
            obs = await client.fetch(bounds=TEST_BOUNDS, per_page=1)
            results["inaturalist"] = {"accessible": True, "count": len(obs)}
        except Exception as e:
            results["inaturalist"] = {"accessible": False, "error": str(e)}

        # Test OntarioGeoHub (critical for parks data)
        try:
            client = OntarioGeoHubClient()
            gdf = await client.get_provincial_parks(bounds=TEST_BOUNDS)
            results["ontario_geohub"] = {"accessible": True, "count": len(gdf)}
        except Exception as e:
            results["ontario_geohub"] = {"accessible": False, "error": str(e)}

        # Test Williams Treaty data (critical)
        try:
            client = StatisticsCanadaWFSClient()
            gdf = client.create_williams_treaty_data()
            results["williams_treaty"] = {"accessible": True, "count": len(gdf)}
        except Exception as e:
            results["williams_treaty"] = {"accessible": False, "error": str(e)}

        # Print results for debugging
        print("\n=== Data Source Availability Test Results ===")
        for source, result in results.items():
            status = "✅" if result["accessible"] else "❌"
            if result["accessible"]:
                print(f"{status} {source}: OK (returned {result['count']} items)")
            else:
                print(f"{status} {source}: FAILED - {result['error']}")

        # Critical data sources that must be accessible
        critical_sources = ["ontario_geohub", "williams_treaty"]

        failed_critical = [
            source for source in critical_sources if not results[source]["accessible"]
        ]

        if failed_critical:
            pytest.fail(
                f"Critical data sources failed: {', '.join(failed_critical)}\n"
                f"Details: {[results[s]['error'] for s in failed_critical]}"
            )

        # Warn about non-critical failures
        non_critical = ["inaturalist"]
        failed_non_critical = [
            source for source in non_critical if not results[source]["accessible"]
        ]

        if failed_non_critical:
            print(
                f"\n⚠️  Warning: Non-critical sources failed: {', '.join(failed_non_critical)}"
            )
            # Don't fail test for non-critical sources
