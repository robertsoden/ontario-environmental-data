#!/usr/bin/env python3
"""
Upload raster GeoTIFFs to Mapbox using the Uploads API.

This uses the correct API for raster data (not the Tiling Service which is for vectors).

Steps:
1. Request temporary S3 credentials from Mapbox
2. Upload file to Mapbox's S3 staging bucket
3. Create an upload job
4. Monitor until complete

Usage:
    python upload_raster_to_mapbox.py --token YOUR_SECRET_TOKEN
    python upload_raster_to_mapbox.py --token YOUR_SECRET_TOKEN --dataset ndvi_2024
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Mapbox configuration
MAPBOX_USERNAME = "robertsoden"
MAPBOX_API_BASE = "https://api.mapbox.com"

# S3 source configuration
S3_BUCKET = "ontario-environmental-data"

# Datasets to upload
DATASETS = {
    "ndvi_2024": {
        "s3_key": "datasets/satellite/ndvi/ontario_ndvi_2024_250m.tif",
        "tileset_name": "ndvi_2024",
        "description": "NDVI 2024 - MODIS 250m vegetation index"
    },
    "landcover_2020": {
        "s3_key": "datasets/satellite/landcover/ontario_landcover_2020.tif",
        "tileset_name": "landcover_2020",
        "description": "Land Cover 2020 - NALCMS 30m"
    },
    "landcover_2015": {
        "s3_key": "datasets/satellite/landcover/ontario_landcover_2015.tif",
        "tileset_name": "landcover_2015",
        "description": "Land Cover 2015 - NALCMS 30m"
    },
    "landcover_2010": {
        "s3_key": "datasets/satellite/landcover/ontario_landcover_2010.tif",
        "tileset_name": "landcover_2010",
        "description": "Land Cover 2010 - NALCMS 30m"
    }
}


def get_mapbox_credentials(token: str) -> dict:
    """
    Get temporary S3 credentials from Mapbox for uploading.

    Returns dict with: accessKeyId, bucket, key, secretAccessKey, sessionToken, url
    """
    logger.info("Requesting Mapbox S3 credentials...")

    response = requests.post(
        f"{MAPBOX_API_BASE}/uploads/v1/{MAPBOX_USERNAME}/credentials",
        params={"access_token": token}
    )

    if response.status_code != 200:
        raise Exception(f"Failed to get credentials: {response.status_code} - {response.text}")

    creds = response.json()
    logger.info(f"Got credentials for bucket: {creds['bucket']}")
    return creds


def upload_to_mapbox_s3(local_file: Path, creds: dict) -> str:
    """
    Upload a file to Mapbox's S3 staging bucket using temporary credentials.

    Returns the S3 URL to use for creating the upload.
    """
    logger.info(f"Uploading {local_file.name} to Mapbox S3...")

    # Set up AWS credentials for this upload
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = creds["accessKeyId"]
    env["AWS_SECRET_ACCESS_KEY"] = creds["secretAccessKey"]
    env["AWS_SESSION_TOKEN"] = creds["sessionToken"]

    s3_dest = f"s3://{creds['bucket']}/{creds['key']}"

    cmd = [
        "aws", "s3", "cp",
        str(local_file),
        s3_dest,
        "--region", "us-east-1"
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"S3 upload failed: {result.stderr}")

    logger.info(f"Uploaded to {s3_dest}")
    return creds["url"]


def create_upload(token: str, staged_url: str, tileset_name: str) -> str:
    """
    Create a Mapbox upload job from a staged S3 file.

    Returns the upload ID.
    """
    tileset_id = f"{MAPBOX_USERNAME}.{tileset_name}"
    logger.info(f"Creating upload for tileset: {tileset_id}")

    response = requests.post(
        f"{MAPBOX_API_BASE}/uploads/v1/{MAPBOX_USERNAME}",
        params={"access_token": token},
        json={
            "url": staged_url,
            "tileset": tileset_id,
            "name": tileset_name
        }
    )

    if response.status_code not in [200, 201]:
        raise Exception(f"Failed to create upload: {response.status_code} - {response.text}")

    result = response.json()
    upload_id = result["id"]
    logger.info(f"Upload created with ID: {upload_id}")
    return upload_id


def wait_for_upload(token: str, upload_id: str, timeout: int = 3600) -> dict:
    """
    Wait for an upload to complete.

    Returns the final upload status.
    """
    logger.info(f"Waiting for upload {upload_id} to complete...")

    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            raise Exception(f"Upload timed out after {timeout} seconds")

        response = requests.get(
            f"{MAPBOX_API_BASE}/uploads/v1/{MAPBOX_USERNAME}/{upload_id}",
            params={"access_token": token}
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get upload status: {response.status_code} - {response.text}")

        status = response.json()
        progress = status.get("progress", 0)
        complete = status.get("complete", False)
        error = status.get("error")

        if error:
            raise Exception(f"Upload failed: {error}")

        if complete:
            logger.info(f"Upload complete!")
            return status

        logger.info(f"Progress: {progress * 100:.1f}%")
        time.sleep(10)


def download_from_s3(s3_key: str, local_path: Path) -> Path:
    """Download a file from our S3 bucket."""
    if local_path.exists():
        size_mb = local_path.stat().st_size / (1024 * 1024)
        logger.info(f"Using cached file: {local_path.name} ({size_mb:.1f} MB)")
        return local_path

    logger.info(f"Downloading s3://{S3_BUCKET}/{s3_key}...")

    cmd = ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{s3_key}", str(local_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Download failed: {result.stderr}")

    size_mb = local_path.stat().st_size / (1024 * 1024)
    logger.info(f"Downloaded {local_path.name} ({size_mb:.1f} MB)")
    return local_path


def upload_dataset(token: str, dataset_id: str, config: dict, work_dir: Path) -> dict:
    """
    Upload a single dataset to Mapbox.

    Returns result dict with tileset info.
    """
    logger.info("=" * 60)
    logger.info(f"UPLOADING: {config['description']}")
    logger.info("=" * 60)

    # Download from our S3
    local_file = work_dir / f"{dataset_id}.tif"
    download_from_s3(config["s3_key"], local_file)

    # Get Mapbox credentials
    creds = get_mapbox_credentials(token)

    # Upload to Mapbox S3
    staged_url = upload_to_mapbox_s3(local_file, creds)

    # Create upload job
    upload_id = create_upload(token, staged_url, config["tileset_name"])

    # Wait for completion
    status = wait_for_upload(token, upload_id)

    tileset_id = f"{MAPBOX_USERNAME}.{config['tileset_name']}"

    return {
        "dataset_id": dataset_id,
        "tileset_id": tileset_id,
        "tileset_url": f"mapbox://{tileset_id}",
        "upload_id": upload_id,
        "status": "complete"
    }


def main():
    parser = argparse.ArgumentParser(description="Upload raster GeoTIFFs to Mapbox")
    parser.add_argument("--token", required=True, help="Mapbox secret access token (sk.xxx)")
    parser.add_argument("--dataset", choices=list(DATASETS.keys()) + ["all"], default="all",
                        help="Which dataset to upload (default: all)")
    parser.add_argument("--work-dir", type=Path, default=Path.home() / "mapbox_uploads",
                        help="Working directory for downloads")
    args = parser.parse_args()

    # Validate token
    if not args.token.startswith("sk."):
        logger.error("Token must be a secret token (starts with 'sk.')")
        sys.exit(1)

    # Create work directory
    args.work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("MAPBOX RASTER UPLOAD")
    logger.info("=" * 60)
    logger.info(f"Username: {MAPBOX_USERNAME}")
    logger.info(f"Work directory: {args.work_dir}")

    # Select datasets
    if args.dataset == "all":
        datasets_to_upload = DATASETS
    else:
        datasets_to_upload = {args.dataset: DATASETS[args.dataset]}

    logger.info(f"Datasets to upload: {list(datasets_to_upload.keys())}")

    results = []

    for dataset_id, config in datasets_to_upload.items():
        try:
            result = upload_dataset(args.token, dataset_id, config, args.work_dir)
            results.append(result)
            logger.info(f"✓ {dataset_id} uploaded successfully")
        except Exception as e:
            logger.error(f"✗ {dataset_id} failed: {e}")
            results.append({
                "dataset_id": dataset_id,
                "status": "failed",
                "error": str(e)
            })

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("UPLOAD SUMMARY")
    logger.info("=" * 60)

    for result in results:
        if result["status"] == "complete":
            logger.info(f"✓ {result['dataset_id']}: {result['tileset_url']}")
        else:
            logger.error(f"✗ {result['dataset_id']}: {result.get('error', 'Unknown error')}")

    # Save results
    results_file = args.work_dir / "upload_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nResults saved to: {results_file}")

    logger.info("")
    logger.info("Tileset URLs for layers.yaml:")
    for result in results:
        if result["status"] == "complete":
            logger.info(f"  {result['dataset_id']}: {result['tileset_url']}")


if __name__ == "__main__":
    main()
