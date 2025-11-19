#!/usr/bin/env python3
"""
Check status of data files in the repository.
Shows which data sources are available and which need to be collected.
"""

import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"

# Define expected data files
DATA_FILES = {
    "williams_treaty_communities": {
        "path": OUTPUT_DIR / "communities" / "williams_treaty_communities.geojson",
        "description": "Williams Treaty First Nations community points",
        "type": "boundaries",
    },
    "williams_treaty_boundaries": {
        "path": OUTPUT_DIR / "boundaries" / "williams_treaty.geojson",
        "description": "Williams Treaty territory boundary polygon",
        "type": "boundaries",
    },
    "fire_perimeters": {
        "path": OUTPUT_DIR / "fire_perimeters_1976_2024.geojson",
        "description": "Historical fire perimeters (1976-2024)",
        "type": "environmental",
    },
    "provincial_parks": {
        "path": OUTPUT_DIR / "provincial_parks.geojson",
        "description": "Ontario provincial parks boundaries",
        "type": "protected_areas",
    },
    "conservation_authorities": {
        "path": OUTPUT_DIR / "conservation_authorities.geojson",
        "description": "Conservation authority boundaries",
        "type": "protected_areas",
    },
    "inaturalist": {
        "path": OUTPUT_DIR / "inaturalist_observations_2024.json",
        "description": "iNaturalist biodiversity observations",
        "type": "biodiversity",
    },
    "satellite": {
        "path": OUTPUT_DIR / "satellite_data_info.json",
        "description": "Satellite data information (NDVI, land cover)",
        "type": "environmental",
    },
}


def format_size(size_bytes):
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def check_data_status():
    """Check status of all data files."""
    status = {
        "timestamp": datetime.now().isoformat(),
        "available": [],
        "missing": [],
        "summary": {},
    }

    print("=" * 80)
    print("ONTARIO ENVIRONMENTAL DATA - STATUS CHECK")
    print("=" * 80)
    print()

    for data_type in ["boundaries", "protected_areas", "biodiversity", "environmental"]:
        print(f"\n{data_type.upper().replace('_', ' ')}:")
        print("-" * 40)

        for name, info in DATA_FILES.items():
            if info["type"] != data_type:
                continue

            path = info["path"]
            if path.exists():
                size = path.stat().st_size
                modified = datetime.fromtimestamp(path.stat().st_mtime)
                status["available"].append(
                    {
                        "name": name,
                        "path": str(path),
                        "size": size,
                        "size_human": format_size(size),
                        "modified": modified.isoformat(),
                    }
                )
                print(
                    f"  ✓ {name:30} {format_size(size):>10}  (modified: {modified.strftime('%Y-%m-%d %H:%M')})"
                )
            else:
                status["missing"].append(
                    {
                        "name": name,
                        "path": str(path),
                        "description": info["description"],
                    }
                )
                print(f"  ✗ {name:30} {'MISSING':>10}")

    print("\n" + "=" * 80)
    print(
        f"SUMMARY: {len(status['available'])} available, {len(status['missing'])} missing"
    )
    print("=" * 80)

    # Group by type
    for data_type in ["boundaries", "protected_areas", "biodiversity", "environmental"]:
        type_files = [f for f in DATA_FILES.values() if f["type"] == data_type]
        available_count = sum(
            1
            for item in status["available"]
            if any(f["path"] == Path(item["path"]) for f in type_files)
        )
        total_count = len(type_files)
        status["summary"][data_type] = {
            "available": available_count,
            "total": total_count,
        }

    return status


if __name__ == "__main__":
    status = check_data_status()

    # Save status to JSON for CI/CD
    status_file = Path("data_status.json")
    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)

    print(f"\nStatus saved to: {status_file}")
