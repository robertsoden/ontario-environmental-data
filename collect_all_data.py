#!/usr/bin/env python3
"""
Ontario Environmental Data - Full Data Collection Script

This script downloads and processes all available data sources.
Creates a complete dataset ready for use in ONW and williams-treaties projects.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from ontario_data import (
    WILLIAMS_TREATY_FIRST_NATIONS,
    CWFISClient,
    INaturalistClient,
    OntarioGeoHubClient,
    SatelliteDataClient,
    StatisticsCanadaWFSClient,
)

# Configuration
DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

# Ontario province bounds (full extent)
# From Point Pelee in the south to Hudson Bay coast in the north
# From Manitoba border in the west to Quebec border in the east
ONTARIO_BOUNDS = (41.7, -95.2, 56.9, -74.3)  # (swlat, swlng, nelat, nelng)

# Williams Treaty territory bounds (for reference)
WILLIAMS_TREATY_BOUNDS = (43.8, -80.2, 45.2, -78.0)  # (swlat, swlng, nelat, nelng)

# Create directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("ONTARIO ENVIRONMENTAL DATA - FULL DATA COLLECTION")
print("=" * 80)
print(f"\nData will be saved to: {OUTPUT_DIR.absolute()}")
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()


async def collect_all_data():
    """Download and process all available data sources."""

    results = {
        "timestamp": datetime.now().isoformat(),
        "bounds": ONTARIO_BOUNDS,
        "sources": {},
    }

    # ==========================================================================
    # 1. WILLIAMS TREATY FIRST NATIONS DATA
    # ==========================================================================
    print("\n" + "=" * 80)
    print("1. WILLIAMS TREATY FIRST NATIONS DATA")
    print("=" * 80)

    try:
        client = StatisticsCanadaWFSClient()

        # Get Williams Treaty community points (fallback data)
        print("\nFetching Williams Treaty First Nations community locations...")
        communities_gdf = client.create_williams_treaty_data()

        # Create communities directory
        communities_dir = OUTPUT_DIR / "communities"
        communities_dir.mkdir(parents=True, exist_ok=True)

        output_file_communities = (
            communities_dir / "williams_treaty_communities.geojson"
        )
        communities_gdf.to_file(output_file_communities, driver="GeoJSON")

        print(f"✅ Saved {len(communities_gdf)} First Nations community points")
        print(f"   File: {output_file_communities}")

        results["sources"]["williams_treaty_communities"] = {
            "status": "success",
            "count": len(communities_gdf),
            "file": str(output_file_communities),
            "first_nations": list(communities_gdf["first_nation"]),
        }

        # Try to fetch official reserve boundaries from WFS
        print(
            "\nAttempting to fetch official treaty boundary polygon from Statistics Canada WFS..."
        )
        try:
            official_gdf = await client.get_reserve_boundaries(
                province="ON",
                first_nations=WILLIAMS_TREATY_FIRST_NATIONS,
                max_features=100,
            )

            if not official_gdf.empty:
                # Create boundaries directory
                boundaries_dir = OUTPUT_DIR / "boundaries"
                boundaries_dir.mkdir(parents=True, exist_ok=True)

                output_file_boundaries = boundaries_dir / "williams_treaty.geojson"
                official_gdf.to_file(output_file_boundaries, driver="GeoJSON")
                print("✅ Saved Williams Treaty boundary polygon from Stats Canada")
                print(f"   File: {output_file_boundaries}")

                results["sources"]["williams_treaty_boundaries"] = {
                    "status": "success",
                    "count": len(official_gdf),
                    "file": str(output_file_boundaries),
                }
            else:
                print("⚠️  No official boundary polygon returned")
                print(
                    "   Note: Treaty boundary polygon should be manually added to data/processed/boundaries/"
                )
        except Exception as e:
            print(f"⚠️  Could not fetch official boundaries: {e}")
            print(
                "   Note: Treaty boundary polygon should be manually added to data/processed/boundaries/williams_treaty.geojson"
            )

    except Exception as e:
        print(f"❌ Error: {e}")
        results["sources"]["williams_treaty_communities"] = {
            "status": "error",
            "error": str(e),
        }

    # ==========================================================================
    # 2. FIRE PERIMETERS (CWFIS)
    # ==========================================================================
    print("\n" + "=" * 80)
    print("2. FIRE PERIMETERS (1976-2024)")
    print("=" * 80)

    try:
        client = CWFISClient()

        print("\nFetching fire perimeters for Ontario")
        print("This may take a few minutes for 50 years of data...")

        fire_gdf = await client.get_fire_perimeters(
            bounds=None,  # Not needed when using province filter
            start_year=1976,
            end_year=2024,
            province="ON",  # Use admin_area filter for province-wide data
        )

        if not fire_gdf.empty:
            output_file = OUTPUT_DIR / "fire_perimeters_1976_2024.geojson"
            fire_gdf.to_file(output_file, driver="GeoJSON")

            print(f"✅ Saved {len(fire_gdf)} fire perimeters")
            print(f"   File: {output_file}")
            print(f"   Years: {fire_gdf['year'].min()} - {fire_gdf['year'].max()}")

            results["sources"]["fire_perimeters"] = {
                "status": "success",
                "count": len(fire_gdf),
                "file": str(output_file),
                "year_range": [
                    int(fire_gdf["year"].min()),
                    int(fire_gdf["year"].max()),
                ],
            }
        else:
            print("⚠️  No fire perimeter data returned (may require manual download)")
            results["sources"]["fire_perimeters"] = {
                "status": "no_data",
                "note": "CWFIS data may require manual download from https://cwfis.cfs.nrcan.gc.ca/datamart",
            }

    except Exception as e:
        print(f"❌ Error: {e}")
        results["sources"]["fire_perimeters"] = {"status": "error", "error": str(e)}

    # ==========================================================================
    # 3. PROVINCIAL PARKS
    # ==========================================================================
    print("\n" + "=" * 80)
    print("3. ONTARIO PROVINCIAL PARKS")
    print("=" * 80)

    try:
        client = OntarioGeoHubClient()

        print(f"\nFetching provincial parks for bounds: {ONTARIO_BOUNDS}")

        parks_gdf = await client.get_provincial_parks(bounds=ONTARIO_BOUNDS)

        if not parks_gdf.empty:
            output_file = OUTPUT_DIR / "provincial_parks.geojson"
            parks_gdf.to_file(output_file, driver="GeoJSON")

            print(f"✅ Saved {len(parks_gdf)} provincial parks")
            print(f"   File: {output_file}")

            if "name" in parks_gdf.columns:
                print("\n   Parks found:")
                for name in parks_gdf["name"].head(10):
                    print(f"     • {name}")
                if len(parks_gdf) > 10:
                    print(f"     ... and {len(parks_gdf) - 10} more")

            results["sources"]["provincial_parks"] = {
                "status": "success",
                "count": len(parks_gdf),
                "file": str(output_file),
            }
        else:
            print("⚠️  No parks data returned")
            results["sources"]["provincial_parks"] = {"status": "no_data"}

    except Exception as e:
        print(f"❌ Error: {e}")
        results["sources"]["provincial_parks"] = {"status": "error", "error": str(e)}

    # ==========================================================================
    # 4. CONSERVATION AUTHORITIES
    # ==========================================================================
    print("\n" + "=" * 80)
    print("4. CONSERVATION AUTHORITIES")
    print("=" * 80)

    try:
        client = OntarioGeoHubClient()

        print(
            f"\nFetching conservation authority boundaries for bounds: {ONTARIO_BOUNDS}"
        )

        ca_gdf = await client.get_conservation_authorities(bounds=ONTARIO_BOUNDS)

        if not ca_gdf.empty:
            output_file = OUTPUT_DIR / "conservation_authorities.geojson"
            ca_gdf.to_file(output_file, driver="GeoJSON")

            print(f"✅ Saved {len(ca_gdf)} conservation authority boundaries")
            print(f"   File: {output_file}")

            results["sources"]["conservation_authorities"] = {
                "status": "success",
                "count": len(ca_gdf),
                "file": str(output_file),
            }
        else:
            print("⚠️  No conservation authority data returned")
            results["sources"]["conservation_authorities"] = {"status": "no_data"}

    except Exception as e:
        print(f"❌ Error: {e}")
        results["sources"]["conservation_authorities"] = {
            "status": "error",
            "error": str(e),
        }

    # ==========================================================================
    # 5. BIODIVERSITY - INATURALIST
    # ==========================================================================
    print("\n" + "=" * 80)
    print("5. BIODIVERSITY OBSERVATIONS (iNaturalist)")
    print("=" * 80)

    try:
        client = INaturalistClient()

        print("\nFetching iNaturalist observations for past year...")
        print(f"Bounds: {ONTARIO_BOUNDS}")

        observations = await client.fetch(
            bounds=ONTARIO_BOUNDS,
            start_date="2024-01-01",
            end_date="2024-12-31",
            quality_grade="research",
            per_page=500,  # Get substantial data
        )

        if observations:
            output_file = OUTPUT_DIR / "inaturalist_observations_2024.json"
            with open(output_file, "w") as f:
                json.dump(observations, f, indent=2)

            print(f"✅ Saved {len(observations)} iNaturalist observations")
            print(f"   File: {output_file}")

            # Get unique species
            species = {obs.get("scientific_name", "Unknown") for obs in observations}
            print(f"   Unique species: {len(species)}")

            results["sources"]["inaturalist"] = {
                "status": "success",
                "count": len(observations),
                "file": str(output_file),
                "unique_species": len(species),
                "year": 2024,
            }
        else:
            print("⚠️  No observations returned")
            results["sources"]["inaturalist"] = {"status": "no_data"}

    except Exception as e:
        print(f"❌ Error: {e}")
        print("   (This is normal if no internet connection)")
        results["sources"]["inaturalist"] = {"status": "error", "error": str(e)}

    # ==========================================================================
    # 6. SATELLITE DATA METADATA
    # ==========================================================================
    print("\n" + "=" * 80)
    print("6. SATELLITE DATA (Land Cover, NDVI, DEM)")
    print("=" * 80)

    try:
        client = SatelliteDataClient()

        print("\nGenerating satellite data metadata and download instructions...")

        # Generate province-wide NDVI (synthetic for demonstration)
        # Real data from Statistics Canada MODIS is 6-7 GB per year
        print("\nGenerating NDVI data for Ontario...")
        print("Note: Real MODIS data available from Statistics Canada (6-7 GB/year)")
        print("      Generating synthetic NDVI for demonstration purposes")

        satellite_info = {
            "land_cover": await client.get_land_cover(ONTARIO_BOUNDS, year=2020),
            "ndvi": await client.get_ndvi(
                ONTARIO_BOUNDS,
                "2024-06-01",
                "2024-06-30",
                output_path=OUTPUT_DIR / "ndvi" / "ndvi_ontario_2024-06.tif",
                resolution="250m",
            ),
            "dem": await client.get_elevation(ONTARIO_BOUNDS, resolution="20m"),
        }

        output_file = OUTPUT_DIR / "satellite_data_info.json"
        with open(output_file, "w") as f:
            json.dump(satellite_info, f, indent=2)

        print("✅ Saved satellite data metadata")
        print(f"   File: {output_file}")
        print("\n   📋 Download instructions:")
        print(
            f"   • Land Cover: {satellite_info['land_cover']['download_url']}"
            if satellite_info["land_cover"]
            else ""
        )
        print("   • NDVI: Requires Planetary Computer API")
        print(f"   • DEM: {satellite_info['dem']['download_url']}")

        results["sources"]["satellite"] = {
            "status": "metadata_only",
            "file": str(output_file),
            "note": "Raster data requires manual download or optional dependencies",
        }

    except Exception as e:
        print(f"❌ Error: {e}")
        results["sources"]["satellite"] = {"status": "error", "error": str(e)}

    # ==========================================================================
    # MANUAL DOWNLOAD INSTRUCTIONS
    # ==========================================================================
    print("\n" + "=" * 80)
    print("MANUAL DOWNLOADS REQUIRED")
    print("=" * 80)

    manual_downloads = {
        "water_advisories": {
            "source": "Indigenous Services Canada",
            "url": "https://www.sac-isc.gc.ca/eng/1506514143353/1533317130660",
            "format": "CSV",
            "save_to": str(RAW_DIR / "water_advisories.csv"),
            "usage": "WaterAdvisoriesClient().fetch_from_csv('data/raw/water_advisories.csv')",
        },
        "community_wellbeing": {
            "source": "Statistics Canada",
            "url": "https://www.sac-isc.gc.ca/eng/1419773101942/1419773233645",
            "format": "CSV (Latin-1 encoding)",
            "save_to": str(RAW_DIR / "CWB_2021.csv"),
            "usage": "CommunityWellBeingClient().fetch_from_csv('data/raw/CWB_2021.csv')",
        },
        "infrastructure": {
            "source": "Indigenous Services Canada ICIM",
            "url": "Request export from ISC",
            "format": "CSV (UTF-16, tab-delimited)",
            "save_to": str(RAW_DIR / "ICIM_Export.csv"),
            "usage": "InfrastructureClient().fetch_from_csv('data/raw/ICIM_Export.csv')",
        },
    }

    print("\nThe following datasets require manual download:\n")
    for name, info in manual_downloads.items():
        print(f"📥 {name.upper().replace('_', ' ')}")
        print(f"   Source: {info['source']}")
        print(f"   URL: {info['url']}")
        print(f"   Save to: {info['save_to']}")
        print(f"   Usage: {info['usage']}")
        print()

    results["manual_downloads"] = manual_downloads

    # ==========================================================================
    # SAVE COLLECTION REPORT
    # ==========================================================================
    report_file = OUTPUT_DIR / "collection_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)

    print("=" * 80)
    print("✅ DATA COLLECTION COMPLETE")
    print("=" * 80)
    print(f"\nCollection report saved to: {report_file}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Summary
    print("\n📊 SUMMARY:")
    successful = sum(
        1 for s in results["sources"].values() if s.get("status") == "success"
    )
    total = len(results["sources"])
    print(f"   • Successfully collected: {successful}/{total} data sources")
    print(f"   • Manual downloads required: {len(manual_downloads)}")
    print(f"   • Output directory: {OUTPUT_DIR.absolute()}")

    print("\n🗺️  Ready for use in:")
    print("   • Ontario Nature Watch (ONW) project")
    print("   • Williams Treaties mapping project")

    return results


# Run collection
if __name__ == "__main__":
    print("\nStarting data collection...")
    print("This will download data from multiple sources.\n")

    asyncio.run(collect_all_data())

    print("\n" + "=" * 80)
    print("Next steps:")
    print("  1. Download manual data files as listed above")
    print("  2. Check data/processed/ for all collected files")
    print("  3. Import into your projects using the ontario_data library")
    print("=" * 80)
