#!/usr/bin/env python3
"""
Satellite data processing pipeline for Ontario.

This script handles:
1. Downloading raw satellite data from government FTP servers
2. Clipping to Ontario bounds
3. Classification and polygonization
4. Vector tile generation (PMTiles format)
5. Upload to cloud storage

Requirements:
    pip install rasterio geopandas tippecanoe pmtiles

Usage:
    python scripts/process_satellite_data.py --data-type ndvi --year 2023
    python scripts/process_satellite_data.py --data-type landcover --year 2020
    python scripts/process_satellite_data.py --data-type elevation
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# Check for required dependencies
try:
    import geopandas as gpd
    import numpy as np
    import rasterio
    import rasterio.features
    import rasterio.mask
    from shapely.geometry import shape

    RASTERIO_AVAILABLE = True
except ImportError:
    print("ERROR: Required dependencies not installed")
    print("Install with: pip install rasterio geopandas numpy shapely")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Ontario bounds (lat/lon)
ONTARIO_BOUNDS = (-95.2, 41.7, -74.3, 56.9)  # (west, south, east, north)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "satellite"
PROCESSED_DIR = DATA_DIR / "processed" / "satellite"
TILES_DIR = DATA_DIR / "tiles"
REGISTRY_FILE = BASE_DIR / "satellite_data_registry.json"

# Ensure directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
TILES_DIR.mkdir(parents=True, exist_ok=True)


class SatelliteProcessor:
    """Process satellite data for Ontario."""

    def __init__(self, data_type: str, year: Optional[int] = None):
        """Initialize processor.

        Args:
            data_type: Type of data (ndvi, landcover, elevation)
            year: Year to process (if applicable)
        """
        self.data_type = data_type
        self.year = year
        self.ontario_bounds = ONTARIO_BOUNDS

        # Load registry
        if REGISTRY_FILE.exists():
            with open(REGISTRY_FILE) as f:
                self.registry = json.load(f)
        else:
            raise FileNotFoundError(f"Registry not found: {REGISTRY_FILE}")

    def clip_raster_to_ontario(
        self, input_path: Path, output_path: Path
    ) -> Tuple[Path, Dict]:
        """Clip raster to Ontario bounds.

        Args:
            input_path: Input raster file
            output_path: Output clipped raster file

        Returns:
            Tuple of (output path, metadata)
        """
        logger.info(f"Clipping {input_path.name} to Ontario bounds...")

        west, south, east, north = self.ontario_bounds

        with rasterio.open(input_path) as src:
            # Create bounding box in source CRS
            bbox = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [west, south],
                        [east, south],
                        [east, north],
                        [west, north],
                        [west, south],
                    ]
                ],
            }

            # Reproject bbox if needed
            if src.crs and src.crs.to_string() != "EPSG:4326":
                from rasterio.warp import transform_geom

                bbox = transform_geom("EPSG:4326", src.crs, bbox)

            bbox_shape = shape(bbox)

            # Mask raster to bbox
            out_image, out_transform = rasterio.mask.mask(
                src, [bbox_shape], crop=True, all_touched=True
            )

            # Copy metadata
            out_meta = src.meta.copy()
            out_meta.update(
                {
                    "driver": "GTiff",
                    "height": out_image.shape[1],
                    "width": out_image.shape[2],
                    "transform": out_transform,
                    "compress": "lzw",
                }
            )

            # Write clipped raster
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **out_meta) as dst:
                dst.write(out_image)

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Clipped raster saved: {output_path} ({size_mb:.1f} MB)")

        return output_path, {"size_mb": size_mb, "bounds": self.ontario_bounds}

    def classify_ndvi(self, input_path: Path, output_path: Path) -> Tuple[Path, Dict]:
        """Classify NDVI into vegetation categories.

        Args:
            input_path: Input NDVI raster
            output_path: Output classified raster

        Returns:
            Tuple of (output path, classification info)
        """
        logger.info("Classifying NDVI into vegetation categories...")

        with rasterio.open(input_path) as src:
            ndvi = src.read(1)

            # Create classification
            # -1 to 0: water/snow (0)
            # 0 to 0.2: barren (1)
            # 0.2 to 0.4: sparse vegetation (2)
            # 0.4 to 0.6: moderate vegetation (3)
            # 0.6 to 1.0: dense vegetation (4)
            classified = np.zeros_like(ndvi, dtype=np.uint8)
            classified[ndvi < 0] = 0
            classified[(ndvi >= 0) & (ndvi < 0.2)] = 1
            classified[(ndvi >= 0.2) & (ndvi < 0.4)] = 2
            classified[(ndvi >= 0.4) & (ndvi < 0.6)] = 3
            classified[(ndvi >= 0.6)] = 4

            # Write classified raster
            out_meta = src.meta.copy()
            out_meta.update(dtype=rasterio.uint8, compress="lzw")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **out_meta) as dst:
                dst.write(classified, 1)

        classification = {
            0: "water_snow",
            1: "barren",
            2: "sparse_vegetation",
            3: "moderate_vegetation",
            4: "dense_vegetation",
        }

        logger.info(f"Classified NDVI saved: {output_path}")
        return output_path, {"classification": classification}

    def polygonize_raster(
        self, input_path: Path, output_path: Path, value_name: str = "value"
    ) -> Tuple[Path, Dict]:
        """Convert classified raster to vector polygons.

        Args:
            input_path: Input classified raster
            output_path: Output GeoJSON file
            value_name: Name for the value field

        Returns:
            Tuple of (output path, polygon info)
        """
        logger.info("Converting raster to vector polygons...")

        with rasterio.open(input_path) as src:
            image = src.read(1)
            transform = src.transform
            crs = src.crs

            # Extract shapes
            shapes_gen = rasterio.features.shapes(
                image, transform=transform, connectivity=8
            )

            # Convert to GeoDataFrame
            geometries = []
            values = []

            for geom, value in shapes_gen:
                if value != 0:  # Skip nodata
                    geometries.append(shape(geom))
                    values.append(int(value))

            if not geometries:
                raise ValueError("No polygons extracted from raster")

            gdf = gpd.GeoDataFrame({value_name: values}, geometry=geometries, crs=crs)

            # Simplify geometries to reduce size
            logger.info("Simplifying geometries...")
            gdf["geometry"] = gdf.geometry.simplify(
                tolerance=0.001, preserve_topology=True
            )

            # Save as GeoJSON
            output_path.parent.mkdir(parents=True, exist_ok=True)
            gdf.to_file(output_path, driver="GeoJSON")

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(
            f"Polygonized data saved: {output_path} ({len(gdf)} features, {size_mb:.1f} MB)"
        )

        return output_path, {"feature_count": len(gdf), "size_mb": size_mb}

    def generate_pmtiles(
        self, input_geojson: Path, output_pmtiles: Path, layer_name: str
    ) -> Tuple[Path, Dict]:
        """Generate PMTiles from GeoJSON using tippecanoe.

        Args:
            input_geojson: Input GeoJSON file
            output_pmtiles: Output PMTiles file
            layer_name: Name of the vector layer

        Returns:
            Tuple of (output path, tile info)
        """
        logger.info("Generating PMTiles with tippecanoe...")

        # Check if tippecanoe is installed
        try:
            subprocess.run(
                ["tippecanoe", "--version"],
                capture_output=True,
                check=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error("tippecanoe not installed!")
            logger.info("Install: https://github.com/felt/tippecanoe#installation")
            logger.info("macOS: brew install tippecanoe")
            logger.info("Ubuntu: apt-get install tippecanoe")
            raise RuntimeError("tippecanoe required for tile generation") from e

        # Determine zoom levels based on data type
        if self.data_type == "ndvi":
            min_zoom, max_zoom = 4, 12
        elif self.data_type == "landcover":
            min_zoom, max_zoom = 4, 14
        else:  # elevation
            min_zoom, max_zoom = 4, 14

        # Run tippecanoe
        output_pmtiles.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "tippecanoe",
            "-o",
            str(output_pmtiles),
            "-Z",
            str(min_zoom),
            "-z",
            str(max_zoom),
            "-l",
            layer_name,
            "--drop-densest-as-needed",
            "--extend-zooms-if-still-dropping",
            "--force",
            str(input_geojson),
        ]

        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"tippecanoe failed: {result.stderr}")
            raise RuntimeError("Tile generation failed")

        size_mb = output_pmtiles.stat().st_size / (1024 * 1024)
        logger.info(f"PMTiles generated: {output_pmtiles} ({size_mb:.1f} MB)")

        return output_pmtiles, {
            "size_mb": size_mb,
            "zoom_range": [min_zoom, max_zoom],
            "format": "pmtiles",
        }

    def process_ndvi(self) -> Dict:
        """Process NDVI data for Ontario.

        Returns:
            Processing results
        """
        if not self.year:
            raise ValueError("Year required for NDVI processing")

        logger.info(f"Processing NDVI data for {self.year}...")

        # Define file paths
        raw_file = RAW_DIR / f"MODISCOMP7d_{self.year}.tif"
        clipped_file = PROCESSED_DIR / f"ndvi_{self.year}_ontario.tif"
        classified_file = PROCESSED_DIR / f"ndvi_{self.year}_classified.tif"
        vector_file = PROCESSED_DIR / f"ndvi_{self.year}.geojson"
        tiles_file = TILES_DIR / f"ndvi_{self.year}.pmtiles"

        results = {"year": self.year, "steps": {}}

        # Step 1: Check for raw data
        if not raw_file.exists():
            logger.warning(f"Raw NDVI data not found: {raw_file}")
            logger.info(
                "Download from: https://ftp.maps.canada.ca/pub/statcan_statcan/modis/"
            )
            return {
                "status": "error",
                "message": "Raw data not available. Manual download required.",
                "download_url": f"https://ftp.maps.canada.ca/pub/statcan_statcan/modis/MODISCOMP7d_{self.year}.zip",
            }

        # Step 2: Clip to Ontario
        if not clipped_file.exists():
            _, clip_info = self.clip_raster_to_ontario(raw_file, clipped_file)
            results["steps"]["clip"] = clip_info
        else:
            logger.info(f"Using existing clipped file: {clipped_file}")

        # Step 3: Classify
        if not classified_file.exists():
            _, class_info = self.classify_ndvi(clipped_file, classified_file)
            results["steps"]["classify"] = class_info
        else:
            logger.info(f"Using existing classified file: {classified_file}")

        # Step 4: Polygonize
        if not vector_file.exists():
            _, poly_info = self.polygonize_raster(
                classified_file, vector_file, "ndvi_class"
            )
            results["steps"]["polygonize"] = poly_info
        else:
            logger.info(f"Using existing vector file: {vector_file}")

        # Step 5: Generate tiles
        if not tiles_file.exists():
            _, tile_info = self.generate_pmtiles(vector_file, tiles_file, "ndvi")
            results["steps"]["tiles"] = tile_info
        else:
            logger.info(f"Using existing tiles: {tiles_file}")

        results["status"] = "success"
        results["output_files"] = {
            "clipped": str(clipped_file),
            "classified": str(classified_file),
            "vector": str(vector_file),
            "tiles": str(tiles_file),
        }

        return results

    def process_landcover(self) -> Dict:
        """Process land cover data for Ontario.

        Returns:
            Processing results
        """
        if not self.year:
            raise ValueError("Year required for land cover processing")

        logger.info(f"Processing land cover data for {self.year}...")

        # Define file paths
        raw_file = RAW_DIR / f"landcover_{self.year}.tif"
        clipped_file = PROCESSED_DIR / f"landcover_{self.year}_ontario.tif"
        vector_file = PROCESSED_DIR / f"landcover_{self.year}.geojson"
        tiles_file = TILES_DIR / f"landcover_{self.year}.pmtiles"

        results = {"year": self.year, "steps": {}}

        # Check for raw data
        if not raw_file.exists():
            logger.warning(f"Raw land cover data not found: {raw_file}")
            logger.info(
                "Download from: https://ftp.maps.canada.ca/pub/nrcan_rncan/Land-cover_Couverture-du-sol/"
            )
            return {
                "status": "error",
                "message": "Raw data not available. Manual download required.",
                "download_url": "https://ftp.maps.canada.ca/pub/nrcan_rncan/Land-cover_Couverture-du-sol/",
            }

        # Process steps...
        if not clipped_file.exists():
            _, clip_info = self.clip_raster_to_ontario(raw_file, clipped_file)
            results["steps"]["clip"] = clip_info

        if not vector_file.exists():
            _, poly_info = self.polygonize_raster(clipped_file, vector_file, "class_id")
            results["steps"]["polygonize"] = poly_info

        if not tiles_file.exists():
            _, tile_info = self.generate_pmtiles(vector_file, tiles_file, "landcover")
            results["steps"]["tiles"] = tile_info

        results["status"] = "success"
        results["output_files"] = {
            "clipped": str(clipped_file),
            "vector": str(vector_file),
            "tiles": str(tiles_file),
        }

        return results

    def update_registry(self, results: Dict):
        """Update satellite data registry with processing results.

        Args:
            results: Processing results
        """
        logger.info("Updating satellite data registry...")

        with open(REGISTRY_FILE) as f:
            registry = json.load(f)

        # Update dataset version
        dataset = registry["datasets"][self.data_type]

        if self.year:
            year_str = str(self.year)
            if "versions" not in dataset:
                dataset["versions"] = {}

            dataset["versions"][year_str] = {
                "processed_date": datetime.now().isoformat(),
                "status": results.get("status", "unknown"),
                "files": results.get("output_files", {}),
                "processing_steps": results.get("steps", {}),
            }

            if year_str not in dataset.get("years_available", []):
                dataset.setdefault("years_available", []).append(int(year_str))
                dataset["years_available"].sort()

        dataset["processing"]["last_run"] = datetime.now().isoformat()
        dataset["processing"]["status"] = results.get("status", "unknown")

        # Save updated registry
        with open(REGISTRY_FILE, "w") as f:
            json.dump(registry, f, indent=2)

        logger.info("Registry updated successfully")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Process satellite data for Ontario",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-type",
        choices=["ndvi", "landcover", "elevation"],
        required=True,
        help="Type of satellite data to process",
    )
    parser.add_argument(
        "--year", type=int, help="Year to process (required for NDVI and land cover)"
    )
    parser.add_argument(
        "--update-registry",
        action="store_true",
        default=True,
        help="Update satellite data registry after processing",
    )

    args = parser.parse_args()

    try:
        processor = SatelliteProcessor(args.data_type, args.year)

        if args.data_type == "ndvi":
            results = processor.process_ndvi()
        elif args.data_type == "landcover":
            results = processor.process_landcover()
        else:
            logger.error(f"Processing for {args.data_type} not yet implemented")
            sys.exit(1)

        print("\n" + "=" * 80)
        print("PROCESSING RESULTS")
        print("=" * 80)
        print(json.dumps(results, indent=2))

        if args.update_registry and results.get("status") == "success":
            processor.update_registry(results)

    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
