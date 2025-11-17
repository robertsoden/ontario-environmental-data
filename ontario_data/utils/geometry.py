"""Geometry utilities for processing AOIs and filtering observations.

This module provides utilities for working with GeoJSON geometries, bounding boxes,
and spatial filtering of observations.
"""

from typing import Dict, List, Tuple


def get_bounds_from_aoi(aoi: dict) -> Tuple[float, float, float, float]:
    """Extract bounding box from AOI geometry.

    Args:
        aoi: Area of interest dictionary with GeoJSON geometry.
             Can be either a geometry dict or dict with 'geometry' key.
             Supports Polygon, MultiPolygon, and Point types.

    Returns:
        Tuple of (swlat, swlng, nelat, nelng) representing the bounding box.
        For Point geometries, creates a small buffer (~11km) around the point.

    Raises:
        ValueError: If geometry type is not supported.

    Examples:
        >>> aoi = {"geometry": {"type": "Point", "coordinates": [-79.0, 44.0]}}
        >>> bounds = get_bounds_from_aoi(aoi)
        >>> bounds
        (43.9, -79.1, 44.1, -78.9)

        >>> polygon_aoi = {
        ...     "type": "Polygon",
        ...     "coordinates": [[[-79.0, 44.0], [-78.0, 44.0], [-78.0, 45.0], [-79.0, 45.0], [-79.0, 44.0]]]
        ... }
        >>> bounds = get_bounds_from_aoi(polygon_aoi)
        >>> bounds
        (44.0, -79.0, 45.0, -78.0)
    """
    # Handle different AOI formats
    if "geometry" in aoi:
        geometry = aoi["geometry"]
    else:
        geometry = aoi

    # Extract coordinates based on geometry type
    if geometry.get("type") == "Polygon":
        coords = geometry["coordinates"][0]
    elif geometry.get("type") == "MultiPolygon":
        # Use first polygon for bounds
        coords = geometry["coordinates"][0][0]
    elif geometry.get("type") == "Point":
        # Create small bounds around point (~11km buffer)
        lon, lat = geometry["coordinates"]
        buffer = 0.1
        return (lat - buffer, lon - buffer, lat + buffer, lon + buffer)
    else:
        raise ValueError(f"Unsupported geometry type: {geometry.get('type')}")

    # Calculate bounding box from coordinates
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    return (
        min(lats),  # swlat (southwest latitude)
        min(lons),  # swlng (southwest longitude)
        max(lats),  # nelat (northeast latitude)
        max(lons),  # nelng (northeast longitude)
    )


def point_in_bounds(
    point: Tuple[float, float], bounds: Tuple[float, float, float, float]
) -> bool:
    """Check if a point is within bounding box.

    Args:
        point: Tuple of (latitude, longitude)
        bounds: Tuple of (swlat, swlng, nelat, nelng)

    Returns:
        True if point is within bounds, False otherwise.

    Examples:
        >>> bounds = (44.0, -79.0, 45.0, -78.0)
        >>> point_in_bounds((44.5, -78.5), bounds)
        True
        >>> point_in_bounds((43.0, -78.5), bounds)
        False
    """
    lat, lon = point
    swlat, swlng, nelat, nelng = bounds

    return swlat <= lat <= nelat and swlng <= lon <= nelng


def filter_by_bounds(
    observations: List[Dict], bounds: Tuple[float, float, float, float]
) -> List[Dict]:
    """Filter observations by bounding box.

    Filters a list of observation dictionaries to only include those
    within the specified bounding box. Observations must have 'lat' and 'lng'
    keys.

    Args:
        observations: List of observation dictionaries with 'lat' and 'lng' keys
        bounds: Tuple of (swlat, swlng, nelat, nelng)

    Returns:
        List of observations that fall within the bounding box.

    Examples:
        >>> obs = [
        ...     {"id": 1, "lat": 44.5, "lng": -78.5},
        ...     {"id": 2, "lat": 43.0, "lng": -78.5},
        ...     {"id": 3, "lat": 44.8, "lng": -78.2}
        ... ]
        >>> bounds = (44.0, -79.0, 45.0, -78.0)
        >>> filtered = filter_by_bounds(obs, bounds)
        >>> len(filtered)
        2
        >>> filtered[0]["id"]
        1
    """
    filtered = []

    for obs in observations:
        lat = obs.get("lat")
        lon = obs.get("lng")

        if lat is not None and lon is not None:
            if point_in_bounds((lat, lon), bounds):
                filtered.append(obs)

    return filtered
