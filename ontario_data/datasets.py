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
from typing import Dict, List, Optional, Callable, Any

from ontario_data import (
    WILLIAMS_TREATY_FIRST_NATIONS,
    CommunityWellBeingClient,
    CWFISClient,
    EBirdClient,
    INaturalistClient,
    OntarioBoundariesClient,
    OntarioGeoHubClient,
    StatisticsCanadaWFSClient,
    WaterAdvisoriesClient,
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
    all_reserves_gdf = await client.get_reserve_boundaries(province="ON", max_features=1000)

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

    print(f"✅ Saved Williams Treaty boundary")
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

    species = set(obs.get("scientific_name") for obs in observations)

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

    species = set(obs.get("species_code") for obs in observations)

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
# Fire Perimeters
# -----------------------------------------------------------------------------
async def _collect_fire_perimeters() -> Dict[str, Any]:
    """Collect historical fire perimeters."""
    print("\n🔥 Fetching fire perimeters (1976-2024)...")

    client = CWFISClient()
    fire_gdf = await client.get_fire_perimeters(
        province="ON",
        start_year=1976,
        end_year=2024
    )

    if fire_gdf.empty:
        return {"status": "no_data"}

    output_file = OUTPUT_DIR / "fire_perimeters_1976_2024.geojson"
    fire_gdf.to_file(output_file, driver="GeoJSON")

    print(f"✅ Saved {len(fire_gdf)} fire perimeters")
    print(f"   Years: 1976-2024")
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
        description="Williams Treaty First Nations reserves (subset of ontario_reserves)",
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
        output_path=Path("data/processed/provincial_parks.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
        enabled=False,  # API is currently unreliable
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

    "watersheds": DatasetDefinition(
        id="watersheds",
        name="Watersheds",
        description="Great Lakes watershed boundaries",
        category="environmental",
        output_path=Path("data/processed/watersheds.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
        enabled=False,  # Not yet implemented
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
    return sorted(set(ds.category for ds in DATASETS.values()))
