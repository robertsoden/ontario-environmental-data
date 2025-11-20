"""Portal harvester for aggregating datasets from Ontario open data portals.

This module provides harvesters for discovering and ingesting datasets from
multiple open data portals across Ontario.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp


@dataclass
class PortalDataset:
    """Metadata for a dataset discovered in a portal."""

    id: str
    title: str
    description: str
    portal: str
    portal_url: str
    download_url: Optional[str]
    format: str
    size_bytes: Optional[int]
    last_modified: Optional[str]
    categories: List[str]
    keywords: List[str]
    spatial_coverage: Optional[str]
    is_geospatial: bool
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "portal": self.portal,
            "portal_url": self.portal_url,
            "download_url": self.download_url,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "last_modified": self.last_modified,
            "categories": self.categories,
            "keywords": self.keywords,
            "spatial_coverage": self.spatial_coverage,
            "is_geospatial": self.is_geospatial,
            "metadata": self.metadata,
        }


class PortalHarvester(ABC):
    """Base class for portal harvesters."""

    def __init__(self, portal_name: str, base_url: str):
        """Initialize harvester.

        Args:
            portal_name: Name of the portal
            base_url: Base URL of the portal API
        """
        self.portal_name = portal_name
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    @abstractmethod
    async def discover_datasets(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[PortalDataset]:
        """Discover all datasets in the portal.

        Args:
            filters: Optional filters to apply (e.g., categories, keywords)

        Returns:
            List of discovered datasets
        """
        pass

    @abstractmethod
    async def get_dataset_metadata(self, dataset_id: str) -> PortalDataset:
        """Get detailed metadata for a specific dataset.

        Args:
            dataset_id: Dataset identifier

        Returns:
            Dataset metadata
        """
        pass

    def filter_environmental_datasets(
        self, datasets: List[PortalDataset]
    ) -> List[PortalDataset]:
        """Filter datasets to only environmental/geospatial ones.

        Args:
            datasets: List of all datasets

        Returns:
            Filtered list of environmental datasets
        """
        environmental_keywords = {
            "environment",
            "environmental",
            "conservation",
            "biodiversity",
            "species",
            "habitat",
            "water",
            "air",
            "quality",
            "pollution",
            "climate",
            "weather",
            "forest",
            "park",
            "protected",
            "wildlife",
            "ecological",
            "ecosystem",
            "watershed",
            "river",
            "lake",
            "wetland",
            "natural",
            "nature",
            "vegetation",
            "land cover",
            "soil",
            "geology",
            "geography",
            "geographic",
            "geospatial",
            "gis",
            "spatial",
            "boundary",
            "boundaries",
            "municipal",
            "indigenous",
            "first nations",
            "treaty",
            "fire",
            "flood",
            "hazard",
        }

        filtered = []
        for dataset in datasets:
            # Check if geospatial format
            if dataset.format.lower() in [
                "geojson",
                "shapefile",
                "shp",
                "kml",
                "gml",
                "wms",
                "wfs",
            ]:
                filtered.append(dataset)
                continue

            # Check keywords
            dataset_text = " ".join(
                [
                    dataset.title.lower(),
                    dataset.description.lower(),
                    " ".join(dataset.keywords).lower(),
                    " ".join(dataset.categories).lower(),
                ]
            )

            if any(keyword in dataset_text for keyword in environmental_keywords):
                filtered.append(dataset)

        return filtered


class ArcGISPortalHarvester(PortalHarvester):
    """Harvester for ArcGIS-based portals (Ontario GeoHub, Conservation Ontario)."""

    async def discover_datasets(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[PortalDataset]:
        """Discover datasets from ArcGIS portal."""
        datasets = []
        start = 0
        num = 100  # Results per page

        while True:
            search_url = f"{self.base_url}/api/search/v1"
            params = {
                "q": filters.get("q", "*") if filters else "*",
                "start": start,
                "num": num,
                "sortField": "modified",
                "sortOrder": "desc",
            }

            async with self.session.get(search_url, params=params) as response:
                if response.status != 200:
                    break

                data = await response.json()
                results = data.get("results", [])

                if not results:
                    break

                for item in results:
                    # Determine if geospatial
                    item_type = item.get("type", "").lower()
                    is_geospatial = any(
                        t in item_type
                        for t in [
                            "feature service",
                            "map service",
                            "shapefile",
                            "geojson",
                        ]
                    )

                    # Get download URL
                    download_url = None
                    if "url" in item:
                        download_url = item["url"]

                    dataset = PortalDataset(
                        id=item.get("id", ""),
                        title=item.get("title", ""),
                        description=item.get("snippet", ""),
                        portal=self.portal_name,
                        portal_url=f"{self.base_url}/datasets/{item.get('id')}",
                        download_url=download_url,
                        format=item.get("type", "unknown"),
                        size_bytes=item.get("size"),
                        last_modified=item.get("modified"),
                        categories=item.get("categories", []),
                        keywords=item.get("tags", []),
                        spatial_coverage=item.get("extent"),
                        is_geospatial=is_geospatial,
                        metadata=item,
                    )
                    datasets.append(dataset)

                start += num

                # Check if we've got all results
                if start >= data.get("total", 0):
                    break

        return datasets

    async def get_dataset_metadata(self, dataset_id: str) -> PortalDataset:
        """Get detailed metadata for ArcGIS dataset."""
        metadata_url = f"{self.base_url}/api/v3/datasets/{dataset_id}"

        async with self.session.get(metadata_url) as response:
            response.raise_for_status()
            data = await response.json()

            return PortalDataset(
                id=data.get("id", ""),
                title=data.get("title", ""),
                description=data.get("description", ""),
                portal=self.portal_name,
                portal_url=f"{self.base_url}/datasets/{dataset_id}",
                download_url=data.get("url"),
                format=data.get("type", "unknown"),
                size_bytes=data.get("size"),
                last_modified=data.get("modified"),
                categories=data.get("categories", []),
                keywords=data.get("tags", []),
                spatial_coverage=data.get("extent"),
                is_geospatial=True,
                metadata=data,
            )


class CKANPortalHarvester(PortalHarvester):
    """Harvester for CKAN-based portals (Toronto Open Data, Ontario Data Catalogue)."""

    async def discover_datasets(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[PortalDataset]:
        """Discover datasets from CKAN portal."""
        datasets = []
        start = 0
        rows = 100  # Results per page

        while True:
            search_url = f"{self.base_url}/api/3/action/package_search"
            params = {
                "q": filters.get("q", "*") if filters else "*",
                "start": start,
                "rows": rows,
                "sort": "metadata_modified desc",
            }

            async with self.session.get(search_url, params=params) as response:
                if response.status != 200:
                    break

                data = await response.json()
                if not data.get("success"):
                    break

                results = data.get("result", {}).get("results", [])

                if not results:
                    break

                for package in results:
                    # Process each resource (file) in the package
                    for resource in package.get("resources", []):
                        # Determine if geospatial
                        fmt = resource.get("format", "").lower()
                        is_geospatial = fmt in [
                            "geojson",
                            "shp",
                            "shapefile",
                            "kml",
                            "gml",
                            "wms",
                            "wfs",
                        ]

                        dataset = PortalDataset(
                            id=f"{package.get('id')}_{resource.get('id')}",
                            title=f"{package.get('title')} - {resource.get('name', '')}",
                            description=package.get("notes", ""),
                            portal=self.portal_name,
                            portal_url=f"{self.base_url}/dataset/{package.get('name')}",
                            download_url=resource.get("url"),
                            format=resource.get("format", "unknown"),
                            size_bytes=resource.get("size"),
                            last_modified=resource.get("last_modified")
                            or package.get("metadata_modified"),
                            categories=[package.get("organization", {}).get("title", "")],
                            keywords=package.get("tags", []),
                            spatial_coverage=None,
                            is_geospatial=is_geospatial,
                            metadata={
                                "package": package,
                                "resource": resource,
                            },
                        )
                        datasets.append(dataset)

                start += rows

                # Check if we've got all results
                if start >= data.get("result", {}).get("count", 0):
                    break

        return datasets

    async def get_dataset_metadata(self, dataset_id: str) -> PortalDataset:
        """Get detailed metadata for CKAN dataset."""
        # Split composite ID
        package_id = dataset_id.split("_")[0]

        metadata_url = f"{self.base_url}/api/3/action/package_show"
        params = {"id": package_id}

        async with self.session.get(metadata_url, params=params) as response:
            response.raise_for_status()
            data = await response.json()
            package = data.get("result", {})

            # Find the specific resource
            resource = next(
                (r for r in package.get("resources", []) if dataset_id.endswith(r["id"])),
                package.get("resources", [{}])[0],
            )

            return PortalDataset(
                id=dataset_id,
                title=f"{package.get('title')} - {resource.get('name', '')}",
                description=package.get("notes", ""),
                portal=self.portal_name,
                portal_url=f"{self.base_url}/dataset/{package.get('name')}",
                download_url=resource.get("url"),
                format=resource.get("format", "unknown"),
                size_bytes=resource.get("size"),
                last_modified=resource.get("last_modified"),
                categories=[package.get("organization", {}).get("title", "")],
                keywords=package.get("tags", []),
                spatial_coverage=None,
                is_geospatial=True,
                metadata={"package": package, "resource": resource},
            )


async def harvest_all_portals(
    portals: List[PortalHarvester], output_file: Path
) -> Dict[str, List[PortalDataset]]:
    """Harvest datasets from all configured portals.

    Args:
        portals: List of portal harvesters
        output_file: Path to save discovered datasets

    Returns:
        Dictionary mapping portal name to discovered datasets
    """
    results = {}

    for harvester in portals:
        async with harvester:
            print(f"\n🔍 Discovering datasets from {harvester.portal_name}...")

            try:
                datasets = await harvester.discover_datasets()
                print(f"   Found {len(datasets)} total datasets")

                # Filter to environmental/geospatial
                filtered = harvester.filter_environmental_datasets(datasets)
                print(f"   Filtered to {len(filtered)} environmental datasets")

                results[harvester.portal_name] = filtered

            except Exception as e:
                print(f"   ❌ Error: {e}")
                results[harvester.portal_name] = []

    # Save results
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(
            {
                portal: [d.to_dict() for d in datasets]
                for portal, datasets in results.items()
            },
            f,
            indent=2,
        )

    print(f"\n✅ Saved discovered datasets to {output_file}")

    return results
