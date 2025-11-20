#!/usr/bin/env python3
"""
Check status of data files in the repository.
Shows which data sources are available and which need to be collected.

This script validates data files to ensure they:
1. Exist and are not empty
2. Contain valid data (proper format, minimum records)
3. Have expected fields and structure

Exit codes:
  0 - Always exits with 0 (status check is informational only)

Note: Missing or invalid data will be reported but won't cause a failure.
This allows the script to be used both before and after data collection.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from ontario_data import validate_data_file
from ontario_data.datasets import DATASETS, get_all_categories

DATA_DIR = Path("data")
OUTPUT_DIR = DATA_DIR / "processed"


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

    # Get all categories from registry
    categories = get_all_categories()

    for category in categories:
        print(f"\n{category.upper().replace('_', ' ')}:")
        print("-" * 40)

        # Get datasets in this category from registry
        category_datasets = [
            (name, ds) for name, ds in DATASETS.items() if ds.category == category
        ]

        for name, dataset in category_datasets:
            path = dataset.output_path

            if path and path.exists():
                size = path.stat().st_size
                modified = datetime.fromtimestamp(path.stat().st_mtime)

                # Perform validation
                validation_success, validation_errors, validation_warnings = (
                    validate_data_file(
                        path,
                        dataset.output_format,
                        dataset.min_records,
                        dataset.required_fields,
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
                }

                status["available"].append(file_info)

                # Print status with validation results
                if validation_success and not validation_warnings:
                    print(f"  ✅ {name:30} {format_size(size):>10}  (valid)")
                elif validation_success and validation_warnings:
                    print(f"  ⚠️  {name:30} {format_size(size):>10}  (warnings)")
                    for warning in validation_warnings[:2]:  # Show first 2 warnings
                        print(f"      └─ {warning}")
                    status["validation_warnings"].extend(
                        [f"{name}: {w}" for w in validation_warnings]
                    )
                else:
                    print(f"  ❌ {name:30} {format_size(size):>10}  (INVALID)")
                    for error in validation_errors[:2]:  # Show first 2 errors
                        print(f"      └─ {error}")
                    status["validation_errors"].extend(
                        [f"{name}: {e}" for e in validation_errors]
                    )
            else:
                status["missing"].append(
                    {
                        "name": name,
                        "path": str(path) if path else "unknown",
                        "description": dataset.description,
                    }
                )
                print(f"  ✗ {name:30} {'MISSING':>10}")

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
    for category in categories:
        category_count = len(
            [ds for ds in DATASETS.values() if ds.category == category]
        )
        available_count = sum(
            1
            for item in status["available"]
            if any(
                ds.output_path == Path(item["path"])
                for ds in DATASETS.values()
                if ds.category == category
            )
        )
        status["summary"][category] = {
            "available": available_count,
            "total": category_count,
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

    # Note: Satellite data has its own separate workflow and status check
    # Run check_satellite_status.py to check satellite data

    # Save results
    combined_status = {
        "timestamp": status["timestamp"],
        "available": status["available"],
        "missing": status["missing"],
        "validation_errors": status["validation_errors"],
        "validation_warnings": status["validation_warnings"],
        "summary": status["summary"],
    }

    # Save status to JSON for CI/CD
    status_file = Path("data_status.json")
    with open(status_file, "w") as f:
        json.dump(combined_status, f, indent=2)

    print(f"\nStatus saved to: {status_file}")

    # Report data status (always exit 0 - this is informational only)
    has_any_errors = len(status["validation_errors"]) > 0 or len(status["missing"]) > 0

    print("\n" + "=" * 80)
    if not has_any_errors and len(status["validation_warnings"]) == 0:
        print("✅ ALL DATA VALID")
        print("=" * 80)
        print("\nAll data files are present and validated successfully!")
    elif not has_any_errors and len(status["validation_warnings"]) > 0:
        print("✅ DATA VALID (WITH WARNINGS)")
        print("=" * 80)
        print("\nAll data files are present and valid.")
        print("However, there are some warnings to review.")
    elif len(status["available"]) > 0:
        print("⚠️  SOME DATA MISSING OR INVALID")
        print("=" * 80)
        total_datasets = len(DATASETS)
        print(f"\n{len(status['available'])}/{total_datasets} data files are present.")
        if len(status["missing"]) > 0:
            print(f"{len(status['missing'])} files are missing.")
        if len(status["validation_errors"]) > 0:
            print(f"{len(status['validation_errors'])} validation errors found.")
    else:
        print("⚠️  NO DATA AVAILABLE")
        print("=" * 80)
        print("\nNo data files are present yet.")
        print("Run data collection to populate the data directory.")

    # Always exit 0 - status check is informational only
    sys.exit(0)
