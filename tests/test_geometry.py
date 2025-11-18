"""Tests for geometry utilities."""

import pytest

from ontario_data.utils.geometry import (
    filter_by_bounds,
    get_bounds_from_aoi,
    point_in_bounds,
)


class TestGetBoundsFromAOI:
    """Tests for get_bounds_from_aoi function."""

    def test_polygon_geometry(self):
        """Test extracting bounds from a polygon geometry."""
        aoi = {
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-79.0, 44.0],
                        [-78.0, 44.0],
                        [-78.0, 45.0],
                        [-79.0, 45.0],
                        [-79.0, 44.0],
                    ]
                ],
            }
        }
        bounds = get_bounds_from_aoi(aoi)
        assert bounds == (44.0, -79.0, 45.0, -78.0)

    def test_polygon_without_geometry_key(self):
        """Test extracting bounds from a polygon without 'geometry' wrapper."""
        aoi = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-79.0, 44.0],
                    [-78.0, 44.0],
                    [-78.0, 45.0],
                    [-79.0, 45.0],
                    [-79.0, 44.0],
                ]
            ],
        }
        bounds = get_bounds_from_aoi(aoi)
        assert bounds == (44.0, -79.0, 45.0, -78.0)

    def test_multipolygon_geometry(self):
        """Test extracting bounds from a multipolygon (uses first polygon)."""
        aoi = {
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [-79.0, 44.0],
                            [-78.0, 44.0],
                            [-78.0, 45.0],
                            [-79.0, 45.0],
                            [-79.0, 44.0],
                        ]
                    ],
                    [
                        [
                            [-77.0, 43.0],
                            [-76.0, 43.0],
                            [-76.0, 44.0],
                            [-77.0, 44.0],
                            [-77.0, 43.0],
                        ]
                    ],
                ],
            }
        }
        bounds = get_bounds_from_aoi(aoi)
        # Should use first polygon
        assert bounds == (44.0, -79.0, 45.0, -78.0)

    def test_point_geometry(self):
        """Test extracting bounds from a point (creates buffer)."""
        aoi = {"geometry": {"type": "Point", "coordinates": [-79.0, 44.0]}}
        bounds = get_bounds_from_aoi(aoi)
        # Should create 0.1 degree buffer (~11km)
        assert bounds == pytest.approx((43.9, -79.1, 44.1, -78.9))

    def test_unsupported_geometry_type(self):
        """Test that unsupported geometry types raise ValueError."""
        aoi = {
            "geometry": {
                "type": "LineString",
                "coordinates": [[-79.0, 44.0], [-78.0, 45.0]],
            }
        }
        with pytest.raises(ValueError, match="Unsupported geometry type"):
            get_bounds_from_aoi(aoi)


class TestPointInBounds:
    """Tests for point_in_bounds function."""

    def test_point_inside_bounds(self):
        """Test that a point inside bounds returns True."""
        bounds = (44.0, -79.0, 45.0, -78.0)
        assert point_in_bounds((44.5, -78.5), bounds) is True

    def test_point_outside_bounds_latitude(self):
        """Test that a point outside bounds (latitude) returns False."""
        bounds = (44.0, -79.0, 45.0, -78.0)
        assert point_in_bounds((43.0, -78.5), bounds) is False
        assert point_in_bounds((46.0, -78.5), bounds) is False

    def test_point_outside_bounds_longitude(self):
        """Test that a point outside bounds (longitude) returns False."""
        bounds = (44.0, -79.0, 45.0, -78.0)
        assert point_in_bounds((44.5, -80.0), bounds) is False
        assert point_in_bounds((44.5, -77.0), bounds) is False

    def test_point_on_boundary(self):
        """Test that a point on the boundary is considered inside."""
        bounds = (44.0, -79.0, 45.0, -78.0)
        assert point_in_bounds((44.0, -78.5), bounds) is True
        assert point_in_bounds((45.0, -78.5), bounds) is True
        assert point_in_bounds((44.5, -79.0), bounds) is True
        assert point_in_bounds((44.5, -78.0), bounds) is True

    def test_point_at_corner(self):
        """Test that a point at a corner is considered inside."""
        bounds = (44.0, -79.0, 45.0, -78.0)
        assert point_in_bounds((44.0, -79.0), bounds) is True
        assert point_in_bounds((45.0, -78.0), bounds) is True


class TestFilterByBounds:
    """Tests for filter_by_bounds function."""

    def test_filter_observations_inside_bounds(self):
        """Test filtering observations to only include those inside bounds."""
        observations = [
            {"id": 1, "lat": 44.5, "lng": -78.5, "species": "Deer"},
            {"id": 2, "lat": 43.0, "lng": -78.5, "species": "Bear"},
            {"id": 3, "lat": 44.8, "lng": -78.2, "species": "Moose"},
            {"id": 4, "lat": 46.0, "lng": -78.5, "species": "Elk"},
        ]
        bounds = (44.0, -79.0, 45.0, -78.0)

        filtered = filter_by_bounds(observations, bounds)

        assert len(filtered) == 2
        assert filtered[0]["id"] == 1
        assert filtered[1]["id"] == 3

    def test_filter_empty_list(self):
        """Test filtering an empty list returns empty list."""
        bounds = (44.0, -79.0, 45.0, -78.0)
        filtered = filter_by_bounds([], bounds)
        assert filtered == []

    def test_filter_no_matches(self):
        """Test filtering when no observations are in bounds."""
        observations = [
            {"id": 1, "lat": 43.0, "lng": -78.5},
            {"id": 2, "lat": 46.0, "lng": -78.5},
        ]
        bounds = (44.0, -79.0, 45.0, -78.0)

        filtered = filter_by_bounds(observations, bounds)
        assert filtered == []

    def test_filter_missing_coordinates(self):
        """Test that observations with missing coordinates are skipped."""
        observations = [
            {"id": 1, "lat": 44.5, "lng": -78.5},
            {"id": 2, "lat": None, "lng": -78.5},
            {"id": 3, "lat": 44.5, "lng": None},
            {"id": 4, "lat": 44.7, "lng": -78.3},
        ]
        bounds = (44.0, -79.0, 45.0, -78.0)

        filtered = filter_by_bounds(observations, bounds)

        assert len(filtered) == 2
        assert filtered[0]["id"] == 1
        assert filtered[1]["id"] == 4

    def test_filter_preserves_observation_data(self):
        """Test that filtering preserves all observation data."""
        observations = [
            {
                "id": 1,
                "lat": 44.5,
                "lng": -78.5,
                "species": "Deer",
                "date": "2024-11-17",
                "observer": "John Doe",
            }
        ]
        bounds = (44.0, -79.0, 45.0, -78.0)

        filtered = filter_by_bounds(observations, bounds)

        assert len(filtered) == 1
        assert filtered[0]["id"] == 1
        assert filtered[0]["species"] == "Deer"
        assert filtered[0]["date"] == "2024-11-17"
        assert filtered[0]["observer"] == "John Doe"
