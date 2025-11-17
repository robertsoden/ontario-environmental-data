#!/usr/bin/env python3
"""Example: Fetch biodiversity observations for an Ontario location.

This example demonstrates how to:
1. Use the iNaturalist client to fetch observations
2. Filter by quality grade
3. Display results
4. Export to GeoJSON
"""

import asyncio
import json
import os
from ontario_data.sources import INaturalistClient
from ontario_data.models import BiodiversityObservation


async def main():
    """Fetch and display biodiversity observations."""

    # Initialize client
    client = INaturalistClient()

    # Peterborough area bounding box
    # (swlat, swlng, nelat, nelng)
    peterborough_bounds = (44.0, -79.5, 45.0, -78.5)

    print("Fetching iNaturalist observations for Peterborough area...")
    print(f"Bounds: {peterborough_bounds}")
    print()

    # Fetch observations from last 30 days
    observations = await client.fetch(
        bounds=peterborough_bounds,
        quality_grade="research",  # Only research-grade observations
        max_results=50,
    )

    print(f"Found {len(observations)} observations")
    print()

    # Display summary
    if observations:
        print("Sample observations:")
        print("-" * 80)

        for i, obs in enumerate(observations[:10], 1):
            print(f"{i}. {obs['common_name'] or obs['scientific_name']}")
            print(f"   Scientific: {obs['scientific_name']}")
            print(f"   Location: {obs['place_name']}")
            print(f"   Date: {obs['observation_date']}")
            print(f"   Observer: {obs['observer']}")
            print(f"   Quality: {obs['quality_grade']}")
            print(f"   URL: {obs['url']}")
            print()

        # Count unique species
        unique_species = len(set(obs["scientific_name"] for obs in observations))
        print(f"Unique species: {unique_species}")
        print()

        # Export to GeoJSON
        geojson = {
            "type": "FeatureCollection",
            "features": []
        }

        for obs in observations:
            # Validate with Pydantic model
            try:
                model = BiodiversityObservation(**obs)
                geojson["features"].append(model.to_geojson_feature())
            except Exception as e:
                print(f"Warning: Could not validate observation {obs.get('observation_id')}: {e}")

        # Save to file
        output_file = "peterborough_biodiversity.geojson"
        with open(output_file, "w") as f:
            json.dump(geojson, f, indent=2)

        print(f"Saved {len(geojson['features'])} observations to {output_file}")

    else:
        print("No observations found for this area and time period.")


if __name__ == "__main__":
    asyncio.run(main())
