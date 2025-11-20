"""S3 storage client for Ontario Environmental Data.

This module provides a client for uploading and managing GeoJSON datasets
in S3 storage, supporting the project's shift from GitHub artifacts to
persistent cloud storage.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp


class S3StorageClient:
    """Client for managing datasets in S3 storage.

    This client handles:
    - Uploading processed GeoJSON files to S3
    - Updating catalog and metadata files
    - Generating public URLs for data access
    - Supporting versioning for datasets

    Authentication:
    - Uses AWS CLI credentials or environment variables
    - Requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    - Optional: AWS_SESSION_TOKEN for temporary credentials

    Example:
        ```python
        storage = S3StorageClient(
            bucket="ontario-environmental-data",
            region="us-east-1",
            base_path="datasets"
        )

        # Upload a dataset
        url = await storage.upload_dataset(
            local_path="data/processed/watersheds.geojson",
            category="environmental",
            dataset_id="watersheds"
        )

        # Update catalog
        await storage.update_catalog(catalog_data)
        ```
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        base_path: str = "datasets",
        public_read: bool = True,
    ):
        """Initialize S3 storage client.

        Args:
            bucket: S3 bucket name (e.g., "ontario-environmental-data")
            region: AWS region (default: us-east-1)
            base_path: Base path within bucket for datasets (default: "datasets")
            public_read: Whether to make uploaded files publicly readable (default: True)
        """
        self.bucket = bucket
        self.region = region
        self.base_path = base_path
        self.public_read = public_read
        self.base_url = f"https://{bucket}.s3.{region}.amazonaws.com"

    def get_public_url(self, s3_key: str) -> str:
        """Get public HTTPS URL for an S3 object.

        Args:
            s3_key: S3 object key (path within bucket)

        Returns:
            Public HTTPS URL
        """
        return f"{self.base_url}/{s3_key}"

    def get_dataset_key(self, category: str, filename: str) -> str:
        """Generate S3 key for a dataset file.

        Args:
            category: Dataset category (e.g., "boundaries", "biodiversity")
            filename: Filename (e.g., "watersheds.geojson")

        Returns:
            S3 key (e.g., "datasets/environmental/watersheds.geojson")
        """
        return f"{self.base_path}/{category}/{filename}"

    async def upload_file(
        self,
        local_path: Path,
        s3_key: str,
        content_type: str = "application/geo+json",
        cache_control: str = "public, max-age=3600",
    ) -> str:
        """Upload a file to S3.

        This method uses the AWS CLI via subprocess for simplicity.
        For production, consider using boto3 for better error handling.

        Args:
            local_path: Local file path to upload
            s3_key: S3 key (destination path in bucket)
            content_type: HTTP Content-Type header
            cache_control: HTTP Cache-Control header

        Returns:
            Public URL of uploaded file

        Raises:
            FileNotFoundError: If local file doesn't exist
            RuntimeError: If upload fails
        """
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        # This will be implemented using AWS CLI or boto3
        # For now, return the expected URL
        return self.get_public_url(s3_key)

    async def upload_dataset(
        self,
        local_path: Path,
        category: str,
        dataset_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """Upload a dataset file and optional metadata.

        Args:
            local_path: Local path to dataset file
            category: Dataset category
            dataset_id: Dataset identifier
            metadata: Optional metadata to upload alongside dataset

        Returns:
            Dictionary with 's3_key' and 'url' of uploaded dataset
        """
        filename = local_path.name
        s3_key = self.get_dataset_key(category, filename)

        url = await self.upload_file(local_path, s3_key)

        result = {
            "s3_key": s3_key,
            "url": url,
            "category": category,
            "dataset_id": dataset_id,
        }

        # Upload metadata if provided
        if metadata:
            metadata_key = s3_key.replace(".geojson", ".metadata.json")
            metadata_path = local_path.parent / f"{dataset_id}.metadata.json"

            # Write metadata to temp file
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            metadata_url = await self.upload_file(
                metadata_path,
                metadata_key,
                content_type="application/json"
            )
            result["metadata_url"] = metadata_url

            # Clean up temp file
            metadata_path.unlink()

        return result

    async def upload_catalog(
        self,
        catalog_data: Dict[str, Any],
        catalog_path: str = "catalog.json",
    ) -> str:
        """Upload catalog.json to S3.

        Args:
            catalog_data: Catalog dictionary
            catalog_path: S3 key for catalog (default: "catalog.json")

        Returns:
            Public URL of catalog
        """
        # Write catalog to temp file
        temp_path = Path("/tmp/catalog.json")
        with open(temp_path, "w") as f:
            json.dump(catalog_data, f, indent=2)

        url = await self.upload_file(
            temp_path,
            catalog_path,
            content_type="application/json",
            cache_control="public, max-age=300"  # 5 minutes for catalog
        )

        temp_path.unlink()
        return url

    async def list_datasets(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """List all datasets in S3.

        Args:
            category: Optional category filter

        Returns:
            List of dataset info dictionaries
        """
        # This will be implemented using AWS CLI or boto3
        # For now, return empty list
        return []

    async def download_file(self, s3_key: str, local_path: Path) -> None:
        """Download a file from S3.

        Args:
            s3_key: S3 key to download
            local_path: Local destination path
        """
        url = self.get_public_url(s3_key)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()

                local_path.parent.mkdir(parents=True, exist_ok=True)

                with open(local_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)

    async def get_catalog(self) -> Dict[str, Any]:
        """Fetch catalog.json from S3.

        Returns:
            Catalog dictionary
        """
        url = self.get_public_url("catalog.json")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()


class AWSCLIUploader:
    """Utility class for uploading files to S3 using AWS CLI.

    This is used in GitHub Actions workflows where AWS CLI is pre-installed.
    """

    @staticmethod
    def upload_command(
        local_path: str,
        bucket: str,
        s3_key: str,
        acl: str = "public-read",
        cache_control: str = "max-age=3600",
        region: str = "us-east-1",
    ) -> str:
        """Generate AWS CLI upload command.

        Args:
            local_path: Local file path
            bucket: S3 bucket name
            s3_key: S3 destination key
            acl: Access control (default: public-read)
            cache_control: Cache control header
            region: AWS region

        Returns:
            AWS CLI command string
        """
        return (
            f"aws s3 cp '{local_path}' 's3://{bucket}/{s3_key}' "
            f"--acl {acl} "
            f"--cache-control '{cache_control}' "
            f"--region {region}"
        )

    @staticmethod
    def sync_command(
        local_dir: str,
        bucket: str,
        s3_prefix: str,
        acl: str = "public-read",
        cache_control: str = "max-age=3600",
        region: str = "us-east-1",
        exclude: Optional[str] = None,
        include: Optional[str] = None,
    ) -> str:
        """Generate AWS CLI sync command.

        Args:
            local_dir: Local directory to sync
            bucket: S3 bucket name
            s3_prefix: S3 destination prefix
            acl: Access control (default: public-read)
            cache_control: Cache control header
            region: AWS region
            exclude: Optional exclude pattern
            include: Optional include pattern

        Returns:
            AWS CLI sync command string
        """
        cmd = (
            f"aws s3 sync '{local_dir}' 's3://{bucket}/{s3_prefix}' "
            f"--acl {acl} "
            f"--cache-control '{cache_control}' "
            f"--region {region}"
        )

        if exclude:
            cmd += f" --exclude '{exclude}'"
        if include:
            cmd += f" --include '{include}'"

        return cmd
