#!/usr/bin/env python3
"""
Clip Ontario-wide datasets to Williams Treaty territory boundaries.

This script takes Ontario-wide datasets and clips/filters them to the Williams
Treaty territory bounds. It uses spatial operations to create regional subsets
of the data for the Williams Treaty First Nations mapping project.

Usage:
    python clip_williams_treaty_data.py
"""

import json
from pathlib import Path
from typing import Optional

import geopandas as gpd
from shapely.ops import unary_union

# Williams Treaty boundary file - the actual treaty territory polygon
WILLIAMS_TREATY_BOUNDARY_FILE = Path("data/boundaries/williams_treaty.geojson")

# Will be loaded at runtime
WILLIAMS_TREATY_BOUNDARY = None


def load_williams_treaty_boundary():
    """Load the actual Williams Treaty boundary polygon."""
    global WILLIAMS_TREATY_BOUNDARY

    boundary_paths = [
        WILLIAMS_TREATY_BOUNDARY_FILE,
        Path("data/processed/boundaries/williams_treaty.geojson"),
    ]

    for path in boundary_paths:
        if path.exists():
            gdf = gpd.read_file(path)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            elif gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs("EPSG:4326")
            WILLIAMS_TREATY_BOUNDARY = unary_union(gdf.geometry)
            print(f"Loaded Williams Treaty boundary from: {path}")
            return True

    print("ERROR: Williams Treaty boundary file not found!")
    print("Please ensure one of these files exists:")
    for path in boundary_paths:
        print(f"  - {path}")
    return False

# Output directory for Williams Treaty datasets
OUTPUT_DIR = Path("data/datasets/williams_treaty")

# Mapping of Williams Treaty datasets to their parent Ontario datasets
# Format: (wt_dataset_id, parent_path, output_filename)
DATASETS_TO_CLIP = [
    # Protected Areas
    (
        "williams_treaty_provincial_parks",
        "data/processed/provincial_parks.geojson",
        "provincial_parks.geojson",
    ),
    (
        "williams_treaty_conservation_authorities",
        "data/processed/conservation_authorities.geojson",
        "conservation_authorities.geojson",
    ),
    # Hydrology
    (
        "williams_treaty_wetlands",
        "data/datasets/environmental/wetlands.geojson",
        "wetlands.geojson",
    ),
    (
        "williams_treaty_waterbodies",
        "data/datasets/environmental/waterbodies.geojson",
        "waterbodies.geojson",
    ),
    (
        "williams_treaty_watercourses",
        "data/datasets/environmental/watercourses.geojson",
        "watercourses.geojson",
    ),
    (
        "williams_treaty_dams",
        "data/datasets/environmental/dams.geojson",
        "dams.geojson",
    ),
    # Infrastructure
    (
        "williams_treaty_trails",
        "data/datasets/infrastructure/trails.geojson",
        "trails.geojson",
    ),
    (
        "williams_treaty_trail_access_points",
        "data/datasets/infrastructure/trail_access_points.geojson",
        "trail_access_points.geojson",
    ),
    # Environmental
    (
        "williams_treaty_ecodistricts",
        "data/datasets/environmental/ecodistricts.geojson",
        "ecodistricts.geojson",
    ),
    (
        "williams_treaty_fire_perimeters",
        "data/processed/fire_perimeters_1976_2024.geojson",
        "fire_perimeters.geojson",
    ),
    # Boundaries
    (
        "williams_treaty_municipalities",
        "data/processed/boundaries/ontario_municipalities.geojson",
        "municipalities.geojson",
    ),
    # Biodiversity
    (
        "williams_treaty_inaturalist",
        "data/processed/inaturalist_observations_2024.json",
        "inaturalist.geojson",
    ),
    # Community
    (
        "williams_treaty_community_wellbeing",
        "data/processed/cwb/community_wellbeing_ontario.geojson",
        "community_wellbeing.geojson",
    ),
    (
        "williams_treaty_water_advisories",
        "data/datasets/community/water_advisories.geojson",
        "water_advisories.geojson",
    ),
    (
        "williams_treaty_infrastructure_projects",
        "data/datasets/community/infrastructure_projects.geojson",
        "infrastructure_projects.geojson",
    ),
]


def load_geojson_or_json(file_path: Path) -> Optional[gpd.GeoDataFrame]:
    """Load a GeoJSON or JSON file as a GeoDataFrame."""
    if not file_path.exists():
        return None

    try:
        if file_path.suffix == ".json":
            # It might be a regular JSON file (like iNaturalist observations)
            with open(file_path) as f:
                data = json.load(f)

            # Check if it's a list of observations with lat/lng
            if isinstance(data, list) and len(data) > 0:
                # Convert to GeoDataFrame
                features = []
                for item in data:
                    lat = item.get("latitude")
                    lng = item.get("longitude")
                    if lat and lng:
                        features.append(
                            {
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                                "properties": item,
                            }
                        )

                if features:
                    geojson = {"type": "FeatureCollection", "features": features}
                    return gpd.GeoDataFrame.from_features(geojson, crs="EPSG:4326")
            return None

        # Standard GeoJSON
        return gpd.read_file(file_path)
    except Exception as e:
        print(f"  Error loading {file_path}: {e}")
        return None


def clip_to_williams_treaty(
    gdf: gpd.GeoDataFrame, geometry_type: str = "auto"
) -> gpd.GeoDataFrame:
    """
    Clip or filter a GeoDataFrame to Williams Treaty territory boundary.

    For polygons: clips geometries to the actual treaty boundary
    For points/lines: filters to features that intersect the boundary
    """
    if gdf.empty:
        return gdf

    if WILLIAMS_TREATY_BOUNDARY is None:
        raise ValueError("Williams Treaty boundary not loaded. Call load_williams_treaty_boundary() first.")

    # Remove rows with null geometries
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        return gdf

    # Ensure CRS is WGS84
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    # Determine geometry type from first valid geometry
    if geometry_type == "auto":
        valid_geoms = gdf[gdf.geometry.is_valid]
        if valid_geoms.empty:
            # Fall back to first geometry
            sample_geom = gdf.geometry.iloc[0]
        else:
            sample_geom = valid_geoms.geometry.iloc[0]
        geom_type = sample_geom.geom_type if sample_geom else "Polygon"
    else:
        geom_type = geometry_type

    # Create boundary GeoDataFrame for spatial operations
    boundary_gdf = gpd.GeoDataFrame(
        {"geometry": [WILLIAMS_TREATY_BOUNDARY]}, crs="EPSG:4326"
    )

    if geom_type in ["Polygon", "MultiPolygon"]:
        # For polygons, use clip (intersection with actual boundary)
        try:
            clipped = gpd.clip(gdf, boundary_gdf)
            return clipped
        except Exception:
            # Fall back to intersection filter
            return gdf[gdf.intersects(WILLIAMS_TREATY_BOUNDARY)]
    else:
        # For points and lines, filter to those that intersect
        return gdf[gdf.intersects(WILLIAMS_TREATY_BOUNDARY)]


def process_dataset(dataset_id: str, parent_path: str, output_filename: str) -> dict:
    """Process a single dataset - load parent, clip, and save."""
    parent_file = Path(parent_path)
    output_file = OUTPUT_DIR / output_filename

    result = {
        "dataset_id": dataset_id,
        "parent_path": str(parent_path),
        "output_path": str(output_file),
        "status": "pending",
        "count": 0,
        "parent_count": 0,
    }

    # Check if parent exists
    if not parent_file.exists():
        result["status"] = "skipped"
        result["note"] = f"Parent file not found: {parent_path}"
        return result

    # Load parent dataset
    print(f"\n  Loading: {parent_path}")
    gdf = load_geojson_or_json(parent_file)

    if gdf is None or gdf.empty:
        result["status"] = "skipped"
        result["note"] = "Failed to load parent or empty dataset"
        return result

    result["parent_count"] = len(gdf)
    print(f"  Loaded {len(gdf)} features from parent")

    # Clip to Williams Treaty bounds
    print("  Clipping to Williams Treaty territory...")
    clipped_gdf = clip_to_williams_treaty(gdf)

    if clipped_gdf.empty:
        result["status"] = "empty"
        result["note"] = "No features within Williams Treaty bounds"
        return result

    result["count"] = len(clipped_gdf)
    print(f"  Clipped to {len(clipped_gdf)} features")

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    clipped_gdf.to_file(output_file, driver="GeoJSON")
    print(f"  Saved: {output_file}")

    result["status"] = "success"
    return result


def main():
    """Main function to clip all datasets."""
    print("=" * 80)
    print("WILLIAMS TREATY TERRITORY DATA CLIPPING")
    print("=" * 80)

    # Load the actual Williams Treaty boundary
    if not load_williams_treaty_boundary():
        print("\nFailed to load boundary. Exiting.")
        return

    print(f"Output directory: {OUTPUT_DIR}")
    print(f"\nDatasets to process: {len(DATASETS_TO_CLIP)}")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {"success": [], "skipped": [], "empty": [], "error": []}

    for dataset_id, parent_path, output_filename in DATASETS_TO_CLIP:
        print(f"\n{'─' * 60}")
        print(f"Processing: {dataset_id}")

        try:
            result = process_dataset(dataset_id, parent_path, output_filename)

            if result["status"] == "success":
                results["success"].append(result)
                print(
                    f"  ✅ Success: {result['count']}/{result['parent_count']} features"
                )
            elif result["status"] == "skipped":
                results["skipped"].append(result)
                print(f"  ⚠️  Skipped: {result.get('note', 'Unknown reason')}")
            elif result["status"] == "empty":
                results["empty"].append(result)
                print(f"  ℹ️  Empty result: {result.get('note', 'No features')}")
            else:
                results["error"].append(result)
                print(f"  ❌ Error: {result.get('note', 'Unknown error')}")

        except Exception as e:
            results["error"].append(
                {
                    "dataset_id": dataset_id,
                    "status": "error",
                    "note": str(e),
                }
            )
            print(f"  ❌ Error: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\n✅ Successfully clipped: {len(results['success'])} datasets")
    for r in results["success"]:
        print(f"   - {r['dataset_id']}: {r['count']} features")

    if results["skipped"]:
        print(f"\n⚠️  Skipped (parent not found): {len(results['skipped'])} datasets")
        for r in results["skipped"]:
            print(f"   - {r['dataset_id']}: {r.get('note', '')}")

    if results["empty"]:
        print(f"\nℹ️  Empty (no features in bounds): {len(results['empty'])} datasets")
        for r in results["empty"]:
            print(f"   - {r['dataset_id']}")

    if results["error"]:
        print(f"\n❌ Errors: {len(results['error'])} datasets")
        for r in results["error"]:
            print(f"   - {r['dataset_id']}: {r.get('note', '')}")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\nTo process skipped datasets, ensure parent data files exist:")
    for r in results["skipped"]:
        print(f"  - {r['parent_path']}")

    print(f"\nOutput files are in: {OUTPUT_DIR}/")
    print("=" * 80)


if __name__ == "__main__":
    main()
