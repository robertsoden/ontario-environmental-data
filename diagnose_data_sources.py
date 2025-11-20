#!/usr/bin/env python3
"""
Diagnostic script to test connectivity and functionality of all data sources.
This helps identify which APIs are working vs failing, and why.
"""

import asyncio
import sys
from datetime import datetime

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


async def test_williams_treaty_communities():
    """Test Williams Treaty Communities (no external API)."""
    print(f"\n{BLUE}[1/6] Testing Williams Treaty Communities{RESET}")
    print("  Source: Internal/fallback data (no external API)")

    try:
        from ontario_data import StatisticsCanadaWFSClient

        client = StatisticsCanadaWFSClient()
        gdf = client.create_williams_treaty_data()

        if len(gdf) == 7:
            print(f"  {GREEN}✅ SUCCESS{RESET}: Got {len(gdf)} communities")
            return {"status": "success", "count": len(gdf), "error": None}
        else:
            print(f"  {YELLOW}⚠️  WARNING{RESET}: Expected 7 communities, got {len(gdf)}")
            return {"status": "partial", "count": len(gdf), "error": "Unexpected count"}

    except Exception as e:
        print(f"  {RED}❌ FAILED{RESET}: {type(e).__name__}: {e}")
        return {"status": "error", "count": 0, "error": str(e)}


async def test_provincial_parks():
    """Test Ontario Provincial Parks."""
    print(f"\n{BLUE}[2/6] Testing Provincial Parks{RESET}")
    print("  Source: ws.lioservices.lrc.gov.on.ca (Ontario GeoHub)")

    try:
        from ontario_data import OntarioGeoHubClient

        client = OntarioGeoHubClient()
        # Test with small area to make it fast
        test_bounds = (44.0, -79.0, 44.5, -78.5)

        print("  Attempting to fetch parks...")
        gdf = await client.get_provincial_parks(bounds=test_bounds)

        if len(gdf) > 0:
            print(f"  {GREEN}✅ SUCCESS{RESET}: Got {len(gdf)} parks in test area")
            return {"status": "success", "count": len(gdf), "error": None}
        else:
            print(f"  {YELLOW}⚠️  WARNING{RESET}: API returned 0 parks (may be network issue)")
            return {"status": "no_data", "count": 0, "error": "Empty result - possible API failure"}

    except Exception as e:
        error_msg = str(e)
        print(f"  {RED}❌ FAILED{RESET}: {type(e).__name__}")
        print(f"      Error: {error_msg}")

        if "Cannot connect" in error_msg or "name resolution" in error_msg:
            print(f"      {YELLOW}Diagnosis: Network/DNS issue - API unreachable{RESET}")

        return {"status": "error", "count": 0, "error": error_msg}


async def test_conservation_authorities():
    """Test Conservation Authorities."""
    print(f"\n{BLUE}[3/6] Testing Conservation Authorities{RESET}")
    print("  Source: ws.lioservices.lrc.gov.on.ca (Ontario GeoHub)")

    try:
        from ontario_data import OntarioGeoHubClient

        client = OntarioGeoHubClient()
        test_bounds = (44.0, -79.0, 44.5, -78.5)

        print("  Attempting to fetch conservation authorities...")
        gdf = await client.get_conservation_authorities(bounds=test_bounds)

        if len(gdf) > 0:
            print(f"  {GREEN}✅ SUCCESS{RESET}: Got {len(gdf)} authorities in test area")
            return {"status": "success", "count": len(gdf), "error": None}
        else:
            print(f"  {YELLOW}⚠️  WARNING{RESET}: API returned 0 authorities")
            return {"status": "no_data", "count": 0, "error": "Empty result - possible API failure"}

    except Exception as e:
        error_msg = str(e)
        print(f"  {RED}❌ FAILED{RESET}: {type(e).__name__}")
        print(f"      Error: {error_msg}")

        if "Cannot connect" in error_msg or "name resolution" in error_msg:
            print(f"      {YELLOW}Diagnosis: Network/DNS issue - API unreachable{RESET}")

        return {"status": "error", "count": 0, "error": error_msg}


async def test_fire_perimeters():
    """Test Fire Perimeters (CWFIS)."""
    print(f"\n{BLUE}[4/6] Testing Fire Perimeters{RESET}")
    print("  Source: cwfis.cfs.nrcan.gc.ca (Canadian Wildfire Info System)")

    try:
        from ontario_data import CWFISClient

        client = CWFISClient()

        print("  Attempting to fetch fire perimeters (2024 only for speed)...")
        gdf = await client.get_fire_perimeters(
            bounds=None,
            start_year=2024,
            end_year=2024,
            province="ON"
        )

        if len(gdf) > 0:
            print(f"  {GREEN}✅ SUCCESS{RESET}: Got {len(gdf)} fire perimeters for 2024")
            return {"status": "success", "count": len(gdf), "error": None}
        else:
            print(f"  {YELLOW}⚠️  WARNING{RESET}: API returned 0 fire perimeters")
            print("      Note: This might be normal if no fires in 2024, or API issue")
            return {"status": "no_data", "count": 0, "error": "Empty result - check logs for API errors"}

    except Exception as e:
        error_msg = str(e)
        print(f"  {RED}❌ FAILED{RESET}: {type(e).__name__}")
        print(f"      Error: {error_msg}")

        if "Cannot connect" in error_msg or "name resolution" in error_msg:
            print(f"      {YELLOW}Diagnosis: Network/DNS issue - API unreachable{RESET}")

        return {"status": "error", "count": 0, "error": error_msg}


async def test_inaturalist():
    """Test iNaturalist."""
    print(f"\n{BLUE}[5/6] Testing iNaturalist{RESET}")
    print("  Source: api.inaturalist.org")

    try:
        from ontario_data import INaturalistClient

        client = INaturalistClient()
        # Small test area
        test_bounds = (44.0, -79.0, 44.5, -78.5)

        print("  Attempting to fetch observations (max 10 for speed)...")
        observations = await client.fetch(
            bounds=test_bounds,
            quality_grade="research",
            max_results=10
        )

        if len(observations) > 0:
            print(f"  {GREEN}✅ SUCCESS{RESET}: Got {len(observations)} observations")
            return {"status": "success", "count": len(observations), "error": None}
        else:
            print(f"  {YELLOW}⚠️  WARNING{RESET}: API returned 0 observations")
            return {"status": "no_data", "count": 0, "error": "Empty result - possible API failure"}

    except Exception as e:
        error_msg = str(e)
        print(f"  {RED}❌ FAILED{RESET}: {type(e).__name__}")
        print(f"      Error: {error_msg}")

        if "Cannot connect" in error_msg or "name resolution" in error_msg:
            print(f"      {YELLOW}Diagnosis: Network/DNS issue - API unreachable{RESET}")

        return {"status": "error", "count": 0, "error": error_msg}


async def test_satellite():
    """Test Satellite Data Client."""
    print(f"\n{BLUE}[6/6] Testing Satellite Data Client{RESET}")
    print("  Source: Internal (metadata generation)")

    try:
        from ontario_data import SatelliteDataClient

        client = SatelliteDataClient()
        print(f"  {GREEN}✅ SUCCESS{RESET}: Client initialized")
        return {"status": "success", "count": 1, "error": None}

    except Exception as e:
        print(f"  {RED}❌ FAILED{RESET}: {type(e).__name__}: {e}")
        return {"status": "error", "count": 0, "error": str(e)}


async def main():
    """Run diagnostics on all data sources."""
    print("=" * 80)
    print("ONTARIO ENVIRONMENTAL DATA - API DIAGNOSTICS")
    print("=" * 80)
    print("\nTesting connectivity and functionality of all data sources...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run all tests
    results = {
        "williams_treaty_communities": await test_williams_treaty_communities(),
        "provincial_parks": await test_provincial_parks(),
        "conservation_authorities": await test_conservation_authorities(),
        "fire_perimeters": await test_fire_perimeters(),
        "inaturalist": await test_inaturalist(),
        "satellite": await test_satellite(),
    }

    # Summary
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)

    successful = sum(1 for r in results.values() if r["status"] == "success")
    failed = sum(1 for r in results.values() if r["status"] == "error")
    no_data = sum(1 for r in results.values() if r["status"] == "no_data")

    print(f"\n{GREEN}✅ Working:{RESET} {successful}/6 data sources")
    print(f"{RED}❌ Failed:{RESET}  {failed}/6 data sources")
    print(f"{YELLOW}⚠️  No Data:{RESET} {no_data}/6 data sources")

    if failed > 0:
        print(f"\n{RED}Failed Sources:{RESET}")
        for name, result in results.items():
            if result["status"] == "error":
                print(f"  • {name}")
                print(f"    Error: {result['error'][:100]}")

    if no_data > 0:
        print(f"\n{YELLOW}Sources Returning No Data:{RESET}")
        for name, result in results.items():
            if result["status"] == "no_data":
                print(f"  • {name}")
                print(f"    Reason: {result['error']}")

    print("\n" + "=" * 80)

    if successful == 6:
        print(f"{GREEN}✅ ALL DATA SOURCES WORKING{RESET}")
        print("=" * 80)
        return 0
    elif successful > 0:
        print(f"{YELLOW}⚠️  PARTIAL SUCCESS{RESET}")
        print("=" * 80)
        print(f"\n{successful}/6 data sources are working.")
        print("This is expected - the workflow will collect available data.")
        print("Check errors above to understand what's not working.")
        return 0  # Don't fail - partial success is OK
    else:
        print(f"{RED}❌ NO DATA SOURCES WORKING{RESET}")
        print("=" * 80)
        print("\nAll data sources failed. This likely indicates:")
        print("  • Network connectivity issues")
        print("  • DNS resolution problems")
        print("  • API outages")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
