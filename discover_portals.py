#!/usr/bin/env python3
"""Discover datasets from Ontario open data portals.

This script harvests metadata from all configured Ontario open data portals
and creates a registry of available environmental datasets.
"""

import asyncio
from pathlib import Path

from ontario_data.sources.portal_harvester import (
    ArcGISPortalHarvester,
    CKANPortalHarvester,
    harvest_all_portals,
)

# Portal configurations
PORTALS = [
    # Ontario GeoHub (ArcGIS)
    ArcGISPortalHarvester(
        portal_name="Ontario GeoHub",
        base_url="https://geohub.lio.gov.on.ca",
    ),
    # Toronto Open Data (CKAN)
    CKANPortalHarvester(
        portal_name="Toronto Open Data",
        base_url="https://ckan0.cf.opendata.inter.prod-toronto.ca",
    ),
    # Ontario Data Catalogue (CKAN)
    CKANPortalHarvester(
        portal_name="Ontario Data Catalogue",
        base_url="https://data.ontario.ca",
    ),
]


async def main():
    """Main discovery function."""
    print("=" * 70)
    print("🌐 Ontario Environmental Data - Portal Discovery")
    print("=" * 70)
    print()
    print(f"Discovering datasets from {len(PORTALS)} portals:")
    for portal in PORTALS:
        print(f"  • {portal.portal_name}")
    print()

    # Output file
    output_file = Path("data/portal_discovery.json")

    # Harvest all portals
    results = await harvest_all_portals(PORTALS, output_file)

    # Summary
    print()
    print("=" * 70)
    print("📊 Discovery Summary")
    print("=" * 70)
    print()

    total = 0
    for portal_name, datasets in results.items():
        count = len(datasets)
        total += count
        print(f"{portal_name:30s} {count:>6,} datasets")

    print()
    print(f"{'TOTAL':30s} {total:>6,} datasets")
    print()
    print("✅ Discovery complete!")
    print(f"   Results saved to: {output_file}")
    print()
    print("Next steps:")
    print("  1. Review discovered datasets in data/portal_discovery.json")
    print("  2. Select datasets to ingest")
    print("  3. Run collection workflow to download and process")


if __name__ == "__main__":
    asyncio.run(main())
