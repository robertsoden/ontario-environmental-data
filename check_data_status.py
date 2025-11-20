#!/usr/bin/env python3
"""
Check status of data files in the repository.
Shows which data sources are available and which need to be collected.

This script validates data files to ensure they:
1. Exist and are not empty
2. Contain valid data (proper format, minimum records)
3. Have expected fields and structure

Exit codes:
  0 - All expected data files are present and valid
  1 - One or more data files are missing or invalid
  2 - Data files exist but have validation warnings
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from ontario_data import validate_data_file

DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"

# Define expected data files with validation requirements
DATA_FILES = {
    "williams_treaty_communities": {
        "path": OUTPUT_DIR / "communities" / "williams_treaty_communities.geojson",
        "description": "Williams Treaty First Nations community points",
        "type": "boundaries",
        "data_type": "geojson",
        "min_records": 7,  # 7 Williams Treaty First Nations
        "required_fields": ["first_nation", "reserve_name"],
        "critical": True,  # Critical data source
    },
    "williams_treaty_boundaries": {
        "path": OUTPUT_DIR / "boundaries" / "williams_treaty.geojson",
        "description": "Williams Treaty territory boundary polygon",
        "type": "boundaries",
        "data_type": "geojson",
        "min_records": 1,
        "required_fields": ["first_nation"],
        "critical": False,  # Nice to have but may not be available
    },
    "fire_perimeters": {
        "path": OUTPUT_DIR / "fire_perimeters_1976_2024.geojson",
        "description": "Historical fire perimeters (1976-2024)",
        "type": "environmental",
        "data_type": "geojson",
        "min_records": 1,
        "required_fields": ["year"],
        "critical": False,
    },
    "provincial_parks": {
        "path": OUTPUT_DIR / "provincial_parks.geojson",
        "description": "Ontario provincial parks boundaries",
        "type": "protected_areas",
        "data_type": "geojson",
        "min_records": 1,
        "required_fields": ["name"],
        "critical": True,  # Critical data source
    },
    "conservation_authorities": {
        "path": OUTPUT_DIR / "conservation_authorities.geojson",
        "description": "Conservation authority boundaries",
        "type": "protected_areas",
        "data_type": "geojson",
        "min_records": 1,
        "required_fields": ["name"],
        "critical": False,
    },
    "inaturalist": {
        "path": OUTPUT_DIR / "inaturalist_observations_2024.json",
        "description": "iNaturalist biodiversity observations",
        "type": "biodiversity",
        "data_type": "json",
        "min_records": 1,
        "required_fields": None,
        "critical": False,
    },
    "satellite": {
        "path": OUTPUT_DIR / "satellite_data_info.json",
        "description": "Satellite data information (NDVI, land cover)",
        "type": "environmental",
        "data_type": "json",
        "min_records": 1,
        "required_fields": None,
        "critical": False,
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
    """Check status of all data files with validation."""
    status = {
        "timestamp": datetime.now().isoformat(),
        "available": [],
        "missing": [],
        "validation_errors": [],
        "validation_warnings": [],
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
            is_critical = info.get("critical", False)
            critical_marker = " [CRITICAL]" if is_critical else ""

            if path.exists():
                size = path.stat().st_size
                modified = datetime.fromtimestamp(path.stat().st_mtime)

                # Perform validation
                validation_success, validation_errors, validation_warnings = (
                    validate_data_file(
                        path,
                        info["data_type"],
                        info.get("min_records", 1),
                        info.get("required_fields"),
                    )
                )

                file_info = {
                    "name": name,
                    "path": str(path),
                    "size": size,
                    "size_human": format_size(size),
                    "modified": modified.isoformat(),
                    "validated": True,
                    "validation_success": validation_success,
                    "validation_errors": validation_errors,
                    "validation_warnings": validation_warnings,
                    "critical": is_critical,
                }

                status["available"].append(file_info)

                # Print status with validation results
                if validation_success and not validation_warnings:
                    print(
                        f"  ✅ {name:30} {format_size(size):>10}  (valid){critical_marker}"
                    )
                elif validation_success and validation_warnings:
                    print(
                        f"  ⚠️  {name:30} {format_size(size):>10}  (warnings){critical_marker}"
                    )
                    for warning in validation_warnings[:2]:  # Show first 2 warnings
                        print(f"      └─ {warning}")
                    status["validation_warnings"].extend(
                        [f"{name}: {w}" for w in validation_warnings]
                    )
                else:
                    print(
                        f"  ❌ {name:30} {format_size(size):>10}  (INVALID){critical_marker}"
                    )
                    for error in validation_errors[:2]:  # Show first 2 errors
                        print(f"      └─ {error}")
                    status["validation_errors"].extend(
                        [f"{name}: {e}" for e in validation_errors]
                    )
            else:
                status["missing"].append(
                    {
                        "name": name,
                        "path": str(path),
                        "description": info["description"],
                        "critical": is_critical,
                    }
                )
                print(f"  ✗ {name:30} {'MISSING':>10}{critical_marker}")

                if is_critical:
                    status["validation_errors"].append(
                        f"{name}: MISSING (critical data source)"
                    )

    print("\n" + "=" * 80)
    print(
        f"SUMMARY: {len(status['available'])} available, {len(status['missing'])} missing"
    )
    print(
        f"Validation: {len(status['validation_errors'])} errors, {len(status['validation_warnings'])} warnings"
    )
    print("=" * 80)

    # Detailed validation summary
    if status["validation_errors"]:
        print("\n❌ VALIDATION ERRORS:")
        for error in status["validation_errors"]:
            print(f"   • {error}")

    if status["validation_warnings"]:
        print("\n⚠️  VALIDATION WARNINGS:")
        for warning in status["validation_warnings"][:10]:  # Show first 10
            print(f"   • {warning}")
        if len(status["validation_warnings"]) > 10:
            print(f"   ... and {len(status['validation_warnings']) - 10} more")

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


def check_satellite_data_status():
    """Check status of satellite data processing."""
    registry_file = Path("satellite_data_registry.json")

    if not registry_file.exists():
        return {"status": "registry_not_found", "datasets": {}}

    with open(registry_file) as f:
        registry = json.load(f)

    satellite_status = {"datasets": {}}

    print("\n" + "=" * 80)
    print("SATELLITE DATA STATUS")
    print("=" * 80)
    print()

    for dataset_name, dataset_info in registry.get("datasets", {}).items():
        print(f"\n{dataset_name.upper()}:")
        print("-" * 40)

        versions = dataset_info.get("versions", {})

        if not versions:
            print("  ✗ No processed versions available")
            satellite_status["datasets"][dataset_name] = {
                "status": "not_processed",
                "versions": [],
            }
            continue

        # Show available versions
        for year, version_info in sorted(versions.items(), reverse=True):
            status_icon = "✓" if version_info.get("status") == "success" else "✗"
            processed_date = version_info.get("processed_date", "unknown")
            if processed_date != "unknown":
                processed_date = datetime.fromisoformat(processed_date).strftime(
                    "%Y-%m-%d"
                )

            print(f"  {status_icon} {year:8} (processed: {processed_date})")

            # Check if tile file exists
            tile_file = version_info.get("files", {}).get("tiles")
            if tile_file and Path(tile_file).exists():
                size_mb = Path(tile_file).stat().st_size / (1024 * 1024)
                print(f"      Tiles: {size_mb:.1f} MB")

        satellite_status["datasets"][dataset_name] = {
            "status": "processed",
            "versions": list(versions.keys()),
            "latest": max(versions.keys()) if versions else None,
        }

    print("\n" + "=" * 80)
    print(
        f"SATELLITE SUMMARY: {len([d for d in satellite_status['datasets'].values() if d['status'] == 'processed'])} datasets processed"
    )
    print("=" * 80)

    return satellite_status


if __name__ == "__main__":
    # Check vector/tabular data
    status = check_data_status()

    # Check satellite data
    satellite_status = check_satellite_data_status()

    # Combine results
    combined_status = {
        "timestamp": status["timestamp"],
        "vector_data": {
            "available": status["available"],
            "missing": status["missing"],
            "validation_errors": status["validation_errors"],
            "validation_warnings": status["validation_warnings"],
            "summary": status["summary"],
        },
        "satellite_data": satellite_status,
    }

    # Save status to JSON for CI/CD
    status_file = Path("data_status.json")
    with open(status_file, "w") as f:
        json.dump(combined_status, f, indent=2)

    print(f"\nStatus saved to: {status_file}")

    # Determine exit code
    # Critical errors: missing critical files or validation errors in critical files
    has_critical_errors = any(
        item["critical"]
        and (
            not item.get("validation_success", False)
            or item.get("name")
            in [e.split(":")[0] for e in status["validation_errors"]]
        )
        for item in status["available"]
    ) or any(item["critical"] for item in status["missing"])

    # Any validation errors (including missing critical files)
    has_any_errors = len(status["validation_errors"]) > 0 or len(status["missing"]) > 0

    # Determine exit code
    if has_critical_errors:
        print("\n" + "=" * 80)
        print("❌ CRITICAL DATA MISSING OR INVALID")
        print("=" * 80)
        print("\nOne or more critical data files are missing or invalid.")
        print("The data repository cannot be considered complete.")
        sys.exit(1)
    elif has_any_errors:
        print("\n" + "=" * 80)
        print("⚠️  SOME DATA MISSING OR INVALID")
        print("=" * 80)
        print("\nSome non-critical data files are missing or invalid.")
        print("Critical data is present, but you may want to fix these issues.")
        sys.exit(2)
    elif len(status["validation_warnings"]) > 0:
        print("\n" + "=" * 80)
        print("✅ DATA VALID (WITH WARNINGS)")
        print("=" * 80)
        print("\nAll data files are present and valid.")
        print("However, there are some warnings to review.")
        sys.exit(0)  # Still success, just warnings
    else:
        print("\n" + "=" * 80)
        print("✅ ALL DATA VALID")
        print("=" * 80)
        print("\nAll data files are present and validated successfully!")
        sys.exit(0)
