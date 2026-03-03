"""Tests for pge_outages.transform module.

Covers the jq-equivalent transformation logic that converts raw PG&E
ArcGIS API responses into the flat record format stored in outages.json.
"""

import pytest

from pge_outages.transform import (
    EXCLUDED_FIELDS,
    extract_geometry,
    flatten_feature,
    remove_excluded_fields,
    transform_api_response,
)


# ---------------------------------------------------------------------------
# remove_excluded_fields
# ---------------------------------------------------------------------------


class TestRemoveExcludedFields:
    """Tests for remove_excluded_fields()."""

    def test_removes_objectid(self):
        attrs = {"OBJECTID": 123, "F_OUTAGE_ID": "1"}
        result = remove_excluded_fields(attrs)
        assert "OBJECTID" not in result
        assert result == {"F_OUTAGE_ID": "1"}

    def test_removes_bluesky(self):
        attrs = {"blueSkyNotificationSubscription": "val", "CITY": "SF"}
        result = remove_excluded_fields(attrs)
        assert "blueSkyNotificationSubscription" not in result
        assert result == {"CITY": "SF"}

    def test_removes_both_excluded(self):
        attrs = {
            "OBJECTID": 1,
            "blueSkyNotificationSubscription": "x",
            "F_OUTAGE_ID": "42",
            "CITY": "Oakland",
        }
        result = remove_excluded_fields(attrs)
        assert set(result.keys()) == {"F_OUTAGE_ID", "CITY"}

    def test_no_excluded_fields_present(self):
        attrs = {"F_OUTAGE_ID": "1", "CITY": "LA"}
        result = remove_excluded_fields(attrs)
        assert result == attrs

    def test_empty_dict(self):
        assert remove_excluded_fields({}) == {}

    def test_preserves_none_values(self):
        attrs = {"CREW_ETA": None, "OBJECTID": 5}
        result = remove_excluded_fields(attrs)
        assert result == {"CREW_ETA": None}

    def test_returns_new_dict(self):
        """Verify the original dict is not mutated."""
        attrs = {"OBJECTID": 1, "CITY": "SF"}
        result = remove_excluded_fields(attrs)
        assert "OBJECTID" in attrs  # original unchanged
        assert "OBJECTID" not in result

    def test_type_error_on_non_dict(self):
        with pytest.raises(TypeError, match="Expected dict"):
            remove_excluded_fields("not a dict")

    def test_type_error_on_list(self):
        with pytest.raises(TypeError, match="Expected dict"):
            remove_excluded_fields([{"OBJECTID": 1}])

    def test_type_error_on_none(self):
        with pytest.raises(TypeError, match="Expected dict"):
            remove_excluded_fields(None)

    def test_excluded_fields_constant_is_frozen(self):
        assert isinstance(EXCLUDED_FIELDS, frozenset)
        assert "OBJECTID" in EXCLUDED_FIELDS
        assert "blueSkyNotificationSubscription" in EXCLUDED_FIELDS


# ---------------------------------------------------------------------------
# extract_geometry
# ---------------------------------------------------------------------------


class TestExtractGeometry:
    """Tests for extract_geometry()."""

    def test_extracts_x_and_y(self):
        feature = {"geometry": {"x": -13562755.99, "y": 4489124.14}}
        assert extract_geometry(feature) == (-13562755.99, 4489124.14)

    def test_missing_geometry_key(self):
        assert extract_geometry({}) == (None, None)

    def test_geometry_is_none(self):
        assert extract_geometry({"geometry": None}) == (None, None)

    def test_geometry_missing_x(self):
        feature = {"geometry": {"y": 100.0}}
        x, y = extract_geometry(feature)
        assert x is None
        assert y == 100.0

    def test_geometry_missing_y(self):
        feature = {"geometry": {"x": 200.0}}
        x, y = extract_geometry(feature)
        assert x == 200.0
        assert y is None

    def test_geometry_with_zero_values(self):
        feature = {"geometry": {"x": 0.0, "y": 0.0}}
        assert extract_geometry(feature) == (0.0, 0.0)

    def test_geometry_with_integer_values(self):
        feature = {"geometry": {"x": -100, "y": 50}}
        assert extract_geometry(feature) == (-100, 50)

    def test_ignores_extra_geometry_fields(self):
        feature = {"geometry": {"x": 1.0, "y": 2.0, "z": 3.0, "spatialReference": {}}}
        assert extract_geometry(feature) == (1.0, 2.0)


# ---------------------------------------------------------------------------
# flatten_feature
# ---------------------------------------------------------------------------


class TestFlattenFeature:
    """Tests for flatten_feature()."""

    def test_basic_flatten(self):
        feature = {
            "attributes": {
                "F_OUTAGE_ID": "42",
                "OBJECTID": 1,
                "blueSkyNotificationSubscription": "x",
                "CITY": "SF",
            },
            "geometry": {"x": -100.0, "y": 50.0},
        }
        result = flatten_feature(feature)
        assert result == {
            "F_OUTAGE_ID": "42",
            "CITY": "SF",
            "geometry_x": -100.0,
            "geometry_y": 50.0,
        }

    def test_excluded_fields_removed(self):
        feature = {
            "attributes": {
                "OBJECTID": 999,
                "blueSkyNotificationSubscription": "val",
                "CITY": "LA",
            },
            "geometry": {"x": 1.0, "y": 2.0},
        }
        result = flatten_feature(feature)
        assert "OBJECTID" not in result
        assert "blueSkyNotificationSubscription" not in result

    def test_geometry_promoted_to_top_level(self):
        feature = {
            "attributes": {"F_OUTAGE_ID": "1"},
            "geometry": {"x": -13562755.99, "y": 4489124.14},
        }
        result = flatten_feature(feature)
        assert result["geometry_x"] == -13562755.99
        assert result["geometry_y"] == 4489124.14

    def test_missing_geometry_produces_none(self):
        feature = {"attributes": {"F_OUTAGE_ID": "1"}}
        result = flatten_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_null_geometry_produces_none(self):
        feature = {"attributes": {"F_OUTAGE_ID": "1"}, "geometry": None}
        result = flatten_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_preserves_all_non_excluded_attributes(self):
        feature = {
            "attributes": {
                "F_OUTAGE_ID": "1",
                "CITY": "SF",
                "EST_CUSTOMERS": 100,
                "CREW_ETA": None,
                "OBJECTID": 5,
            },
            "geometry": {"x": 0.0, "y": 0.0},
        }
        result = flatten_feature(feature)
        assert result["F_OUTAGE_ID"] == "1"
        assert result["CITY"] == "SF"
        assert result["EST_CUSTOMERS"] == 100
        assert result["CREW_ETA"] is None

    def test_missing_attributes_raises_key_error(self):
        with pytest.raises(KeyError, match="attributes"):
            flatten_feature({"geometry": {"x": 1, "y": 2}})

    def test_non_dict_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            flatten_feature("not a feature")

    def test_list_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            flatten_feature([{"attributes": {}}])

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            flatten_feature(None)

    def test_empty_attributes(self):
        feature = {"attributes": {}, "geometry": {"x": 1.0, "y": 2.0}}
        result = flatten_feature(feature)
        assert result == {"geometry_x": 1.0, "geometry_y": 2.0}


# ---------------------------------------------------------------------------
# transform_api_response
# ---------------------------------------------------------------------------


class TestTransformApiResponse:
    """Tests for transform_api_response()."""

    def test_transforms_full_response(self, sample_api_response):
        result = transform_api_response(sample_api_response)
        assert len(result) == 2

        # First record
        assert result[0]["F_OUTAGE_ID"] == "100001"
        assert result[0]["CITY"] == "San Jose"
        assert result[0]["geometry_x"] == -13562755.9893
        assert result[0]["geometry_y"] == 4489124.143
        assert "OBJECTID" not in result[0]
        assert "blueSkyNotificationSubscription" not in result[0]

        # Second record
        assert result[1]["F_OUTAGE_ID"] == "100002"
        assert result[1]["CITY"] == "Sacramento"

    def test_empty_features_list(self):
        result = transform_api_response({"features": []})
        assert result == []

    def test_single_feature(self):
        raw = {
            "features": [
                {
                    "attributes": {"F_OUTAGE_ID": "1", "OBJECTID": 99},
                    "geometry": {"x": 10.0, "y": 20.0},
                }
            ]
        }
        result = transform_api_response(raw)
        assert len(result) == 1
        assert result[0]["F_OUTAGE_ID"] == "1"
        assert result[0]["geometry_x"] == 10.0
        assert "OBJECTID" not in result[0]

    def test_missing_features_key_raises(self):
        with pytest.raises(KeyError, match="features"):
            transform_api_response({"data": []})

    def test_non_dict_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            transform_api_response("not a dict")

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            transform_api_response(None)

    def test_features_not_a_list_raises(self):
        with pytest.raises(ValueError, match="Expected list"):
            transform_api_response({"features": "oops"})

    def test_features_is_dict_raises(self):
        with pytest.raises(ValueError, match="Expected list"):
            transform_api_response({"features": {"a": 1}})

    def test_extra_top_level_keys_ignored(self):
        """API responses may include metadata keys besides 'features'."""
        raw = {
            "features": [
                {
                    "attributes": {"F_OUTAGE_ID": "1"},
                    "geometry": {"x": 0, "y": 0},
                }
            ],
            "objectIdFieldName": "OBJECTID",
            "globalIdFieldName": "",
            "geometryType": "esriGeometryPoint",
        }
        result = transform_api_response(raw)
        assert len(result) == 1
        assert result[0]["F_OUTAGE_ID"] == "1"

    def test_malformed_feature_in_list_raises(self):
        raw = {
            "features": [
                {"attributes": {"F_OUTAGE_ID": "1"}, "geometry": None},
                "bad_feature",
            ]
        }
        with pytest.raises(TypeError, match="Expected dict"):
            transform_api_response(raw)

    def test_preserves_field_order(self):
        """Attributes should come first, then geometry_x, geometry_y."""
        raw = {
            "features": [
                {
                    "attributes": {"A": 1, "B": 2},
                    "geometry": {"x": 10, "y": 20},
                }
            ]
        }
        result = transform_api_response(raw)
        keys = list(result[0].keys())
        assert keys[-2:] == ["geometry_x", "geometry_y"]
