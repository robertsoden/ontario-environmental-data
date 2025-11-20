#!/usr/bin/env python3
"""
Data Collection Script (Registry-Based)

This script collects data sources using the centralized dataset registry.
Dataset selection is controlled via environment variables.

Environment Variables:
  COLLECT_<DATASET_ID>=true - Collect that specific dataset

Examples:
  COLLECT_INATURALIST=true
  COLLECT_EBIRD=true
  COLLECT_COMMUNITY_WELLBEING=true

All dataset definitions (metadata, collection functions, validation rules)
are in ontario_data/datasets.py - the single source of truth.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from ontario_data.datasets import DATASETS, get_enabled_datasets

# Configuration
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_selected_datasets():
    """Get list of selected datasets from environment variables.

    Returns list of dataset IDs to collect based on COLLECT_<ID>=true env vars.
    """
    selected = []

    for dataset_id, dataset in DATASETS.items():
        # Skip disabled datasets
        if not dataset.enabled:
            continue

        # Check environment variable COLLECT_<DATASET_ID>
        env_var = f"COLLECT_{dataset_id.upper()}"
        if os.getenv(env_var, "").lower() == "true":
            selected.append(dataset_id)

    return selected


async def collect_selected_data():
    """Collect only selected data sources."""

    selected_ids = get_selected_datasets()

    # Check for --overwrite flag
    overwrite = os.getenv("OVERWRITE", "false").lower() == "true"

    if not selected_ids:
        print("⚠️  No datasets selected")
        print("Set COLLECT_<DATASET_ID>=true environment variables to select datasets")
        print("\nAvailable datasets:")
        for dataset_id, dataset in DATASETS.items():
            status = "enabled" if dataset.enabled else "disabled"
            has_fn = "✓" if dataset.collect_fn else "✗"
            print(f"  {has_fn} {dataset_id:30} ({status})")
        return

    print("\nStarting selective data collection...")
    print("\n" + "=" * 80)
    print("DATA COLLECTION")
    print("=" * 80)

    if overwrite:
        print(f"\n📦 Collecting {len(selected_ids)}/{len(get_enabled_datasets())} selected data sources (overwrite mode)\n")
    else:
        print(f"\n📦 Collecting {len(selected_ids)}/{len(get_enabled_datasets())} selected data sources (skip existing)\n")

    # Show checklist
    for dataset_id, dataset in DATASETS.items():
        if not dataset.enabled:
            continue
        icon = "✅" if dataset_id in selected_ids else "⬜"
        name = dataset.name
        exists = "📁" if dataset.output_path and dataset.output_path.exists() else ""
        print(f"  {icon} {name} {exists}")

    print()

    # Collect each selected dataset
    results = {
        "timestamp": datetime.now().isoformat(),
        "selected": selected_ids,
        "sources": {},
    }

    for dataset_id in selected_ids:
        dataset = DATASETS.get(dataset_id)
        if not dataset:
            print(f"⚠️  Unknown dataset: {dataset_id}")
            continue

        # Check if this is a static dataset with an existing file
        # Static datasets should not be re-collected even if they have a collect_fn
        if dataset.is_static and dataset.output_path and dataset.output_path.exists():
            file_size = dataset.output_path.stat().st_size / (1024 * 1024)  # MB

            # Try to get feature count from GeoJSON
            count = 0
            if dataset.output_path.suffix == ".geojson":
                try:
                    with open(dataset.output_path) as f:
                        data = json.load(f)
                        count = len(data.get("features", []))
                except Exception:
                    pass

            print(f"\n📦 {dataset.name}: Static dataset ({file_size:.1f} MB, {count} features)")
            print(f"   File: {dataset.output_path}")
            results["sources"][dataset_id] = {
                "status": "static",
                "note": "Static pre-processed dataset",
                "file": str(dataset.output_path),
                "count": count
            }
            continue

        # Check if collection function exists
        if not dataset.collect_fn:
            # Check if this is a static file that already exists
            if dataset.output_path and dataset.output_path.exists():
                print(f"\n📄 {dataset.name}: Static file (no collection needed)")
                results["sources"][dataset_id] = {
                    "status": "static",
                    "note": "Static file - no collection required",
                    "file": str(dataset.output_path)
                }
            else:
                print(f"\n⚠️  {dataset.name}: No collection function implemented")
                results["sources"][dataset_id] = {
                    "status": "not_implemented",
                    "note": "Collection function not yet implemented"
                }
            continue

        # Check if file already exists and we're not in overwrite mode
        if not overwrite and dataset.output_path and dataset.output_path.exists():
            file_size = dataset.output_path.stat().st_size / (1024 * 1024)  # MB

            # Try to get feature count from GeoJSON
            count = 0
            if dataset.output_path.suffix == ".geojson":
                try:
                    with open(dataset.output_path) as f:
                        data = json.load(f)
                        count = len(data.get("features", []))
                except Exception:
                    pass

            print(f"\n⏭️  {dataset.name}: Skipping (already exists, {file_size:.1f} MB, {count} features)")
            print(f"   File: {dataset.output_path}")
            print(f"   Use OVERWRITE=true to re-collect")
            results["sources"][dataset_id] = {
                "status": "skipped",
                "note": "File already exists",
                "file": str(dataset.output_path),
                "count": count
            }
            continue

        # Display section header
        print("\n" + "=" * 80)
        print(dataset.name.upper())
        print("=" * 80)

        # Collect the data
        try:
            result = await dataset.collect_fn()
            results["sources"][dataset_id] = result
        except Exception as e:
            print(f"❌ Error: {e}")
            results["sources"][dataset_id] = {
                "status": "error",
                "error": str(e)
            }

    # Summary
    print("\n" + "=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)

    success_count = sum(1 for r in results["sources"].values() if r.get("status") == "success")
    skipped_count = sum(1 for r in results["sources"].values() if r.get("status") == "skipped")
    failed_count = sum(1 for r in results["sources"].values() if r.get("status") == "error")

    print(f"\n✅ Collected: {success_count}")
    if skipped_count > 0:
        print(f"⏭️  Skipped: {skipped_count} (already exist)")
    if failed_count > 0:
        print(f"❌ Failed: {failed_count}")

    # Save collection report
    report_file = OUTPUT_DIR / "collection_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n📄 Collection report: {report_file}")


if __name__ == "__main__":
    try:
        asyncio.run(collect_selected_data())
    except KeyboardInterrupt:
        print("\n\n⚠️  Collection interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Collection failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
