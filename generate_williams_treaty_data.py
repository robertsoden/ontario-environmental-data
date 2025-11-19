#!/usr/bin/env python3
"""
Generate ALL data files for Williams Treaty Territories.

This script generates/downloads all data files needed for the williams-treaties
visualization project.
"""

import asyncio
from pathlib import Path

from ontario_data import (
    StatisticsCanadaWFSClient,
)

# Configuration
DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

# Williams Treaty reserve search keywords for NRCan database
# NRCan uses reserve names (not First Nation names), so we search by keywords
WILLIAMS_TREATY_KEYWORDS = [
    "ALDERVILLE",
    "CURVE LAKE",
    "HIAWATHA",
    "SCUGOG",
    "CHRISTIAN",  # Chippewas of Beausoleil (Christian Island)
    "GEORGINA",
    "RAMA",
]

# Ensure directories exist
(OUTPUT_DIR / "boundaries").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "communities").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "charities").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "infrastructure").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "water").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "cwb").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "csicp").mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("WILLIAMS TREATY TERRITORIES - COMPREHENSIVE DATA GENERATION")
print("=" * 80)
print()


async def generate_all_data():
    """Generate all possible data files."""

    results = {
        "generated": [],
        "skipped": [],
        "errors": [],
    }

    # ========================================================================
    # 1. FIRST NATIONS RESERVES (Auto-generate from NRCan REST API)
    # ========================================================================
    print("\n1. First Nations Reserves")
    print("-" * 80)

    try:
        client = StatisticsCanadaWFSClient()

        # 1a. Generate ALL Ontario reserves
        print("\n1a. Fetching ALL Ontario Indian Reserves...")
        all_reserves_gdf = await client.get_reserve_boundaries(
            province="ON", first_nations=None, max_features=500
        )

        if not all_reserves_gdf.empty:
            output_file = OUTPUT_DIR / "boundaries" / "ontario_reserves.geojson"
            all_reserves_gdf.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(all_reserves_gdf)} reserves)")
            results["generated"].append(str(output_file))
        else:
            print("⚠️  No reserve data returned from API")
            results["skipped"].append("ontario_reserves.geojson - API returned no data")

        # 1b. Generate Williams Treaty reserves only
        print("\n1b. Fetching Williams Treaty reserves...")
        print(f"Search keywords: {WILLIAMS_TREATY_KEYWORDS}")

        wt_reserves_gdf = await client.get_reserve_boundaries(
            province="ON", first_nations=WILLIAMS_TREATY_KEYWORDS, max_features=100
        )

        if not wt_reserves_gdf.empty:
            output_file = (
                OUTPUT_DIR / "communities" / "williams_treaty_reserves.geojson"
            )
            wt_reserves_gdf.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(wt_reserves_gdf)} reserves)")

            # List reserve names
            print("\nWilliams Treaty reserves found:")
            for _idx, row in wt_reserves_gdf.iterrows():
                print(f"  - {row['adminAreaNameEng']}")

            results["generated"].append(str(output_file))
        else:
            print("⚠️  No Williams Treaty reserve data returned from API")
            results["skipped"].append(
                "williams_treaty_reserves.geojson - API returned no data"
            )

    except Exception as e:
        print(f"❌ Error generating reserves: {e}")
        results["errors"].append(f"Reserves: {e}")

    # ========================================================================
    # 2. WATER ADVISORIES (Requires manual CSV)
    # ========================================================================
    print("\n2. Water Advisories")
    print("-" * 80)

    water_csv = RAW_DIR / "water_advisories.csv"
    if water_csv.exists():
        print(f"Found CSV: {water_csv}")
        try:
            from ontario_data import WaterAdvisoriesClient

            client = WaterAdvisoriesClient()
            advisories = await client.fetch_from_csv(water_csv, province="ON")

            # Convert to GeoDataFrame
            gdf = client.to_geodataframe(advisories)
            output_file = OUTPUT_DIR / "water" / "water_advisories.geojson"
            gdf.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(gdf)} advisories)")
            results["generated"].append(str(output_file))
        except Exception as e:
            print(f"❌ Error processing water advisories: {e}")
            results["errors"].append(f"Water advisories: {e}")
    else:
        print(f"⚠️  Skipped: {water_csv} not found")
        print(
            "   Download from: https://www.sac-isc.gc.ca/eng/1506514143353/1533317130660"
        )
        results["skipped"].append("water_advisories.geojson - CSV not downloaded")

    # ========================================================================
    # 3. COMMUNITY WELL-BEING (Requires manual CSV)
    # ========================================================================
    print("\n3. Community Well-Being")
    print("-" * 80)

    cwb_csv = RAW_DIR / "CWB_2021.csv"
    if cwb_csv.exists():
        print(f"Found CSV: {cwb_csv}")
        try:
            from ontario_data import CommunityWellBeingClient

            client = CommunityWellBeingClient()
            print("Fetching CWB data with census subdivision boundaries...")

            # Get CWB data with actual census boundaries
            gdf = await client.get_cwb_with_boundaries(
                cwb_csv,
                province="ON",
                first_nations_only=False,  # Get all communities for context
            )

            if not gdf.empty and "geometry" in gdf.columns:
                output_file = OUTPUT_DIR / "cwb" / "community_wellbeing.geojson"
                gdf.to_file(output_file, driver="GeoJSON")
                print(
                    f"✅ Generated: {output_file} ({len(gdf)} communities with boundaries)"
                )
                results["generated"].append(str(output_file))
            else:
                print("⚠️  No CWB data with boundaries returned")
                results["skipped"].append(
                    "community_wellbeing.geojson - No data with boundaries"
                )
        except Exception as e:
            print(f"❌ Error processing CWB data: {e}")
            import traceback

            traceback.print_exc()
            results["errors"].append(f"CWB: {e}")
    else:
        print(f"⚠️  Skipped: {cwb_csv} not found")
        print(
            "   Download from: https://www.sac-isc.gc.ca/eng/1419773101942/1419773233645"
        )
        results["skipped"].append("community_wellbeing.geojson - CSV not downloaded")

    # ========================================================================
    # 4. INFRASTRUCTURE (Requires manual CSV)
    # ========================================================================
    print("\n4. Infrastructure Projects")
    print("-" * 80)

    infra_csv = RAW_DIR / "ICIM_Export.csv"
    if infra_csv.exists():
        print(f"Found CSV: {infra_csv}")
        try:
            from ontario_data import InfrastructureClient

            client = InfrastructureClient()
            projects = await client.fetch_from_csv(infra_csv, province="ON")

            gdf = client.to_geodataframe(projects)
            output_file = (
                OUTPUT_DIR / "infrastructure" / "infrastructure_projects.geojson"
            )
            gdf.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(gdf)} projects)")
            results["generated"].append(str(output_file))
        except Exception as e:
            print(f"❌ Error processing infrastructure: {e}")
            results["errors"].append(f"Infrastructure: {e}")
    else:
        print(f"⚠️  Skipped: {infra_csv} not found")
        print("   Request export from Indigenous Services Canada ICIM")
        results["skipped"].append(
            "infrastructure_projects.geojson - CSV not downloaded"
        )

    # ========================================================================
    # 5. ONTARIO BOUNDARIES (Auto-generate from APIs and local shapefiles)
    # ========================================================================
    print("\n5. Ontario Administrative and Environmental Boundaries")
    print("-" * 80)

    try:
        from ontario_data import OntarioBoundariesClient

        boundaries_client = OntarioBoundariesClient()

        # 5a. Provincial boundary
        print("\n5a. Ontario Provincial Boundary...")
        try:
            ontario_boundary = await boundaries_client.get_provincial_boundary("ON")
            output_file = OUTPUT_DIR / "boundaries" / "ontario_boundary.geojson"
            ontario_boundary.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(ontario_boundary)} feature)")
            results["generated"].append(str(output_file))
        except FileNotFoundError:
            print("⚠️  Skipped: Provincial boundary shapefile not found")
            print(
                "   Download from: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index2021-eng.cfm?year=21"
            )
            print(
                "   Select: Provinces and territories, Cartographic boundary file, Shapefile"
            )
            print("   Extract lpr_000b21a_e.* files to data/raw/")
            results["skipped"].append(
                "ontario_boundary.geojson - Shapefile not downloaded"
            )

        # 5b. Municipal boundaries (all Ontario CSDs)
        print("\n5b. Ontario Municipal Boundaries...")
        try:
            municipalities = await boundaries_client.get_municipalities("ON")
            output_file = OUTPUT_DIR / "boundaries" / "ontario_municipalities.geojson"
            municipalities.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(municipalities)} municipalities)")
            results["generated"].append(str(output_file))
        except FileNotFoundError:
            print("⚠️  Skipped: Census subdivisions shapefile not found")
            print("   (This file is also needed for Community Well-Being data)")
            print(
                "   Download from: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000a21a_e.zip"
            )
            results["skipped"].append(
                "ontario_municipalities.geojson - Shapefile not downloaded"
            )

        # 5c. Conservation Authorities
        print("\n5c. Conservation Authority Boundaries...")
        try:
            authorities = await boundaries_client.get_conservation_authorities()
            output_file = OUTPUT_DIR / "boundaries" / "conservation_authorities.geojson"
            authorities.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(authorities)} authorities)")
            results["generated"].append(str(output_file))
        except Exception as e:
            print(f"❌ Error fetching conservation authorities: {e}")
            results["errors"].append(f"Conservation authorities: {e}")

        # 5d. Watersheds
        print("\n5d. Great Lakes Watershed Boundaries...")
        try:
            watersheds = await boundaries_client.get_watersheds("great_lakes")
            output_file = OUTPUT_DIR / "boundaries" / "great_lakes_watersheds.geojson"
            watersheds.to_file(output_file, driver="GeoJSON")
            print(f"✅ Generated: {output_file} ({len(watersheds)} watersheds)")
            results["generated"].append(str(output_file))
        except Exception as e:
            print(f"❌ Error fetching watersheds: {e}")
            results["errors"].append(f"Watersheds: {e}")

    except Exception as e:
        print(f"❌ Error generating boundary data: {e}")
        import traceback

        traceback.print_exc()
        results["errors"].append(f"Boundaries: {e}")

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print("GENERATION COMPLETE")
    print("=" * 80)
    print(f"\n✅ Generated: {len(results['generated'])} files")
    for f in results["generated"]:
        print(f"   - {f}")

    print(f"\n⚠️  Skipped: {len(results['skipped'])} files")
    for s in results["skipped"]:
        print(f"   - {s}")

    if results["errors"]:
        print(f"\n❌ Errors: {len(results['errors'])}")
        for e in results["errors"]:
            print(f"   - {e}")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\nFor manual data files, download and place in data/raw/:")
    print("\nCSV files:")
    print("  - water_advisories.csv")
    print("  - CWB_2021.csv")
    print("  - ICIM_Export.csv")
    print("\nShapefiles:")
    print("  - lpr_000b21a_e.* (Provincial boundaries)")
    print("  - lcsd000a21a_e.* (Census subdivisions - also used for CWB)")
    print("\nThen run this script again to process them.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(generate_all_data())
