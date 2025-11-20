"""
Data validation utilities for Ontario Environmental Data.

This module provides functions to validate downloaded data to ensure:
1. Files exist and are not empty
2. Data formats are correct (GeoJSON, JSON, CSV)
3. Data contains expected fields and minimum number of records
4. Geometries are valid (for spatial data)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import pandas as pd
from shapely.validation import explain_validity


class ValidationError(Exception):
    """Raised when data validation fails."""

    pass


def validate_file_exists(file_path: Path, min_size_bytes: int = 100) -> None:
    """
    Validate that a file exists and is not empty.

    Args:
        file_path: Path to the file
        min_size_bytes: Minimum file size in bytes (default 100)

    Raises:
        ValidationError: If file doesn't exist or is too small
    """
    if not file_path.exists():
        raise ValidationError(f"File does not exist: {file_path}")

    size = file_path.stat().st_size
    if size < min_size_bytes:
        raise ValidationError(
            f"File is too small ({size} bytes, expected at least {min_size_bytes}): {file_path}"
        )


def validate_json_file(
    file_path: Path, required_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Validate that a file is valid JSON and contains required keys.

    Args:
        file_path: Path to JSON file
        required_keys: List of required top-level keys

    Returns:
        Parsed JSON data

    Raises:
        ValidationError: If JSON is invalid or missing required keys
    """
    validate_file_exists(file_path)

    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in {file_path}: {e}") from e

    if required_keys:
        missing_keys = set(required_keys) - set(data.keys())
        if missing_keys:
            raise ValidationError(
                f"JSON missing required keys in {file_path}: {missing_keys}"
            )

    return data


def validate_geojson_file(
    file_path: Path,
    min_features: int = 1,
    required_properties: Optional[List[str]] = None,
    check_geometries: bool = True,
) -> Tuple[gpd.GeoDataFrame, List[str]]:
    """
    Validate that a file is valid GeoJSON with expected content.

    Args:
        file_path: Path to GeoJSON file
        min_features: Minimum number of features expected
        required_properties: List of required properties for each feature
        check_geometries: Whether to validate geometry validity

    Returns:
        Tuple of (GeoDataFrame, list of warnings)

    Raises:
        ValidationError: If GeoJSON is invalid or doesn't meet requirements
    """
    validate_file_exists(file_path)

    warnings = []

    # Try to load as GeoDataFrame
    try:
        gdf = gpd.read_file(file_path)
    except Exception as e:
        raise ValidationError(f"Failed to read GeoJSON {file_path}: {e}") from e

    # Check feature count
    if len(gdf) < min_features:
        raise ValidationError(
            f"GeoJSON has too few features in {file_path}: {len(gdf)} (expected at least {min_features})"
        )

    # Check required properties
    if required_properties:
        missing_props = set(required_properties) - set(gdf.columns)
        if missing_props:
            raise ValidationError(
                f"GeoJSON missing required properties in {file_path}: {missing_props}"
            )

    # Check CRS
    if gdf.crs is None:
        warnings.append(f"GeoJSON has no CRS defined in {file_path}")
    elif gdf.crs.to_string() != "EPSG:4326":
        warnings.append(
            f"GeoJSON CRS is {gdf.crs.to_string()}, expected EPSG:4326 in {file_path}"
        )

    # Check geometries
    if check_geometries and "geometry" in gdf.columns:
        invalid_geoms = []
        for idx, geom in enumerate(gdf.geometry):
            if geom is None or geom.is_empty:
                invalid_geoms.append(f"Feature {idx}: empty geometry")
            elif not geom.is_valid:
                invalid_geoms.append(f"Feature {idx}: {explain_validity(geom)}")

        if invalid_geoms:
            # If more than 10% of geometries are invalid, fail
            if len(invalid_geoms) > len(gdf) * 0.1:
                raise ValidationError(
                    f"Too many invalid geometries in {file_path}: {len(invalid_geoms)}/{len(gdf)}"
                )
            else:
                warnings.append(
                    f"Some invalid geometries in {file_path}: {len(invalid_geoms)}/{len(gdf)}"
                )

    return gdf, warnings


def validate_json_observations(
    file_path: Path,
    min_observations: int = 1,
    required_fields: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate JSON file containing observation records.

    Args:
        file_path: Path to JSON file
        min_observations: Minimum number of observations expected
        required_fields: List of required fields for each observation

    Returns:
        Tuple of (observations list, list of warnings)

    Raises:
        ValidationError: If data is invalid or doesn't meet requirements
    """
    data = validate_json_file(file_path)

    warnings = []

    # Support both list of observations and dict with observations key
    if isinstance(data, dict):
        if "observations" in data:
            observations = data["observations"]
        elif "features" in data:
            observations = data["features"]
        else:
            # Assume it's a single observation
            observations = [data]
    elif isinstance(data, list):
        observations = data
    else:
        raise ValidationError(
            f"JSON data is not a list or dict in {file_path}: {type(data)}"
        )

    # Check observation count
    if len(observations) < min_observations:
        raise ValidationError(
            f"Too few observations in {file_path}: {len(observations)} (expected at least {min_observations})"
        )

    # Check required fields
    if required_fields:
        for idx, obs in enumerate(observations[:10]):  # Check first 10
            missing_fields = set(required_fields) - set(obs.keys())
            if missing_fields:
                warnings.append(
                    f"Observation {idx} missing fields in {file_path}: {missing_fields}"
                )

    return observations, warnings


def validate_collection_results(
    results: Dict[str, Any],
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate data collection results dictionary.

    Args:
        results: Collection results dictionary with 'sources' key

    Returns:
        Tuple of (success, list of errors, list of warnings)
    """
    errors = []
    warnings = []

    if "sources" not in results:
        errors.append("Collection results missing 'sources' key")
        return False, errors, warnings

    sources = results["sources"]

    # Check each source
    for source_name, source_info in sources.items():
        status = source_info.get("status")

        if status == "error":
            error_msg = source_info.get("error", "Unknown error")
            errors.append(f"{source_name}: {error_msg}")

        elif status == "no_data":
            warnings.append(f"{source_name}: No data returned (may be expected)")

        elif status == "success":
            # Validate file exists if specified
            if "file" in source_info:
                file_path = Path(source_info["file"])
                try:
                    validate_file_exists(file_path)
                except ValidationError as e:
                    errors.append(f"{source_name}: {e}")

            # Check count
            if "count" in source_info:
                count = source_info["count"]
                if count == 0:
                    warnings.append(f"{source_name}: File exists but has 0 records")

        elif status == "metadata_only":
            # This is OK for satellite data
            pass

        else:
            warnings.append(f"{source_name}: Unknown status '{status}'")

    success = len(errors) == 0
    return success, errors, warnings


def validate_data_file(
    file_path: Path,
    data_type: str,
    min_records: int = 1,
    required_fields: Optional[List[str]] = None,
) -> Tuple[bool, List[str], List[str]]:
    """
    Validate a data file based on its type.

    Args:
        file_path: Path to data file
        data_type: Type of data ('geojson', 'json', 'csv')
        min_records: Minimum number of records expected
        required_fields: List of required fields/properties

    Returns:
        Tuple of (success, list of errors, list of warnings)
    """
    errors = []
    warnings = []

    try:
        if data_type == "geojson":
            _, file_warnings = validate_geojson_file(
                file_path,
                min_features=min_records,
                required_properties=required_fields,
            )
            warnings.extend(file_warnings)

        elif data_type == "json":
            _, file_warnings = validate_json_observations(
                file_path,
                min_observations=min_records,
                required_fields=required_fields,
            )
            warnings.extend(file_warnings)

        elif data_type == "csv":
            validate_file_exists(file_path)
            try:
                df = pd.read_csv(file_path)
                if len(df) < min_records:
                    errors.append(
                        f"CSV has too few records: {len(df)} (expected at least {min_records})"
                    )
                if required_fields:
                    missing_fields = set(required_fields) - set(df.columns)
                    if missing_fields:
                        errors.append(f"CSV missing required columns: {missing_fields}")
            except Exception as e:
                errors.append(f"Failed to read CSV: {e}")

        else:
            errors.append(f"Unknown data type: {data_type}")

    except ValidationError as e:
        errors.append(str(e))

    success = len(errors) == 0
    return success, errors, warnings
