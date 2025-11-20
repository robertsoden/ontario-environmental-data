#!/usr/bin/env python3
"""
Selective Data Collection Script

This script collects only the data sources selected via environment variables
(typically set by GitHub Actions workflow checkboxes).

Environment Variables:
  COLLECT_WILLIAMS_TREATY_COMMUNITIES - Set to 'true' to collect
  COLLECT_WILLIAMS_TREATY_BOUNDARIES - Set to 'true' to collect
  COLLECT_WATER_ADVISORIES - Set to 'true' to collect
  COLLECT_FIRE_PERIMETERS - Set to 'true' to collect
  COLLECT_PROVINCIAL_PARKS - Set to 'true' to collect
  COLLECT_CONSERVATION_AUTHORITIES - Set to 'true' to collect
  COLLECT_INATURALIST - Set to 'true' to collect
  COLLECT_EBIRD - Set to 'true' to collect
  COLLECT_COMMUNITY_WELLBEING - Set to 'true' to collect
  COLLECT_WATERSHEDS - Set to 'true' to collect
  COLLECT_SATELLITE - Set to 'true' to collect

Set any to 'true' to collect that source.
If none are set, collects all available sources.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from ontario_data import (
    WILLIAMS_TREATY_FIRST_NATIONS,
    CommunityWellBeingClient,
    CWFISClient,
    EBirdClient,
    INaturalistClient,
    OntarioBoundariesClient,
    OntarioGeoHubClient,
    SatelliteDataClient,
    StatisticsCanadaWFSClient,
    WaterAdvisoriesClient,
)

# Configuration
DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Ontario bounds
ONTARIO_BOUNDS = (41.7, -95.2, 56.9, -74.3)
WILLIAMS_TREATY_BOUNDS = (43.8, -80.2, 45.2, -78.0)


def get_selected_sources():
    """Get list of selected data sources from environment variables.

    Returns dict with True for selected sources, False for unselected.
    If no environment variables are set at all, nothing is selected.
    """
    sources = {
        "WILLIAMS_TREATY_COMMUNITIES": os.getenv("COLLECT_WILLIAMS_TREATY_COMMUNITIES", "").lower() == "true",
        "WILLIAMS_TREATY_BOUNDARIES": os.getenv("COLLECT_WILLIAMS_TREATY_BOUNDARIES", "").lower() == "true",
        "WATER_ADVISORIES": os.getenv("COLLECT_WATER_ADVISORIES", "").lower() == "true",
        "FIRE_PERIMETERS": os.getenv("COLLECT_FIRE_PERIMETERS", "").lower() == "true",
        "PROVINCIAL_PARKS": os.getenv("COLLECT_PROVINCIAL_PARKS", "").lower() == "true",
        "CONSERVATION_AUTHORITIES": os.getenv("COLLECT_CONSERVATION_AUTHORITIES", "").lower() == "true",
        "INATURALIST": os.getenv("COLLECT_INATURALIST", "").lower() == "true",
        "EBIRD": os.getenv("COLLECT_EBIRD", "").lower() == "true",
        "COMMUNITY_WELLBEING": os.getenv("COLLECT_COMMUNITY_WELLBEING", "").lower() == "true",
        "WATERSHEDS": os.getenv("COLLECT_WATERSHEDS", "").lower() == "true",
        "SATELLITE": os.getenv("COLLECT_SATELLITE", "").lower() == "true",
    }

    return sources


async def collect_selected_data():
    """Collect only selected data sources."""

    selected = get_selected_sources()
    selected_count = sum(selected.values())

    print("=" * 80)
    print("DATA COLLECTION")
    print("=" * 80)
    print()

    if selected_count == 0:
        print("⚠️  No data sources selected!")
        print("   Please check at least one data source checkbox.")
        print()
        print("Available sources:")
        for source in selected.keys():
            print(f"  ⬜ {source.replace('_', ' ').title()}")
        return {"error": "No sources selected", "sources": {}}
    elif selected_count == len(selected):
        print(f"📦 Collecting ALL {len(selected)} data sources")
    else:
        print(f"📦 Collecting {selected_count}/{len(selected)} selected data sources")

    print()
    for source, is_selected in selected.items():
        status = "✅" if is_selected else "⬜"
        print(f"  {status} {source.replace('_', ' ').title()}")
    print()

    results = {
        "timestamp": datetime.now().isoformat(),
        "bounds": ONTARIO_BOUNDS,
        "sources": {},
        "selected_count": selected_count,
        "total_sources": len(selected),
    }

    # 1. Williams Treaty Communities
    if selected["WILLIAMS_TREATY_COMMUNITIES"] or selected["WILLIAMS_TREATY_BOUNDARIES"]:
        print("\n" + "=" * 80)
        print("WILLIAMS TREATY FIRST NATIONS DATA")
        print("=" * 80)

        try:
            client = StatisticsCanadaWFSClient()

            if selected["WILLIAMS_TREATY_COMMUNITIES"]:
                print("\n📍 Fetching community locations...")
                communities_gdf = client.create_williams_treaty_data()

                output_file = OUTPUT_DIR / "communities" / "williams_treaty_communities.geojson"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                communities_gdf.to_file(output_file, driver="GeoJSON")

                print(f"✅ Saved {len(communities_gdf)} communities")
                print(f"   File: {output_file}")

                results["sources"]["williams_treaty_communities"] = {
                    "status": "success",
                    "count": len(communities_gdf),
                    "file": str(output_file),
                }

            if selected["WILLIAMS_TREATY_BOUNDARIES"]:
                print("\n🗺️  Fetching treaty boundaries...")
                try:
                    boundaries_gdf = await client.get_reserve_boundaries(
                        province="ON",
                        first_nations=WILLIAMS_TREATY_FIRST_NATIONS,
                        max_features=100
                    )

                    if not boundaries_gdf.empty:
                        output_file = OUTPUT_DIR / "boundaries" / "williams_treaty.geojson"
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        boundaries_gdf.to_file(output_file, driver="GeoJSON")

                        print(f"✅ Saved {len(boundaries_gdf)} boundaries")
                        print(f"   File: {output_file}")

                        results["sources"]["williams_treaty_boundaries"] = {
                            "status": "success",
                            "count": len(boundaries_gdf),
                            "file": str(output_file),
                        }
                    else:
                        print("⚠️  No boundaries returned")
                        results["sources"]["williams_treaty_boundaries"] = {"status": "no_data"}
                except Exception as e:
                    print(f"❌ Error: {e}")
                    results["sources"]["williams_treaty_boundaries"] = {"status": "error", "error": str(e)}

        except Exception as e:
            print(f"❌ Error: {e}")
            results["sources"]["williams_treaty_communities"] = {"status": "error", "error": str(e)}

    # 2. Water Advisories
    if selected["WATER_ADVISORIES"]:
        print("\n" + "=" * 80)
        print("WATER ADVISORIES")
        print("=" * 80)

        csv_file = RAW_DIR / "water_advisories_historical.csv"
        if csv_file.exists():
            try:
                client = WaterAdvisoriesClient()
                advisories = await client.fetch_from_csv(csv_file, province="ON")

                if advisories:
                    output_file = OUTPUT_DIR / "water" / "water_advisories.json"
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_file, "w") as f:
                        json.dump(advisories, f, indent=2)

                    print(f"✅ Saved {len(advisories)} water advisories")
                    print(f"   File: {output_file}")

                    results["sources"]["water_advisories"] = {
                        "status": "success",
                        "count": len(advisories),
                        "file": str(output_file),
                    }
            except Exception as e:
                print(f"❌ Error: {e}")
                results["sources"]["water_advisories"] = {"status": "error", "error": str(e)}
        else:
            print(f"⚠️  CSV not found: {csv_file}")
            results["sources"]["water_advisories"] = {"status": "skipped", "note": "CSV file not found"}

    # 3. Fire Perimeters
    if selected["FIRE_PERIMETERS"]:
        print("\n" + "=" * 80)
        print("FIRE PERIMETERS (1976-2024)")
        print("=" * 80)

        try:
            client = CWFISClient()
            print("\n🔥 Fetching fire perimeters...")
            fire_gdf = await client.get_fire_perimeters(bounds=ONTARIO_BOUNDS, start_year=1976, end_year=2024)

            if not fire_gdf.empty:
                output_file = OUTPUT_DIR / "fire_perimeters_1976_2024.geojson"
                fire_gdf.to_file(output_file, driver="GeoJSON")

                print(f"✅ Saved {len(fire_gdf)} fire perimeters")
                print(f"   File: {output_file}")

                results["sources"]["fire_perimeters"] = {
                    "status": "success",
                    "count": len(fire_gdf),
                    "file": str(output_file),
                }
        except Exception as e:
            print(f"❌ Error: {e}")
            results["sources"]["fire_perimeters"] = {"status": "error", "error": str(e)}

    # 4. Provincial Parks
    if selected["PROVINCIAL_PARKS"]:
        print("\n" + "=" * 80)
        print("PROVINCIAL PARKS")
        print("=" * 80)

        try:
            client = OntarioGeoHubClient()
            print("\n🏞️  Fetching provincial parks...")

            # Retry logic
            parks_gdf = None
            for attempt in range(3):
                try:
                    parks_gdf = await client.get_provincial_parks(bounds=ONTARIO_BOUNDS)
                    if not parks_gdf.empty:
                        break
                    elif attempt < 2:
                        print(f"⚠️  Attempt {attempt + 1} returned no data, retrying...")
                        await asyncio.sleep(5)
                except Exception as retry_error:
                    if attempt < 2:
                        print(f"⚠️  Attempt {attempt + 1} failed: {retry_error}, retrying...")
                        await asyncio.sleep(5)
                    else:
                        raise

            if parks_gdf is not None and not parks_gdf.empty:
                output_file = OUTPUT_DIR / "provincial_parks.geojson"
                parks_gdf.to_file(output_file, driver="GeoJSON")

                print(f"✅ Saved {len(parks_gdf)} provincial parks")
                print(f"   File: {output_file}")

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

    # 5. Conservation Authorities
    if selected["CONSERVATION_AUTHORITIES"]:
        print("\n" + "=" * 80)
        print("CONSERVATION AUTHORITIES")
        print("=" * 80)

        try:
            client = OntarioGeoHubClient()
            print("\n🌳 Fetching conservation authorities...")
            ca_gdf = await client.get_conservation_authorities()

            if not ca_gdf.empty:
                output_file = OUTPUT_DIR / "conservation_authorities.geojson"
                ca_gdf.to_file(output_file, driver="GeoJSON")

                print(f"✅ Saved {len(ca_gdf)} conservation authorities")
                print(f"   File: {output_file}")

                results["sources"]["conservation_authorities"] = {
                    "status": "success",
                    "count": len(ca_gdf),
                    "file": str(output_file),
                }
        except Exception as e:
            print(f"❌ Error: {e}")
            results["sources"]["conservation_authorities"] = {"status": "error", "error": str(e)}

    # 6. iNaturalist
    if selected["INATURALIST"]:
        print("\n" + "=" * 80)
        print("INATURALIST OBSERVATIONS")
        print("=" * 80)

        try:
            client = INaturalistClient()
            print("\n🦋 Fetching iNaturalist observations...")
            observations = await client.fetch(
                bounds=ONTARIO_BOUNDS,
                start_date="2024-01-01",
                end_date="2024-12-31",
                quality_grade="research",
                per_page=200,
                max_results=10000
            )

            if observations:
                output_file = OUTPUT_DIR / "inaturalist_observations_2024.json"
                with open(output_file, "w") as f:
                    json.dump(observations, f, indent=2)

                species = {obs.get("scientific_name", "Unknown") for obs in observations}

                print(f"✅ Saved {len(observations)} observations")
                print(f"   Unique species: {len(species)}")
                print(f"   File: {output_file}")

                results["sources"]["inaturalist"] = {
                    "status": "success",
                    "count": len(observations),
                    "unique_species": len(species),
                    "file": str(output_file),
                }
        except Exception as e:
            print(f"❌ Error: {e}")
            results["sources"]["inaturalist"] = {"status": "error", "error": str(e)}

    # 7. eBird
    if selected["EBIRD"]:
        print("\n" + "=" * 80)
        print("EBIRD OBSERVATIONS")
        print("=" * 80)

        ebird_api_key = os.getenv("EBIRD_API_KEY")
        if ebird_api_key:
            try:
                client = EBirdClient(api_key=ebird_api_key)
                print("\n🦅 Fetching eBird observations...")
                observations = await client.fetch(region_code="CA-ON", back_days=30, max_results=5000)

                if observations:
                    output_file = OUTPUT_DIR / "ebird_observations_recent.json"
                    with open(output_file, "w") as f:
                        json.dump(observations, f, indent=2)

                    species = {obs.get("scientific_name", "Unknown") for obs in observations}

                    print(f"✅ Saved {len(observations)} bird observations")
                    print(f"   Unique species: {len(species)}")
                    print(f"   File: {output_file}")

                    results["sources"]["ebird"] = {
                        "status": "success",
                        "count": len(observations),
                        "unique_species": len(species),
                        "file": str(output_file),
                    }
            except Exception as e:
                print(f"❌ Error: {e}")
                results["sources"]["ebird"] = {"status": "error", "error": str(e)}
        else:
            print("⚠️  EBIRD_API_KEY not set")
            results["sources"]["ebird"] = {"status": "skipped", "note": "API key not provided"}

    # 8. Community Well-Being
    if selected["COMMUNITY_WELLBEING"]:
        print("\n" + "=" * 80)
        print("COMMUNITY WELL-BEING INDEX")
        print("=" * 80)

        csv_file = RAW_DIR / "CWB_2021.csv"
        if csv_file.exists():
            try:
                client = CommunityWellBeingClient()
                print("\n📊 Fetching Community Well-Being data...")
                cwb_gdf = await client.get_cwb_with_boundaries(
                    csv_path=csv_file,
                    province="ON",
                    first_nations_only=True
                )

                if not cwb_gdf.empty:
                    output_file = OUTPUT_DIR / "cwb" / "community_wellbeing_first_nations.geojson"
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    cwb_gdf.to_file(output_file, driver="GeoJSON")

                    avg_score = cwb_gdf["cwb_score"].mean() if "cwb_score" in cwb_gdf.columns else None

                    print(f"✅ Saved {len(cwb_gdf)} First Nations communities")
                    if avg_score:
                        print(f"   Average CWB score: {avg_score:.1f}")
                    print(f"   File: {output_file}")

                    results["sources"]["community_wellbeing"] = {
                        "status": "success",
                        "count": len(cwb_gdf),
                        "average_score": float(avg_score) if avg_score else None,
                        "file": str(output_file),
                    }
            except Exception as e:
                print(f"❌ Error: {e}")
                results["sources"]["community_wellbeing"] = {"status": "error", "error": str(e)}
        else:
            print(f"⚠️  CSV not found: {csv_file}")
            results["sources"]["community_wellbeing"] = {"status": "skipped", "note": "CSV file not found"}

    # 9. Watersheds
    if selected["WATERSHEDS"]:
        print("\n" + "=" * 80)
        print("WATERSHEDS")
        print("=" * 80)

        try:
            client = OntarioBoundariesClient()
            print("\n💧 Fetching Great Lakes watersheds...")
            watersheds_gdf = await client.get_watersheds(watershed_type="great_lakes")

            if not watersheds_gdf.empty:
                output_file = OUTPUT_DIR / "boundaries" / "great_lakes_watersheds.geojson"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                watersheds_gdf.to_file(output_file, driver="GeoJSON")

                print(f"✅ Saved {len(watersheds_gdf)} watersheds")
                print(f"   File: {output_file}")

                results["sources"]["watersheds"] = {
                    "status": "success",
                    "count": len(watersheds_gdf),
                    "file": str(output_file),
                }
        except Exception as e:
            print(f"❌ Error: {e}")
            results["sources"]["watersheds"] = {"status": "error", "error": str(e)}

    # 10. Satellite Data
    if selected["SATELLITE"]:
        print("\n" + "=" * 80)
        print("SATELLITE DATA METADATA")
        print("=" * 80)

        try:
            client = SatelliteDataClient()
            info = {
                "message": "Satellite data client initialized",
                "timestamp": datetime.now().isoformat(),
                "note": "Raster data requires manual download or optional dependencies"
            }

            output_file = OUTPUT_DIR / "satellite_data_info.json"
            with open(output_file, "w") as f:
                json.dump(info, f, indent=2)

            print(f"✅ Saved satellite metadata")
            print(f"   File: {output_file}")

            results["sources"]["satellite"] = {
                "status": "metadata_only",
                "file": str(output_file),
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            results["sources"]["satellite"] = {"status": "error", "error": str(e)}

    # Save collection report
    report_file = OUTPUT_DIR / "collection_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)

    successful = sum(1 for s in results["sources"].values() if s.get("status") == "success")
    failed = sum(1 for s in results["sources"].values() if s.get("status") == "error")
    skipped = sum(1 for s in results["sources"].values() if s.get("status") == "skipped")

    print(f"\n✅ Successful: {successful}")
    if failed > 0:
        print(f"❌ Failed: {failed}")
    if skipped > 0:
        print(f"⏭️  Skipped: {skipped}")

    print(f"\n📄 Collection report: {report_file}")

    return results


if __name__ == "__main__":
    print("\nStarting selective data collection...")
    print()

    results = asyncio.run(collect_selected_data())

    # Exit successfully - individual source failures are in the report
    sys.exit(0)
