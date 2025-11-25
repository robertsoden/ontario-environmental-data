"""Dataset registry for Ontario environmental data.

This module defines all available datasets in ONE central location.
Each dataset includes:
- Metadata (name, description, category)
- Collection function (how to collect the data)
- Validation rules (output path, format, required fields)
- Visual styling (colors, opacity, stroke width)
- Scope (ontario or williams_treaty)
- Status (enabled/disabled)

This is the SINGLE SOURCE OF TRUTH for all datasets.
"""

import json
import os
from dataclasses import dataclass, field
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

# =============================================================================
# CONSTANTS
# =============================================================================

DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
ONTARIO_BOUNDS = (41.7, -95.2, 56.9, -74.3)
WILLIAMS_TREATY_BOUNDS = (43.8, -80.2, 45.2, -78.0)

# =============================================================================
# STYLE CONSTANTS - Color palette for map visualization
# =============================================================================

# Category colors - primary colors for each category
CATEGORY_COLORS = {
    "boundaries": "#4a4a4a",           # Dark gray for administrative boundaries
    "indigenous": "#8B4513",           # Saddle brown for Indigenous territories
    "protected_areas": "#228B22",      # Forest green for protected areas
    "biodiversity": "#9932CC",         # Dark orchid for wildlife/biodiversity
    "hydrology": "#4169E1",            # Royal blue for water features
    "environmental": "#2E8B57",        # Sea green for environmental features
    "infrastructure": "#CD853F",       # Peru (tan) for infrastructure
    "community": "#FF8C00",            # Dark orange for community data
    "organizations": "#6495ED",        # Cornflower blue for organizations
}

# Specific feature colors for fine-grained styling
FEATURE_COLORS = {
    # Boundaries
    "provincial_boundary": "#1a1a1a",
    "municipal_boundary": "#666666",
    "treaty_boundary": "#8B4513",
    "reserve_boundary": "#CD853F",

    # Hydrology
    "waterbody": "#4169E1",
    "watercourse": "#1E90FF",
    "wetland": "#20B2AA",
    "watershed": "#6495ED",
    "dam": "#4682B4",

    # Protected Areas
    "provincial_park": "#228B22",
    "conservation_reserve": "#32CD32",
    "conservation_authority": "#90EE90",
    "federal_protected": "#006400",

    # Biodiversity
    "bird_observation": "#9932CC",
    "wildlife_observation": "#BA55D3",
    "species_at_risk": "#FF1493",

    # Environmental
    "ecoregion": "#2E8B57",
    "ecodistrict": "#3CB371",
    "fire_perimeter": "#FF4500",
    "contour": "#8B8682",

    # Infrastructure
    "trail": "#CD853F",
    "trail_access": "#DEB887",

    # Community
    "community_point": "#FF8C00",
    "water_advisory": "#DC143C",
    "infrastructure_project": "#FFD700",

    # Organizations
    "organization": "#6495ED",
}

# Default style values
DEFAULT_STYLES = {
    "polygon": {
        "fill_opacity": 0.3,
        "stroke_width": 1,
        "stroke_opacity": 0.8,
    },
    "line": {
        "stroke_width": 2,
        "stroke_opacity": 0.8,
    },
    "point": {
        "point_radius": 6,
        "stroke_width": 1,
        "fill_opacity": 0.8,
    },
}


@dataclass
class DatasetStyle:
    """Visual styling for a dataset layer."""

    # Geometry type: "polygon", "line", "point"
    geometry_type: str = "polygon"

    # Colors (hex format)
    fill_color: Optional[str] = None
    stroke_color: Optional[str] = None

    # Opacity (0.0 - 1.0)
    fill_opacity: float = 0.3
    stroke_opacity: float = 0.8

    # Line/stroke width in pixels
    stroke_width: float = 1.0

    # Point-specific styling
    point_radius: float = 6.0

    # Legend display
    legend_label: Optional[str] = None  # Override name for legend

    # Icon for point features (e.g., "marker", "circle", "triangle")
    icon: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert style to dictionary for serialization."""
        return {
            "geometry_type": self.geometry_type,
            "fill_color": self.fill_color,
            "stroke_color": self.stroke_color,
            "fill_opacity": self.fill_opacity,
            "stroke_opacity": self.stroke_opacity,
            "stroke_width": self.stroke_width,
            "point_radius": self.point_radius,
            "legend_label": self.legend_label,
            "icon": self.icon,
        }


@dataclass
class DatasetDefinition:
    """Definition of a data source/dataset."""

    # Identification
    id: str
    name: str
    description: str

    # Categorization
    category: str  # boundaries, indigenous, protected_areas, biodiversity,
                   # hydrology, environmental, infrastructure, community, organizations

    # Scope - geographic extent of the dataset
    scope: str = "ontario"  # "ontario" or "williams_treaty"

    # Parent dataset (for filtered subsets like Williams Treaty versions)
    parent_dataset: Optional[str] = None  # ID of the parent dataset

    # Visual Styling
    style: Optional[DatasetStyle] = None

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
    # =========================================================================
    # BOUNDARIES - Administrative and political boundaries
    # =========================================================================

    "ontario_boundary": DatasetDefinition(
        id="ontario_boundary",
        name="Ontario Provincial Boundary",
        description=(
            "Official provincial boundary of Ontario, Canada. Derived from "
            "Statistics Canada census geography (2021). Use as a basemap layer "
            "or for clipping other datasets to provincial extent."
        ),
        category="boundaries",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["provincial_boundary"],
            stroke_color=FEATURE_COLORS["provincial_boundary"],
            fill_opacity=0.05,
            stroke_width=2,
            stroke_opacity=1.0,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/ontario_boundary.geojson",
        local_path=Path("data/processed/boundaries/ontario_boundary.geojson"),
        collect_fn=_collect_ontario_boundary,
        output_path=Path("data/processed/boundaries/ontario_boundary.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["PRNAME"],
        enabled=True,
    ),

    "ontario_municipalities": DatasetDefinition(
        id="ontario_municipalities",
        name="Ontario Municipalities",
        description=(
            "Municipal boundaries for Ontario including cities, towns, townships, "
            "and other census subdivisions. Source: Statistics Canada 2021 Census. "
            "Useful for local government analysis and regional planning."
        ),
        category="boundaries",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["municipal_boundary"],
            stroke_color=FEATURE_COLORS["municipal_boundary"],
            fill_opacity=0.1,
            stroke_width=1,
            stroke_opacity=0.6,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/ontario_municipalities.geojson",
        local_path=Path("data/processed/boundaries/ontario_municipalities.geojson"),
        collect_fn=_collect_ontario_municipalities,
        output_path=Path("data/processed/boundaries/ontario_municipalities.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["CSDNAME"],
    ),

    # =========================================================================
    # INDIGENOUS - First Nations territories, reserves, and communities
    # =========================================================================

    "ontario_reserves": DatasetDefinition(
        id="ontario_reserves",
        name="First Nations Reserves (Ontario)",
        description=(
            "All First Nations reserve boundaries in Ontario. Source: Indigenous "
            "Services Canada / Statistics Canada Aboriginal Lands dataset. Includes "
            "reserve name, First Nation affiliation, and administrative details."
        ),
        category="indigenous",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["reserve_boundary"],
            stroke_color=FEATURE_COLORS["reserve_boundary"],
            fill_opacity=0.4,
            stroke_width=2,
            stroke_opacity=0.9,
        ),
        collect_fn=_collect_ontario_reserves,
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/ontario_reserves.geojson",
        output_path=Path("data/processed/boundaries/ontario_reserves.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["adminAreaNameEng"],
    ),

    "williams_treaty_boundaries": DatasetDefinition(
        id="williams_treaty_boundaries",
        name="Williams Treaties Territory",
        description=(
            "Historical boundary of the Williams Treaties territory (1923). The "
            "Williams Treaties were signed between the Crown and the Chippewa and "
            "Mississauga First Nations, covering lands in central Ontario from "
            "Georgian Bay to the Ottawa River."
        ),
        category="indigenous",
        scope="williams_treaty",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["treaty_boundary"],
            stroke_color=FEATURE_COLORS["treaty_boundary"],
            fill_opacity=0.15,
            stroke_width=3,
            stroke_opacity=1.0,
            legend_label="Williams Treaties Territory (1923)",
        ),
        collect_fn=None,  # Static dataset - manually curated
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/williams_treaty.geojson",
        output_path=Path("data/processed/boundaries/williams_treaty.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["ENAME"],
        enabled=True,
    ),

    "williams_treaty_reserves": DatasetDefinition(
        id="williams_treaty_reserves",
        name="Williams Treaty Reserves",
        description=(
            "Reserve boundaries for the seven Williams Treaty First Nations: "
            "Alderville, Beausoleil, Chippewas of Georgina Island, Chippewas of "
            "Rama, Curve Lake, Hiawatha, and Mississaugas of Scugog Island. "
            "Filtered subset of Ontario reserves data."
        ),
        category="indigenous",
        scope="williams_treaty",
        parent_dataset="ontario_reserves",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["reserve_boundary"],
            stroke_color="#5D3A1A",  # Darker brown for emphasis
            fill_opacity=0.5,
            stroke_width=2.5,
            stroke_opacity=1.0,
        ),
        collect_fn=_collect_williams_treaty_reserves,
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/williams_treaty_reserves.geojson",
        output_path=Path("data/processed/communities/williams_treaty_reserves.geojson"),
        output_format="geojson",
        min_records=6,
        required_fields=["adminAreaNameEng"],
    ),

    "williams_treaty_communities": DatasetDefinition(
        id="williams_treaty_communities",
        name="Williams Treaty Communities",
        description=(
            "Community point locations for the seven Williams Treaty First Nations. "
            "Includes community name, First Nation, population data, and contact "
            "information where available. Use for community-level analysis and mapping."
        ),
        category="indigenous",
        scope="williams_treaty",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["community_point"],
            stroke_color="#FFFFFF",
            fill_opacity=0.9,
            stroke_width=2,
            point_radius=8,
            icon="circle",
        ),
        collect_fn=_collect_williams_treaty_communities,
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/williams_treaty_communities.geojson",
        output_path=Path("data/processed/communities/williams_treaty_communities.geojson"),
        output_format="geojson",
        min_records=7,
        required_fields=["first_nation", "reserve_name"],
    ),

    # =========================================================================
    # PROTECTED AREAS - Parks, conservation lands, and protected spaces
    # =========================================================================

    "provincial_parks": DatasetDefinition(
        id="provincial_parks",
        name="Provincial Parks",
        description=(
            "Ontario Provincial Parks managed by Ontario Parks. Includes operating "
            "parks, non-operating parks, and park reserves. Data includes park name, "
            "class (wilderness, natural environment, recreation, etc.), and area."
        ),
        category="protected_areas",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["provincial_park"],
            stroke_color=FEATURE_COLORS["provincial_park"],
            fill_opacity=0.35,
            stroke_width=1.5,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/provincial_parks.geojson",
        local_path=Path("data/processed/provincial_parks.geojson"),
        output_path=Path("data/processed/provincial_parks.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
        enabled=True,
    ),

    "conservation_reserves": DatasetDefinition(
        id="conservation_reserves",
        name="Conservation Reserves",
        description=(
            "Ontario Conservation Reserves - provincially regulated protected areas "
            "that protect representative natural areas and special landscapes. "
            "Managed under the Provincial Parks and Conservation Reserves Act."
        ),
        category="protected_areas",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["conservation_reserve"],
            stroke_color=FEATURE_COLORS["conservation_reserve"],
            fill_opacity=0.3,
            stroke_width=1.5,
            stroke_opacity=0.8,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/conservation_reserves.geojson",
        output_path=Path("data/datasets/protected_areas/conservation_reserves.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "conservation_authorities": DatasetDefinition(
        id="conservation_authorities",
        name="Conservation Authorities",
        description=(
            "Boundaries of Ontario's 36 Conservation Authorities - watershed-based "
            "organizations that deliver programs to protect and manage water and "
            "natural resources. Includes authority name and jurisdiction area."
        ),
        category="protected_areas",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["conservation_authority"],
            stroke_color="#2E8B57",
            fill_opacity=0.2,
            stroke_width=1.5,
            stroke_opacity=0.7,
        ),
        collect_fn=_collect_conservation_authorities,
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/conservation_authorities.geojson",
        output_path=Path("data/processed/conservation_authorities.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
    ),

    "federal_protected": DatasetDefinition(
        id="federal_protected",
        name="Federal Protected Areas",
        description=(
            "Federally protected areas in Ontario including National Parks, "
            "National Wildlife Areas, Migratory Bird Sanctuaries, and Marine "
            "Protected Areas. Source: Environment and Climate Change Canada."
        ),
        category="protected_areas",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["federal_protected"],
            stroke_color=FEATURE_COLORS["federal_protected"],
            fill_opacity=0.35,
            stroke_width=2,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/federal_protected.geojson",
        output_path=Path("data/datasets/protected_areas/federal_protected.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # =========================================================================
    # HYDROLOGY - Water features and watersheds
    # =========================================================================

    "waterbodies": DatasetDefinition(
        id="waterbodies",
        name="Lakes and Ponds",
        description=(
            "Lakes, ponds, and other standing water bodies from the Ontario Hydro "
            "Network (OHN). Includes waterbody name, type, and surface area. "
            "Provincial coverage with detailed geometry."
        ),
        category="hydrology",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["waterbody"],
            stroke_color=FEATURE_COLORS["waterbody"],
            fill_opacity=0.5,
            stroke_width=1,
            stroke_opacity=0.8,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/waterbodies.geojson",
        output_path=Path("data/datasets/environmental/waterbodies.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "watercourses": DatasetDefinition(
        id="watercourses",
        name="Rivers and Streams",
        description=(
            "Rivers, streams, and other flowing water features from the Ontario "
            "Hydro Network (OHN). Includes stream name, order, and flow direction. "
            "Essential for hydrological analysis and watershed studies."
        ),
        category="hydrology",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="line",
            stroke_color=FEATURE_COLORS["watercourse"],
            stroke_width=1.5,
            stroke_opacity=0.8,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watercourses.geojson",
        output_path=Path("data/datasets/environmental/watercourses.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "wetlands": DatasetDefinition(
        id="wetlands",
        name="Wetlands",
        description=(
            "Provincially Significant Wetlands (PSW) and other evaluated wetlands "
            "in Ontario. Includes wetland type (marsh, swamp, bog, fen), ecological "
            "significance rating, and evaluation status. Critical habitat data."
        ),
        category="hydrology",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["wetland"],
            stroke_color=FEATURE_COLORS["wetland"],
            fill_opacity=0.4,
            stroke_width=1,
            stroke_opacity=0.7,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/wetlands.geojson",
        output_path=Path("data/datasets/environmental/wetlands.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "watersheds": DatasetDefinition(
        id="watersheds",
        name="Primary Watersheds",
        description=(
            "Primary (major) watershed boundaries for Ontario. Represents the "
            "largest drainage units in the provincial watershed hierarchy. "
            "Use for broad-scale water resource planning and analysis."
        ),
        category="hydrology",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["watershed"],
            stroke_color=FEATURE_COLORS["watershed"],
            fill_opacity=0.15,
            stroke_width=2,
            stroke_opacity=0.8,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watersheds.geojson",
        local_path=Path("data/processed/watersheds.geojson"),
        collect_fn=_collect_watersheds,
        output_path=Path("data/processed/watersheds.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=[],
    ),

    "watersheds_tertiary": DatasetDefinition(
        id="watersheds_tertiary",
        name="Tertiary Watersheds",
        description=(
            "Tertiary watershed boundaries - medium-scale drainage areas within "
            "the Ontario watershed hierarchy. Useful for regional water management "
            "and environmental assessment at the sub-basin level."
        ),
        category="hydrology",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["watershed"],
            stroke_color="#5080C0",
            fill_opacity=0.1,
            stroke_width=1.5,
            stroke_opacity=0.6,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watersheds_tertiary.geojson",
        output_path=Path("data/datasets/environmental/watersheds_tertiary.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "watersheds_quaternary": DatasetDefinition(
        id="watersheds_quaternary",
        name="Quaternary Watersheds",
        description=(
            "Quaternary watershed boundaries - the smallest drainage units in "
            "Ontario's watershed hierarchy. Best for detailed local analysis, "
            "site-specific planning, and fine-scale hydrological modeling."
        ),
        category="hydrology",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["watershed"],
            stroke_color="#7090D0",
            fill_opacity=0.08,
            stroke_width=1,
            stroke_opacity=0.5,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watersheds_quaternary.geojson",
        output_path=Path("data/datasets/environmental/watersheds_quaternary.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "lake_simcoe_watershed": DatasetDefinition(
        id="lake_simcoe_watershed",
        name="Lake Simcoe Watershed",
        description=(
            "Lake Simcoe Protection Act watershed boundary. This specially "
            "designated watershed is protected under provincial legislation "
            "due to its ecological significance. Key area for Williams Treaty "
            "First Nations and regional water quality protection."
        ),
        category="hydrology",
        scope="williams_treaty",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color="#4169E1",
            stroke_color="#1E3A8A",
            fill_opacity=0.2,
            stroke_width=2.5,
            stroke_opacity=0.9,
            legend_label="Lake Simcoe Watershed (Protected)",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/lake_simcoe_watershed.geojson",
        output_path=Path("data/datasets/environmental/lake_simcoe_watershed.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_watersheds": DatasetDefinition(
        id="williams_treaty_watersheds",
        name="Watersheds (Williams Treaty)",
        description=(
            "Watershed boundaries clipped to Williams Treaty territory. Shows the "
            "hierarchical drainage basins from primary to quaternary levels within "
            "the treaty area. Essential for understanding water resources, drainage "
            "patterns, and environmental management in treaty lands."
        ),
        category="hydrology",
        scope="williams_treaty",
        parent_dataset="watersheds",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color="#4292c6",
            stroke_color="#08519c",
            fill_opacity=0.15,
            stroke_width=1.5,
            stroke_opacity=0.6,
            legend_label="Watersheds (Williams Treaty)",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/hydrology/williams_treaty_watersheds.geojson",
        output_path=Path("data/datasets/williams_treaty/watersheds.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "dams": DatasetDefinition(
        id="dams",
        name="Dams",
        description=(
            "Ontario Dam Inventory - locations of dams across the province. "
            "Includes dam name, type, height, purpose (hydroelectric, flood "
            "control, recreation), and ownership. Important for understanding "
            "water flow modifications and fish passage barriers."
        ),
        category="hydrology",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["dam"],
            stroke_color="#FFFFFF",
            fill_opacity=0.9,
            stroke_width=1.5,
            point_radius=5,
            icon="triangle",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/dams.geojson",
        output_path=Path("data/datasets/environmental/dams.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # =========================================================================
    # BIODIVERSITY - Species observations and wildlife data
    # =========================================================================

    "inaturalist": DatasetDefinition(
        id="inaturalist",
        name="iNaturalist Observations",
        description=(
            "Citizen science biodiversity observations from iNaturalist. Research-"
            "grade observations verified by the community. Includes species name, "
            "location, date, and observer. Updated periodically with recent data."
        ),
        category="biodiversity",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["wildlife_observation"],
            stroke_color="#FFFFFF",
            fill_opacity=0.7,
            stroke_width=1,
            point_radius=5,
            icon="circle",
        ),
        collect_fn=_collect_inaturalist,
        output_path=Path("data/processed/inaturalist_observations_2024.json"),
        output_format="json",
        min_records=1,
        enabled=False,  # Dynamic API dataset - use williams_treaty_inaturalist for static S3 data
    ),

    "ebird": DatasetDefinition(
        id="ebird",
        name="eBird Recent Observations",
        description=(
            "Recent bird sightings from eBird, the world's largest biodiversity "
            "citizen science project. Includes species, location, count, and "
            "observation date. Data refreshed from eBird API."
        ),
        category="biodiversity",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["bird_observation"],
            stroke_color="#FFFFFF",
            fill_opacity=0.7,
            stroke_width=1,
            point_radius=5,
            icon="circle",
        ),
        collect_fn=_collect_ebird,
        output_path=Path("data/processed/ebird_observations_recent.json"),
        output_format="json",
        min_records=1,
        enabled=False,  # Dynamic API dataset - use ebird_observations for static S3 data
    ),

    "ebird_observations": DatasetDefinition(
        id="ebird_observations",
        name="eBird Observations (Static)",
        description=(
            "Archived eBird bird observations for Ontario. Static dataset with "
            "historical bird sighting data. Use for trend analysis and seasonal "
            "distribution mapping."
        ),
        category="biodiversity",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["bird_observation"],
            stroke_color="#FFFFFF",
            fill_opacity=0.7,
            stroke_width=1,
            point_radius=4,
            icon="circle",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/biodiversity/ebird_observations.geojson",
        output_path=Path("data/datasets/biodiversity/ebird_observations.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # =========================================================================
    # ENVIRONMENTAL - Ecology, terrain, and natural hazards
    # =========================================================================

    "ecoregions": DatasetDefinition(
        id="ecoregions",
        name="Ecoregions",
        description=(
            "Ontario Ecoregions - broad ecological classification zones based on "
            "climate, landform, soil, and vegetation. Part of the national "
            "ecological framework. Useful for landscape-level ecological analysis."
        ),
        category="environmental",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["ecoregion"],
            stroke_color=FEATURE_COLORS["ecoregion"],
            fill_opacity=0.2,
            stroke_width=2,
            stroke_opacity=0.7,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/ecoregions.geojson",
        output_path=Path("data/datasets/environmental/ecoregions.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "ecodistricts": DatasetDefinition(
        id="ecodistricts",
        name="Ecodistricts",
        description=(
            "Ontario Ecodistricts - subdivisions of ecoregions representing areas "
            "with distinctive assemblages of landform, relief, geology, soil, "
            "vegetation, water, and fauna. Mid-scale ecological classification."
        ),
        category="environmental",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["ecodistrict"],
            stroke_color=FEATURE_COLORS["ecodistrict"],
            fill_opacity=0.15,
            stroke_width=1.5,
            stroke_opacity=0.6,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/ecodistricts.geojson",
        output_path=Path("data/datasets/environmental/ecodistricts.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "fire_perimeters": DatasetDefinition(
        id="fire_perimeters",
        name="Historical Fire Perimeters",
        description=(
            "Historical wildfire perimeters in Ontario from 1976-2024. Source: "
            "Canadian Wildland Fire Information System (CWFIS). Includes fire "
            "year, size, and cause where available. Essential for fire risk "
            "assessment and forest management planning."
        ),
        category="environmental",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["fire_perimeter"],
            stroke_color=FEATURE_COLORS["fire_perimeter"],
            fill_opacity=0.4,
            stroke_width=1,
            stroke_opacity=0.8,
        ),
        collect_fn=_collect_fire_perimeters,
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/fire_perimeters_1976_2024.geojson",
        output_path=Path("data/processed/fire_perimeters_1976_2024.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["year"],
    ),

    "contours": DatasetDefinition(
        id="contours",
        name="Topographic Contours",
        description=(
            "Topographic contour lines showing elevation intervals across Ontario. "
            "Derived from Digital Elevation Model data. Useful for terrain "
            "visualization and slope analysis."
        ),
        category="environmental",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="line",
            stroke_color=FEATURE_COLORS["contour"],
            stroke_width=0.5,
            stroke_opacity=0.5,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/contours.geojson",
        output_path=Path("data/datasets/environmental/contours.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # =========================================================================
    # INFRASTRUCTURE - Trails, access points, and built features
    # =========================================================================

    "trails": DatasetDefinition(
        id="trails",
        name="Recreational Trails",
        description=(
            "Ontario's recreational trail network including hiking, cycling, "
            "snowmobile, and multi-use trails. Source: Ontario Trail Network. "
            "Includes trail name, type, surface, and permitted uses."
        ),
        category="infrastructure",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="line",
            stroke_color=FEATURE_COLORS["trail"],
            stroke_width=2,
            stroke_opacity=0.8,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/infrastructure/trails.geojson",
        output_path=Path("data/datasets/infrastructure/trails.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "trail_access_points": DatasetDefinition(
        id="trail_access_points",
        name="Trail Access Points",
        description=(
            "Trailheads and access points for Ontario's recreational trail network. "
            "Includes parking availability, facilities, and trail connections. "
            "Useful for recreation planning and accessibility analysis."
        ),
        category="infrastructure",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["trail_access"],
            stroke_color="#8B4513",
            fill_opacity=0.9,
            stroke_width=1.5,
            point_radius=6,
            icon="marker",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/infrastructure/trail_access_points.geojson",
        output_path=Path("data/datasets/infrastructure/trail_access_points.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # =========================================================================
    # COMMUNITY - Social indicators, health, and services
    # =========================================================================

    "community_wellbeing": DatasetDefinition(
        id="community_wellbeing",
        name="Community Well-Being Index",
        description=(
            "Community Well-Being (CWB) Index scores for Ontario communities. "
            "Measures socio-economic well-being across income, education, housing, "
            "and labour force participation. Source: Indigenous Services Canada. "
            "Enables comparison between First Nations and non-First Nations communities."
        ),
        category="community",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["community_point"],
            stroke_color=FEATURE_COLORS["community_point"],
            fill_opacity=0.4,
            stroke_width=1,
            stroke_opacity=0.8,
        ),
        collect_fn=_collect_community_wellbeing,
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/community_wellbeing_ontario.geojson",
        output_path=Path("data/processed/cwb/community_wellbeing_ontario.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["csd_name", "cwb_score"],
    ),

    "water_advisories": DatasetDefinition(
        id="water_advisories",
        name="Drinking Water Advisories (Legacy)",
        description=(
            "Historical drinking water advisories for First Nations communities. "
            "This dataset is deprecated - use water_advisories_data instead."
        ),
        category="community",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["water_advisory"],
            stroke_color="#FFFFFF",
            fill_opacity=0.9,
            stroke_width=2,
            point_radius=8,
            icon="alert",
        ),
        output_path=Path("data/processed/water_advisories.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["community_name", "latitude", "longitude"],
        enabled=False,  # Deprecated
    ),

    "water_advisories_data": DatasetDefinition(
        id="water_advisories_data",
        name="Drinking Water Advisories",
        description=(
            "Current and historical drinking water advisories for First Nations "
            "communities in Ontario. Includes advisory type (boil water, do not "
            "consume), start date, and affected population. Critical public health data."
        ),
        category="community",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["water_advisory"],
            stroke_color="#FFFFFF",
            fill_opacity=0.9,
            stroke_width=2,
            point_radius=8,
            icon="alert",
            legend_label="Drinking Water Advisory",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/water_advisories.geojson",
        output_path=Path("data/datasets/community/water_advisories.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "infrastructure_projects": DatasetDefinition(
        id="infrastructure_projects",
        name="Indigenous Infrastructure Projects",
        description=(
            "Infrastructure projects in Indigenous communities from the Indigenous "
            "Services Canada ICIM database. Includes project type (water, housing, "
            "education), status, funding, and timeline. Tracks federal investments "
            "in First Nations infrastructure."
        ),
        category="community",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["infrastructure_project"],
            stroke_color="#B8860B",
            fill_opacity=0.85,
            stroke_width=1.5,
            point_radius=6,
            icon="square",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/infrastructure_projects.geojson",
        output_path=Path("data/datasets/community/infrastructure_projects.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "federal_infrastructure": DatasetDefinition(
        id="federal_infrastructure",
        name="Federal Infrastructure Projects",
        description=(
            "Federal infrastructure investments in Ontario including housing, "
            "transit, green infrastructure, and community facilities. Source: "
            "Infrastructure Canada. Tracks government investments in public "
            "infrastructure across the province."
        ),
        category="community",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color="#4682B4",
            stroke_color="#FFFFFF",
            fill_opacity=0.8,
            stroke_width=1.5,
            point_radius=5,
            icon="square",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/federal_infrastructure.geojson",
        output_path=Path("data/datasets/community/federal_infrastructure.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # =========================================================================
    # ORGANIZATIONS - Environmental groups and institutions
    # =========================================================================

    "environmental_organizations": DatasetDefinition(
        id="environmental_organizations",
        name="Environmental Organizations",
        description=(
            "Registered environmental charities and non-profit organizations in "
            "Ontario. Includes organization name, type (conservation, education, "
            "advocacy), location, and contact information. Source: CRA Charities "
            "Directorate with environmental focus filter."
        ),
        category="organizations",
        scope="ontario",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["organization"],
            stroke_color="#FFFFFF",
            fill_opacity=0.85,
            stroke_width=1.5,
            point_radius=6,
            icon="circle",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/organizations/environmental_organizations.geojson",
        local_path=Path("data/processed/charities/environmental_organizations.geojson"),
        output_path=Path("data/processed/charities/environmental_organizations.geojson"),
        output_format="geojson",
        min_records=1,
        required_fields=["name"],
        enabled=True,
    ),

    # =========================================================================
    # WILLIAMS TREATY REGIONAL DATASETS
    # Filtered subsets of Ontario-wide datasets for Williams Treaty territory
    # =========================================================================

    "williams_treaty_provincial_parks": DatasetDefinition(
        id="williams_treaty_provincial_parks",
        name="Provincial Parks (Williams Treaty)",
        description=(
            "Provincial parks within and adjacent to Williams Treaty territory. "
            "Includes parks near Lake Simcoe, Kawartha Lakes, Georgian Bay, and "
            "other areas significant to Williams Treaty First Nations. Filtered "
            "from the provincial parks dataset."
        ),
        category="protected_areas",
        scope="williams_treaty",
        parent_dataset="provincial_parks",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["provincial_park"],
            stroke_color="#1B5E20",
            fill_opacity=0.4,
            stroke_width=2,
            stroke_opacity=1.0,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/williams_treaty_provincial_parks.geojson",
        output_path=Path("data/datasets/williams_treaty/provincial_parks.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_wetlands": DatasetDefinition(
        id="williams_treaty_wetlands",
        name="Wetlands (Williams Treaty)",
        description=(
            "Provincially Significant Wetlands and evaluated wetlands within "
            "Williams Treaty territory. Critical habitat for wildlife and important "
            "for water quality in the Lake Simcoe and Kawartha watersheds. Filtered "
            "to treaty territory bounds."
        ),
        category="hydrology",
        scope="williams_treaty",
        parent_dataset="wetlands",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["wetland"],
            stroke_color="#008B8B",
            fill_opacity=0.45,
            stroke_width=1.5,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/hydrology/williams_treaty_wetlands.geojson",
        output_path=Path("data/datasets/williams_treaty/wetlands.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_waterbodies": DatasetDefinition(
        id="williams_treaty_waterbodies",
        name="Lakes and Ponds (Williams Treaty)",
        description=(
            "Lakes, ponds, and other water bodies within Williams Treaty territory. "
            "Includes Lake Simcoe, Rice Lake, Scugog Lake, and the Kawartha Lakes - "
            "waters with deep cultural and historical significance to Williams Treaty "
            "First Nations."
        ),
        category="hydrology",
        scope="williams_treaty",
        parent_dataset="waterbodies",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["waterbody"],
            stroke_color="#1E3A8A",
            fill_opacity=0.55,
            stroke_width=1.5,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/hydrology/williams_treaty_waterbodies.geojson",
        output_path=Path("data/datasets/williams_treaty/waterbodies.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_watercourses": DatasetDefinition(
        id="williams_treaty_watercourses",
        name="Rivers and Streams (Williams Treaty)",
        description=(
            "Rivers, streams, and creeks within Williams Treaty territory. Includes "
            "the Trent-Severn Waterway corridor and tributaries to Lake Simcoe and "
            "the Kawartha Lakes. Important for fisheries and traditional activities."
        ),
        category="hydrology",
        scope="williams_treaty",
        parent_dataset="watercourses",
        style=DatasetStyle(
            geometry_type="line",
            stroke_color=FEATURE_COLORS["watercourse"],
            stroke_width=2,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/hydrology/williams_treaty_watercourses.geojson",
        output_path=Path("data/datasets/williams_treaty/watercourses.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_trails": DatasetDefinition(
        id="williams_treaty_trails",
        name="Recreational Trails (Williams Treaty)",
        description=(
            "Recreational trails within Williams Treaty territory. Includes portions "
            "of the Trans Canada Trail, Kawartha Highlands trails, and local hiking "
            "and cycling routes. Important for recreation and land access planning."
        ),
        category="infrastructure",
        scope="williams_treaty",
        parent_dataset="trails",
        style=DatasetStyle(
            geometry_type="line",
            stroke_color=FEATURE_COLORS["trail"],
            stroke_width=2.5,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/infrastructure/williams_treaty_trails.geojson",
        output_path=Path("data/datasets/williams_treaty/trails.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_conservation_authorities": DatasetDefinition(
        id="williams_treaty_conservation_authorities",
        name="Conservation Authorities (Williams Treaty)",
        description=(
            "Conservation Authority boundaries that overlap with Williams Treaty "
            "territory. Includes Lake Simcoe Region CA, Kawartha CA, Otonabee CA, "
            "and others. Key partners in watershed management and environmental "
            "protection in the region."
        ),
        category="protected_areas",
        scope="williams_treaty",
        parent_dataset="conservation_authorities",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["conservation_authority"],
            stroke_color="#1B5E20",
            fill_opacity=0.25,
            stroke_width=2,
            stroke_opacity=0.8,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/protected_areas/williams_treaty_conservation_authorities.geojson",
        output_path=Path("data/datasets/williams_treaty/conservation_authorities.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_ecodistricts": DatasetDefinition(
        id="williams_treaty_ecodistricts",
        name="Ecodistricts (Williams Treaty)",
        description=(
            "Ecodistricts within Williams Treaty territory showing the ecological "
            "classification of the region. Includes the Lake Simcoe-Rideau, "
            "Georgian Bay, and Algonquin-Lake Nipissing ecoregion subunits."
        ),
        category="environmental",
        scope="williams_treaty",
        parent_dataset="ecodistricts",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["ecodistrict"],
            stroke_color="#2E8B57",
            fill_opacity=0.2,
            stroke_width=2,
            stroke_opacity=0.8,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/williams_treaty_ecodistricts.geojson",
        output_path=Path("data/datasets/williams_treaty/ecodistricts.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_dams": DatasetDefinition(
        id="williams_treaty_dams",
        name="Dams (Williams Treaty)",
        description=(
            "Dams and water control structures within Williams Treaty territory. "
            "Includes structures on the Trent-Severn Waterway and tributaries. "
            "Important for understanding water flow modifications and fish passage "
            "issues in treaty waters."
        ),
        category="hydrology",
        scope="williams_treaty",
        parent_dataset="dams",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["dam"],
            stroke_color="#1E3A8A",
            fill_opacity=0.95,
            stroke_width=2,
            point_radius=6,
            icon="triangle",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/hydrology/williams_treaty_dams.geojson",
        output_path=Path("data/datasets/williams_treaty/dams.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_fire_perimeters": DatasetDefinition(
        id="williams_treaty_fire_perimeters",
        name="Historical Fires (Williams Treaty)",
        description=(
            "Historical wildfire perimeters within Williams Treaty territory. "
            "Shows fire history in the region from 1976-2024. Important for "
            "understanding forest management needs and ecological history."
        ),
        category="environmental",
        scope="williams_treaty",
        parent_dataset="fire_perimeters",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["fire_perimeter"],
            stroke_color="#B22222",
            fill_opacity=0.45,
            stroke_width=1.5,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/williams_treaty_fire_perimeters.geojson",
        output_path=Path("data/datasets/williams_treaty/fire_perimeters.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_municipalities": DatasetDefinition(
        id="williams_treaty_municipalities",
        name="Municipalities (Williams Treaty)",
        description=(
            "Municipal boundaries within and overlapping Williams Treaty territory. "
            "Includes cities, towns, and townships in the region such as Orillia, "
            "Peterborough, and municipalities around Lake Simcoe and Kawartha Lakes."
        ),
        category="boundaries",
        scope="williams_treaty",
        parent_dataset="ontario_municipalities",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["municipal_boundary"],
            stroke_color="#4a4a4a",
            fill_opacity=0.15,
            stroke_width=1.5,
            stroke_opacity=0.7,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/williams_treaty_municipalities.geojson",
        output_path=Path("data/datasets/williams_treaty/municipalities.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_trail_access_points": DatasetDefinition(
        id="williams_treaty_trail_access_points",
        name="Trail Access Points (Williams Treaty)",
        description=(
            "Trailheads and access points within Williams Treaty territory. Includes "
            "parking areas and facilities for trails in the Kawartha Highlands, "
            "Lake Simcoe region, and Georgian Bay area. Important for recreation "
            "planning and land access."
        ),
        category="infrastructure",
        scope="williams_treaty",
        parent_dataset="trail_access_points",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["trail_access"],
            stroke_color="#5D3A1A",
            fill_opacity=0.95,
            stroke_width=2,
            point_radius=7,
            icon="marker",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/infrastructure/williams_treaty_trail_access_points.geojson",
        output_path=Path("data/datasets/williams_treaty/trail_access_points.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_inaturalist": DatasetDefinition(
        id="williams_treaty_inaturalist",
        name="iNaturalist Observations (Williams Treaty)",
        description=(
            "Biodiversity observations from iNaturalist within Williams Treaty "
            "territory. Research-grade citizen science data showing species "
            "distribution in the Lake Simcoe, Kawartha, and Georgian Bay regions. "
            "Valuable for understanding local biodiversity and species at risk."
        ),
        category="biodiversity",
        scope="williams_treaty",
        parent_dataset="inaturalist",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["wildlife_observation"],
            stroke_color="#FFFFFF",
            fill_opacity=0.8,
            stroke_width=1.5,
            point_radius=6,
            icon="circle",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/biodiversity/williams_treaty_inaturalist.geojson",
        output_path=Path("data/datasets/williams_treaty/inaturalist.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_community_wellbeing": DatasetDefinition(
        id="williams_treaty_community_wellbeing",
        name="Community Well-Being (Williams Treaty)",
        description=(
            "Community Well-Being Index scores for communities within Williams "
            "Treaty territory. Enables comparison of socio-economic indicators "
            "between Williams Treaty First Nations and surrounding municipalities. "
            "Key data for understanding regional equity and service needs."
        ),
        category="community",
        scope="williams_treaty",
        parent_dataset="community_wellbeing",
        style=DatasetStyle(
            geometry_type="polygon",
            fill_color=FEATURE_COLORS["community_point"],
            stroke_color="#CC7000",
            fill_opacity=0.45,
            stroke_width=1.5,
            stroke_opacity=0.9,
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/williams_treaty_community_wellbeing.geojson",
        output_path=Path("data/datasets/williams_treaty/community_wellbeing.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_water_advisories": DatasetDefinition(
        id="williams_treaty_water_advisories",
        name="Drinking Water Advisories (Williams Treaty)",
        description=(
            "Drinking water advisories affecting Williams Treaty First Nations "
            "communities. Tracks current and historical boil water and do-not-consume "
            "advisories. Critical data for understanding water security and "
            "infrastructure needs in treaty communities."
        ),
        category="community",
        scope="williams_treaty",
        parent_dataset="water_advisories_data",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["water_advisory"],
            stroke_color="#8B0000",
            fill_opacity=0.95,
            stroke_width=2.5,
            point_radius=10,
            icon="alert",
            legend_label="Water Advisory (Williams Treaty)",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/williams_treaty_water_advisories.geojson",
        output_path=Path("data/datasets/williams_treaty/water_advisories.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    "williams_treaty_infrastructure_projects": DatasetDefinition(
        id="williams_treaty_infrastructure_projects",
        name="Infrastructure Projects (Williams Treaty)",
        description=(
            "Federal infrastructure investments in Williams Treaty First Nations "
            "communities. Includes water treatment, housing, education, and other "
            "capital projects funded through Indigenous Services Canada. Tracks "
            "progress on closing infrastructure gaps."
        ),
        category="community",
        scope="williams_treaty",
        parent_dataset="infrastructure_projects",
        style=DatasetStyle(
            geometry_type="point",
            fill_color=FEATURE_COLORS["infrastructure_project"],
            stroke_color="#8B6914",
            fill_opacity=0.95,
            stroke_width=2,
            point_radius=7,
            icon="square",
        ),
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/community/williams_treaty_infrastructure_projects.geojson",
        output_path=Path("data/datasets/williams_treaty/infrastructure_projects.geojson"),
        output_format="geojson",
        min_records=1,
    ),

    # =========================================================================
    # SATELLITE DATA - Raster datasets (NDVI, Land Cover)
    # =========================================================================

    "ndvi_2024": DatasetDefinition(
        id="ndvi_2024",
        name="NDVI 2024 (Vegetation Index)",
        description=(
            "Normalized Difference Vegetation Index (NDVI) for 2024 from MODIS 250m "
            "resolution satellite imagery. Measures vegetation health and density across "
            "Ontario. Served as Cloud Optimized GeoTIFF (COG) for efficient web access."
        ),
        category="environmental",
        scope="ontario",
        style=None,  # Raster styling handled by map renderer
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.amazonaws.com/datasets/satellite/ndvi/ontario_ndvi_2024_250m.tif",
        output_path=Path("datasets/satellite/ndvi/ontario_ndvi_2024_250m.tif"),
        output_format="tif",
        min_records=1,
        enabled=True,
    ),

    "landcover_2020": DatasetDefinition(
        id="landcover_2020",
        name="Land Cover 2020",
        description=(
            "North American Land Change Monitoring System (NALCMS) 2020 land cover "
            "classification for Ontario at 30m resolution. 15 land cover classes "
            "including forests, wetlands, cropland, and urban areas. Served as Cloud "
            "Optimized GeoTIFF (COG). Source: Natural Resources Canada."
        ),
        category="environmental",
        scope="ontario",
        style=None,  # Raster styling handled by map renderer
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.amazonaws.com/datasets/satellite/landcover/ontario_landcover_2020.tif",
        output_path=Path("datasets/satellite/landcover/ontario_landcover_2020.tif"),
        output_format="tif",
        min_records=1,
        enabled=True,
    ),

    "landcover_2015": DatasetDefinition(
        id="landcover_2015",
        name="Land Cover 2015",
        description=(
            "North American Land Change Monitoring System (NALCMS) 2015 land cover "
            "classification for Ontario at 30m resolution. Enables temporal analysis "
            "of land cover change when compared with 2010 and 2020 data. Served as "
            "Cloud Optimized GeoTIFF (COG). Source: Natural Resources Canada."
        ),
        category="environmental",
        scope="ontario",
        style=None,  # Raster styling handled by map renderer
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.amazonaws.com/datasets/satellite/landcover/ontario_landcover_2015.tif",
        output_path=Path("datasets/satellite/landcover/ontario_landcover_2015.tif"),
        output_format="tif",
        min_records=1,
        enabled=True,
    ),

    "landcover_2010": DatasetDefinition(
        id="landcover_2010",
        name="Land Cover 2010",
        description=(
            "North American Land Change Monitoring System (NALCMS) 2010 land cover "
            "classification for Ontario at 30m resolution. Baseline data for land "
            "cover change analysis over the 2010-2020 decade. Served as Cloud "
            "Optimized GeoTIFF (COG). Source: Natural Resources Canada."
        ),
        category="environmental",
        scope="ontario",
        style=None,  # Raster styling handled by map renderer
        is_static=True,
        s3_url="https://ontario-environmental-data.s3.amazonaws.com/datasets/satellite/landcover/ontario_landcover_2010.tif",
        output_path=Path("datasets/satellite/landcover/ontario_landcover_2010.tif"),
        output_format="tif",
        min_records=1,
        enabled=True,
    ),
}


def get_dataset(dataset_id: str) -> Optional[DatasetDefinition]:
    """Get dataset definition by ID."""
    return DATASETS.get(dataset_id)


def get_datasets_by_category(category: str) -> List[DatasetDefinition]:
    """Get all datasets in a category."""
    return [ds for ds in DATASETS.values() if ds.category == category]


def get_datasets_by_scope(scope: str) -> List[DatasetDefinition]:
    """Get all datasets for a specific scope (ontario or williams_treaty)."""
    return [ds for ds in DATASETS.values() if ds.scope == scope and ds.enabled]


def get_williams_treaty_datasets() -> List[DatasetDefinition]:
    """Get all datasets specific to Williams Treaty territory."""
    return get_datasets_by_scope("williams_treaty")


def get_ontario_datasets() -> List[DatasetDefinition]:
    """Get all Ontario-wide datasets."""
    return get_datasets_by_scope("ontario")


def get_enabled_datasets() -> List[DatasetDefinition]:
    """Get all enabled datasets."""
    return [ds for ds in DATASETS.values() if ds.enabled]


def get_all_categories() -> List[str]:
    """Get all unique categories."""
    return sorted({ds.category for ds in DATASETS.values()})


def get_all_scopes() -> List[str]:
    """Get all unique scopes."""
    return sorted({ds.scope for ds in DATASETS.values()})
