"""Dataset registry for Ontario environmental data.

This module defines all available datasets in ONE central location.
Each dataset includes:
- Metadata (name, description, category)
- Collection function (how to collect the data)
- Validation rules (output path, format, required fields)
- Status (enabled/disabled)

This is the SINGLE SOURCE OF TRUTH for all datasets.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ontario_data import (
    WILLIAMS_TREATY_FIRST_NATIONS,
    CommunityWellBeingClient,
    CWFISClient,
    EBirdClient,
    INaturalistClient,
    OntarioBoundariesClient,
    OntarioGeoHubClient,
    StatisticsCanadaWFSClient,
)

# Note: SatelliteDataClient not imported - satellite data has separate workflow

# Constants
DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
ONTARIO_BOUNDS = (41.7, -95.2, 56.9, -74.3)
WILLIAMS_TREATY_BOUNDS = (43.8, -80.2, 45.2, -78.0)


@dataclass
class DatasetDefinition:
    """Definition of a data source/dataset."""

    # Identification
    id: str
    name: str
    description: str

    # Categorization
    category: str  # boundaries, protected_areas, biodiversity, community, environmental

    # Collection
    collect_fn: Optional[Callable] = None  # Async function to collect this dataset

    # Static datasets (pre-processed, uploaded to S3)
    is_static: bool = False  # True if this is a pre-processed static dataset
    s3_url: Optional[str] = None  # S3 URL for static datasets
    local_path: Optional[Path] = None  # Local path for static datasets (for upload)

    # Output
    output_path: Optional[Path] = None  # Where the collected data is saved
    output_format: str = "geojson"  # geojson, json, csv

    # Validation
    min_records: int = 1
    required_fields: Optional[List[str]] = None

    # Status
    enabled: bool = True  # Can be disabled if deprecated or not working


# =============================================================================
# DATASET DEFINITIONS
# Each dataset is defined with its collection function inline
# =============================================================================

# -----------------------------------------------------------------------------
# Williams Treaty Communities
# -----------------------------------------------------------------------------
async def _collect_williams_treaty_communities() -> Dict[str, Any]:
    """Collect Williams Treaty Communities and reserves."""
    print("\n📍 Fetching Williams Treaty communities...")

    client = StatisticsCanadaWFSClient()
    communities_gdf = client.create_williams_treaty_data()

    output_file = OUTPUT_DIR / "communities" / "williams_treaty_communities.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    communities_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(communities_gdf)} communities")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(communities_gdf),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Williams Treaty Reserves
# -----------------------------------------------------------------------------
async def _collect_williams_treaty_reserves() -> Dict[str, Any]:
    """Collect Williams Treaty reserve boundaries by filtering Ontario reserves."""
    print("\n📍 Fetching Williams Treaty reserve boundaries...")

    # Get all Ontario reserves first
    client = StatisticsCanadaWFSClient()
    all_reserves_gdf = await client.get_reserve_boundaries(
        province="ON", max_features=1000
    )

    if all_reserves_gdf.empty:
        return {"status": "no_data"}

    # Filter to Williams Treaty First Nations
    # Match against reserve names that contain the First Nation names
    williams_reserves = all_reserves_gdf[
        all_reserves_gdf["adminAreaNameEng"].str.contains(
            "|".join(WILLIAMS_TREATY_FIRST_NATIONS), case=False, na=False
        )
    ]

    if williams_reserves.empty:
        print("⚠️  No Williams Treaty reserves found in Ontario reserves data")
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "communities" / "williams_treaty_reserves.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    williams_reserves.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(williams_reserves)} Williams Treaty reserve boundaries")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(williams_reserves),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Williams Treaty Boundaries
# -----------------------------------------------------------------------------
async def _collect_williams_treaty_boundaries() -> Dict[str, Any]:
    """Collect Williams Treaty boundary polygon."""
    print("\n🗺️  Fetching Williams Treaty boundary...")

    client = OntarioBoundariesClient()
    boundaries_gdf = await client.get_treaty_boundaries()

    if boundaries_gdf.empty:
        return {"status": "no_data"}

    # Filter to Williams Treaty
    williams_gdf = boundaries_gdf[
        boundaries_gdf["ENAME"].str.contains("Williams", case=False, na=False)
    ]

    if williams_gdf.empty:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "boundaries" / "williams_treaty.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    williams_gdf.to_file(output_file, driver="GeoJSON")

    print("✅ Saved Williams Treaty boundary")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(williams_gdf),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Ontario Reserves
# -----------------------------------------------------------------------------
async def _collect_ontario_reserves() -> Dict[str, Any]:
    """Collect all Ontario First Nations reserves."""
    print("\n📍 Fetching Ontario reserve boundaries...")

    client = StatisticsCanadaWFSClient()
    reserves_gdf = await client.get_reserve_boundaries(province="ON", max_features=1000)

    if reserves_gdf.empty:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "boundaries" / "ontario_reserves.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    reserves_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(reserves_gdf)} reserve boundaries")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(reserves_gdf),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# iNaturalist
# -----------------------------------------------------------------------------
async def _collect_inaturalist() -> Dict[str, Any]:
    """Collect iNaturalist observations."""
    print("\n🦋 Fetching iNaturalist observations...")

    client = INaturalistClient()
    observations = await client.fetch(
        bounds=ONTARIO_BOUNDS,
        start_date="2024-01-01",
        quality_grade="research",
        max_results=10000,
    )

    if not observations:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "inaturalist_observations_2024.json"
    with open(output_file, "w") as f:
        json.dump(observations, f, indent=2)

    species = {obs.get("scientific_name") for obs in observations}

    print(f"✅ Saved {len(observations)} observations")
    print(f"   Unique species: {len(species)}")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(observations),
        "species": len(species),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# eBird
# -----------------------------------------------------------------------------
async def _collect_ebird() -> Dict[str, Any]:
    """Collect eBird observations."""
    api_key = os.getenv("EBIRD_API_KEY")
    if not api_key:
        print("⚠️  EBIRD_API_KEY not set")
        return {"status": "skipped", "note": "API key not provided"}

    print("\n🦅 Fetching eBird observations...")

    client = EBirdClient(api_key=api_key)
    observations = await client.fetch(region_code="CA-ON", back_days=30)

    if not observations:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "ebird_observations_recent.json"
    with open(output_file, "w") as f:
        json.dump(observations, f, indent=2)

    species = {obs.get("species_code") for obs in observations}

    print(f"✅ Saved {len(observations)} bird observations")
    print(f"   Unique species: {len(species)}")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(observations),
        "species": len(species),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Community Well-Being
# -----------------------------------------------------------------------------
async def _collect_community_wellbeing() -> Dict[str, Any]:
    """Collect Community Well-Being Index data."""
    csv_file = RAW_DIR / "CWB_2021.csv"
    if not csv_file.exists():
        print(f"⚠️  CSV file not found: {csv_file}")
        return {"status": "skipped", "note": "CSV file missing"}

    print("\n📊 Fetching Community Well-Being data...")

    client = CommunityWellBeingClient()
    cwb_gdf = await client.get_cwb_with_boundaries(
        csv_path=csv_file,
        province="ON",
        first_nations_only=False
    )

    if cwb_gdf.empty:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "cwb" / "community_wellbeing_ontario.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cwb_gdf.to_file(output_file, driver="GeoJSON")

    avg_score = cwb_gdf["cwb_score"].mean() if "cwb_score" in cwb_gdf.columns else None

    print(f"✅ Saved {len(cwb_gdf)} Ontario communities")
    if avg_score:
        print(f"   Average CWB score: {avg_score:.1f}")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(cwb_gdf),
        "average_score": float(avg_score) if avg_score else None,
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Conservation Authorities
# -----------------------------------------------------------------------------
async def _collect_conservation_authorities() -> Dict[str, Any]:
    """Collect Conservation Authority boundaries."""
    print("\n🌳 Fetching conservation authorities...")

    client = OntarioGeoHubClient()
    ca_gdf = await client.get_conservation_authorities()

    if ca_gdf.empty:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "conservation_authorities.geojson"
    ca_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(ca_gdf)} conservation authorities")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(ca_gdf),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Ontario Provincial Boundary
# -----------------------------------------------------------------------------
async def _collect_ontario_boundary() -> Dict[str, Any]:
    """Collect Ontario provincial boundary from local shapefile."""
    import geopandas as gpd

    shapefile = RAW_DIR / "lpr_000b21a_e.shp"

    if not shapefile.exists():
        print(f"⚠️  Provincial boundary shapefile not found: {shapefile}")
        return {"status": "skipped", "note": "Shapefile not found"}

    print("\n🗺️  Loading Ontario provincial boundary from shapefile...")

    # Read the shapefile
    all_provinces_gdf = gpd.read_file(shapefile)

    # Filter to Ontario (PRUID = 35)
    ontario_gdf = all_provinces_gdf[all_provinces_gdf["PRUID"] == "35"].copy()

    if ontario_gdf.empty:
        return {"status": "no_data"}

    # Ensure CRS is WGS84 for web compatibility
    if ontario_gdf.crs and ontario_gdf.crs.to_epsg() != 4326:
        ontario_gdf = ontario_gdf.to_crs(epsg=4326)

    output_file = OUTPUT_DIR / "boundaries" / "ontario_boundary.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ontario_gdf.to_file(output_file, driver="GeoJSON")

    print("✅ Saved Ontario provincial boundary")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(ontario_gdf),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Ontario Municipalities
# -----------------------------------------------------------------------------
async def _collect_ontario_municipalities() -> Dict[str, Any]:
    """Collect Ontario municipal boundaries."""
    print("\n🏛️  Fetching Ontario municipalities...")

    client = OntarioBoundariesClient()
    municipalities_gdf = await client.get_municipalities(province="ON")

    if municipalities_gdf.empty:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "boundaries" / "ontario_municipalities.geojson"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    municipalities_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(municipalities_gdf)} municipalities")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(municipalities_gdf),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Watersheds
# -----------------------------------------------------------------------------
async def _collect_watersheds() -> Dict[str, Any]:
    """Collect Ontario watershed boundaries from local shapefile."""
    import geopandas as gpd

    shapefile = RAW_DIR / "ONT_WSHED_BDRY.shp"

    if not shapefile.exists():
        print(f"⚠️  Watershed shapefile not found: {shapefile}")
        return {"status": "skipped", "note": "Shapefile not found"}

    print("\n🌊 Loading Ontario watersheds from shapefile...")

    # Read the shapefile
    watersheds_gdf = gpd.read_file(shapefile)

    if watersheds_gdf.empty:
        return {"status": "no_data"}

    # Ensure CRS is WGS84 for web compatibility
    if watersheds_gdf.crs and watersheds_gdf.crs.to_epsg() != 4326:
        watersheds_gdf = watersheds_gdf.to_crs(epsg=4326)

    output_file = OUTPUT_DIR / "watersheds.geojson"
    watersheds_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(watersheds_gdf)} watersheds")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(watersheds_gdf),
        "file": str(output_file),
    }


# -----------------------------------------------------------------------------
# Fire Perimeters
# -----------------------------------------------------------------------------
async def _collect_fire_perimeters() -> Dict[str, Any]:
    """Collect historical fire perimeters."""
    print("\n🔥 Fetching fire perimeters (1976-2024)...")

    client = CWFISClient()
    fire_gdf = await client.get_fire_perimeters(
        bounds=None,
        start_year=1976,
        end_year=2024,
        province="ON"
    )

    if fire_gdf.empty:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "fire_perimeters_1976_2024.geojson"
    fire_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(fire_gdf)} fire perimeters")
    print("   Years: 1976-2024")
    print(f"   File: {output_file}")

    return {
        "status": "success",
        "count": len(fire_gdf),
        "years": "1976-2024",
        "file": str(output_file),
    }


# =============================================================================
# DATASET REGISTRY
# =============================================================================

DATASETS: Dict[str, DatasetDefinition] = {
    "williams_treaty_communities": DatasetDefinition(
        id="williams_treaty_communities",
        name="Williams Treaty Communities",
        description="Williams Treaty First Nations community points",
        category="boundaries",
        collect_fn=_collect_williams_treaty_communities,
        output_path=Path("data/processed/communities/williams_treaty_communities.geojson"),
        output_format="geojson",
        min_records=7,
        required_fields=["first_nation", "reserve_name"],
    ),

    "williams_treaty_boundaries": DatasetDefinition(
        id="williams_treaty_boundaries",
        name="Williams Treaty Boundaries",
        description="Williams Treaty territory boundary polygon",
        category="boundaries",
        collect_fn=None,  # Static dataset - manually curated, no collection needed
        output_path=Path("data/processed/boundaries/williams_treaty.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["ENAME"],
        enabled=True,  # Static file that should be served
    ),

    "ontario_reserves": DatasetDefinition(
        id="ontario_reserves",
        name="Ontario Reserves",
        description="First Nations reserves in Ontario",
        category="boundaries",
        collect_fn=_collect_ontario_reserves,
        output_path=Path("data/processed/boundaries/ontario_reserves.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["adminAreaNameEng"],
    ),

    "williams_treaty_reserves": DatasetDefinition(
        id="williams_treaty_reserves",
        name="Williams Treaty Reserves",
        description=(
            "Williams Treaty First Nations reserves "
            "(subset of ontario_reserves)"
        ),
        category="boundaries",
        collect_fn=_collect_williams_treaty_reserves,
        output_path=Path("data/processed/communities/williams_treaty_reserves.geojson"),
        output_format="geojson",
        min_records=6,
        required_fields=["adminAreaNameEng"],
    ),

    "provincial_parks": DatasetDefinition(
        id="provincial_parks",
        name="Provincial Parks",
        description="Ontario provincial parks boundaries",
        category="protected_areas",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/provincial_parks.geojson",
        local_path=Path("data/processed/provincial_parks.geojson"),
        output_path=Path("data/processed/provincial_parks.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
        enabled=True,  # Now available as static dataset
    ),

    "conservation_authorities": DatasetDefinition(
        id="conservation_authorities",
        name="Conservation Authorities",
        description="Conservation authority boundaries",
        category="protected_areas",
        collect_fn=_collect_conservation_authorities,
        output_path=Path("data/processed/conservation_authorities.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
    ),

    "inaturalist": DatasetDefinition(
        id="inaturalist",
        name="iNaturalist",
        description="iNaturalist biodiversity observations",
        category="biodiversity",
        collect_fn=_collect_inaturalist,
        output_path=Path("data/processed/inaturalist_observations_2024.json"),
        output_format="json",
        min_records=1,
    ),

    "ebird": DatasetDefinition(
        id="ebird",
        name="eBird",
        description="eBird bird observations",
        category="biodiversity",
        collect_fn=_collect_ebird,
        output_path=Path("data/processed/ebird_observations_recent.json"),
        output_format="json",
        min_records=1,
    ),

    "community_wellbeing": DatasetDefinition(
        id="community_wellbeing",
        name="Community Well-Being",
        description="Community Well-Being Index for Ontario",
        category="community",
        collect_fn=_collect_community_wellbeing,
        output_path=Path("data/processed/cwb/community_wellbeing_ontario.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["csd_name", "cwb_score"],
    ),

    "water_advisories": DatasetDefinition(
        id="water_advisories",
        name="Water Advisories",
        description="Indigenous water advisories",
        category="community",
        output_path=Path("data/processed/water_advisories.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["community_name", "latitude", "longitude"],
        enabled=False,  # CSV doesn't have required format
    ),

    "ontario_boundary": DatasetDefinition(
        id="ontario_boundary",
        name="Ontario Provincial Boundary",
        description="Ontario provincial boundary polygon",
        category="boundaries",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/ontario_boundary.geojson",
        local_path=Path("data/processed/boundaries/ontario_boundary.geojson"),
        collect_fn=_collect_ontario_boundary,  # Keep for local re-processing if needed
        output_path=Path("data/processed/boundaries/ontario_boundary.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["PRNAME"],
        enabled=True,  # Available as static dataset
    ),

    "ontario_municipalities": DatasetDefinition(
        id="ontario_municipalities",
        name="Ontario Municipalities",
        description="Ontario municipal boundaries (Census Subdivisions)",
        category="boundaries",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/ontario_municipalities.geojson",
        local_path=Path("data/processed/boundaries/ontario_municipalities.geojson"),
        collect_fn=_collect_ontario_municipalities,  # Keep for local re-processing if needed
        output_path=Path("data/processed/boundaries/ontario_municipalities.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["CSDNAME"],
    ),

    "environmental_organizations": DatasetDefinition(
        id="environmental_organizations",
        name="Environmental Organizations",
        description="Environmental charities and organizations in Ontario",
        category="organizations",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/organizations/environmental_organizations.geojson",
        local_path=Path("data/processed/charities/environmental_organizations.geojson"),
        output_path=Path("data/processed/charities/environmental_organizations.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
        enabled=True,
    ),

    "watersheds": DatasetDefinition(
        id="watersheds",
        name="Watersheds",
        description="Ontario watershed boundaries",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watersheds.geojson",
        local_path=Path("data/processed/watersheds.geojson"),
        collect_fn=_collect_watersheds,  # Keep for local re-processing if needed
        output_path=Path("data/processed/watersheds.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=[],  # Field names vary by shapefile source
    ),

    "fire_perimeters": DatasetDefinition(
        id="fire_perimeters",
        name="Fire Perimeters",
        description="Historical fire perimeters (1976-2024)",
        category="environmental",
        collect_fn=_collect_fire_perimeters,
        output_path=Path("data/processed/fire_perimeters_1976_2024.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["year"],
    ),

    # =========================================================================
    # NEW DATASETS - Added from Williams Treaty data pipeline
    # =========================================================================

    # Hydrology / Water
    "wetlands": DatasetDefinition(
        id="wetlands",
        name="Wetlands",
        description="Provincial wetlands with ecological significance ratings",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/wetlands.geojson",
        output_path=Path("data/datasets/environmental/wetlands.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "watercourses": DatasetDefinition(
        id="watercourses",
        name="Rivers & Streams",
        description="Ontario Hydro Network - rivers and streams",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watercourses.geojson",
        output_path=Path("data/datasets/environmental/watercourses.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "waterbodies": DatasetDefinition(
        id="waterbodies",
        name="Lakes & Ponds",
        description="Ontario Hydro Network - lakes and ponds",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/waterbodies.geojson",
        output_path=Path("data/datasets/environmental/waterbodies.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "watersheds_tertiary": DatasetDefinition(
        id="watersheds_tertiary",
        name="Tertiary Watersheds",
        description="Ontario Watershed Boundaries - Tertiary level drainage areas",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watersheds_tertiary.geojson",
        output_path=Path("data/datasets/environmental/watersheds_tertiary.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "watersheds_quaternary": DatasetDefinition(
        id="watersheds_quaternary",
        name="Quaternary Watersheds",
        description="Ontario Watershed Boundaries - Quaternary (smallest) drainage areas",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watersheds_quaternary.geojson",
        output_path=Path("data/datasets/environmental/watersheds_quaternary.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "lake_simcoe_watershed": DatasetDefinition(
        id="lake_simcoe_watershed",
        name="Lake Simcoe Watershed",
        description="Lake Simcoe Protection Act Watershed Boundary",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/lake_simcoe_watershed.geojson",
        output_path=Path("data/datasets/environmental/lake_simcoe_watershed.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "dams": DatasetDefinition(
        id="dams",
        name="Dams",
        description="Ontario Dam Inventory",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/dams.geojson",
        output_path=Path("data/datasets/environmental/dams.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # Ecology / Protected Areas
    "conservation_reserves": DatasetDefinition(
        id="conservation_reserves",
        name="Conservation Reserves",
        description="Ontario Conservation Reserves - regulated protected areas",
        category="protected_areas",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/conservation_reserves.geojson",
        output_path=Path("data/datasets/protected_areas/conservation_reserves.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "federal_protected": DatasetDefinition(
        id="federal_protected",
        name="Federal Protected Areas",
        description="Federal protected areas including National Parks and Wildlife Areas",
        category="protected_areas",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/federal_protected.geojson",
        output_path=Path("data/datasets/protected_areas/federal_protected.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "ecodistricts": DatasetDefinition(
        id="ecodistricts",
        name="Ecodistricts",
        description="Ontario Ecodistricts - ecological classification units",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/ecodistricts.geojson",
        output_path=Path("data/datasets/environmental/ecodistricts.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "ecoregions": DatasetDefinition(
        id="ecoregions",
        name="Ecoregions",
        description="Ontario Ecoregions - broad ecological classification zones",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/ecoregions.geojson",
        output_path=Path("data/datasets/environmental/ecoregions.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # Terrain
    "contours": DatasetDefinition(
        id="contours",
        name="Contour Lines",
        description="Topographic contour lines",
        category="environmental",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/contours.geojson",
        output_path=Path("data/datasets/environmental/contours.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # Recreation / Trails
    "trails": DatasetDefinition(
        id="trails",
        name="Recreational Trails",
        description="Ontario Recreational Trail Network",
        category="infrastructure",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/infrastructure/trails.geojson",
        output_path=Path("data/datasets/infrastructure/trails.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "trail_access_points": DatasetDefinition(
        id="trail_access_points",
        name="Trail Access Points",
        description="Ontario Trail Network access points and trailheads",
        category="infrastructure",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/infrastructure/trail_access_points.geojson",
        output_path=Path("data/datasets/infrastructure/trail_access_points.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # Biodiversity
    "ebird_observations": DatasetDefinition(
        id="ebird_observations",
        name="eBird Observations",
        description="Recent bird observations from eBird",
        category="biodiversity",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/biodiversity/ebird_observations.geojson",
        output_path=Path("data/datasets/biodiversity/ebird_observations.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # Community / Infrastructure
    "infrastructure_projects": DatasetDefinition(
        id="infrastructure_projects",
        name="Indigenous Infrastructure Projects",
        description="Indigenous infrastructure projects from ISC ICIM database",
        category="community",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/infrastructure_projects.geojson",
        output_path=Path("data/datasets/community/infrastructure_projects.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "federal_infrastructure": DatasetDefinition(
        id="federal_infrastructure",
        name="Federal Infrastructure Projects",
        description="Federal infrastructure projects (housing, transit, green infrastructure)",
        category="community",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/federal_infrastructure.geojson",
        output_path=Path("data/datasets/community/federal_infrastructure.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "water_advisories_data": DatasetDefinition(
        id="water_advisories_data",
        name="Water Advisories",
        description="Drinking water advisories for First Nations communities",
        category="community",
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/water_advisories.geojson",
        output_path=Path("data/datasets/community/water_advisories.geojson"),
        output_format="geojson",
        min_records=1,
    ),
}


def get_dataset(dataset_id: str) -> Optional[DatasetDefinition]:
    """Get dataset definition by ID."""
    return DATASETS.get(dataset_id)


def get_datasets_by_category(category: str) -> List[DatasetDefinition]:
    """Get all datasets in a category."""
    return [ds for ds in DATASETS.values() if ds.category == category]


def get_enabled_datasets() -> List[DatasetDefinition]:
    """Get all enabled datasets."""
    return [ds for ds in DATASETS.values() if ds.enabled]


def get_all_categories() -> List[str]:
    """Get all unique categories."""
    return sorted({ds.category for ds in DATASETS.values()})
