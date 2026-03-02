"""Tests for the data transformation module."""

import pytest

from pge_outages.transform import (
    EXCLUDED_FIELDS,
    build_fetch_url,
    extract_features,
    flatten_feature,
    transform_api_response,
)


class TestExtractFeatures:
    """Tests for extract_features()."""

    def test_extracts_features_from_valid_response(self, sample_api_response):
        features = extract_features(sample_api_response)
        assert isinstance(features, list)
        assert len(features) == 2

    def test_raises_on_missing_features_key(self):
        with pytest.raises(ValueError, match="missing 'features' key"):
            extract_features({"error": "no data"})

    def test_raises_on_non_list_features(self):
        with pytest.raises(ValueError, match="Expected 'features' to be a list"):
            extract_features({"features": "not a list"})

    def test_empty_features_array(self):
        result = extract_features({"features": []})
        assert result == []

    def test_error_message_includes_available_keys(self):
        with pytest.raises(ValueError, match="Available keys.*error"):
            extract_features({"error": "bad"})

    def test_preserves_feature_structure(self, sample_api_response):
        features = extract_features(sample_api_response)
        assert "attributes" in features[0]
        assert "geometry" in features[0]


class TestFlattenFeature:
    """Tests for flatten_feature()."""

    def test_flattens_basic_feature(self, sample_api_response):
        feature = sample_api_response["features"][0]
        result = flatten_feature(feature)

        # Check that attributes are promoted to top level
        assert result["F_OUTAGE_ID"] == "187779"
        assert result["CITY"] == "San Jose"
        assert result["EST_CUSTOMERS"] == 68

    def test_removes_excluded_fields(self, sample_api_response):
        feature = sample_api_response["features"][0]
        result = flatten_feature(feature)

        for field in EXCLUDED_FIELDS:
            assert field not in result

    def test_objectid_removed(self, sample_api_response):
        feature = sample_api_response["features"][0]
        assert "OBJECTID" in feature["attributes"]
        result = flatten_feature(feature)
        assert "OBJECTID" not in result

    def test_bluesky_removed(self, sample_api_response):
        feature = sample_api_response["features"][0]
        assert "blueSkyNotificationSubscription" in feature["attributes"]
        result = flatten_feature(feature)
        assert "blueSkyNotificationSubscription" not in result

    def test_promotes_geometry_coordinates(self, sample_api_response):
        feature = sample_api_response["features"][0]
        result = flatten_feature(feature)

        assert result["geometry_x"] == -13562755.9893
        assert result["geometry_y"] == 4489124.143

    def test_handles_missing_geometry(self):
        feature = {
            "attributes": {"F_OUTAGE_ID": "100", "CITY": "Oakland"},
        }
        result = flatten_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_handles_null_geometry(self):
        feature = {
            "attributes": {"F_OUTAGE_ID": "100"},
            "geometry": None,
        }
        result = flatten_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_handles_empty_geometry(self):
        feature = {
            "attributes": {"F_OUTAGE_ID": "100"},
            "geometry": {},
        }
        result = flatten_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_raises_on_missing_attributes(self):
        with pytest.raises(ValueError, match="missing 'attributes' key"):
            flatten_feature({"geometry": {"x": 1, "y": 2}})

    def test_raises_on_non_dict_attributes(self):
        with pytest.raises(ValueError, match="Expected 'attributes' to be a dict"):
            flatten_feature({"attributes": "string"})

    def test_preserves_null_values(self, sample_api_response):
        feature = sample_api_response["features"][0]
        result = flatten_feature(feature)
        assert result["CREW_ETA"] is None
        assert result["COUNTY"] is None

    def test_preserves_all_non_excluded_attributes(self, sample_api_response):
        feature = sample_api_response["features"][0]
        result = flatten_feature(feature)
        expected_attrs = {
            k for k in feature["attributes"] if k not in EXCLUDED_FIELDS
        }
        for attr in expected_attrs:
            assert attr in result, f"Missing attribute: {attr}"

    def test_only_adds_geometry_x_and_y(self, sample_api_response):
        feature = sample_api_response["features"][0]
        attrs = {k for k in feature["attributes"] if k not in EXCLUDED_FIELDS}
        result = flatten_feature(feature)
        extra_keys = set(result.keys()) - attrs
        assert extra_keys == {"geometry_x", "geometry_y"}

    def test_feature_with_extra_geometry_fields(self):
        """Only x and y should be extracted from geometry, ignoring others."""
        feature = {
            "attributes": {"F_OUTAGE_ID": "100"},
            "geometry": {"x": 1.0, "y": 2.0, "z": 3.0, "spatialReference": {}},
        }
        result = flatten_feature(feature)
        assert result["geometry_x"] == 1.0
        assert result["geometry_y"] == 2.0
        assert "z" not in result
        assert "spatialReference" not in result


class TestTransformApiResponse:
    """Tests for transform_api_response()."""

    def test_transforms_full_response(self, sample_api_response):
        result = transform_api_response(sample_api_response)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_all_records_are_flat(self, sample_api_response):
        result = transform_api_response(sample_api_response)
        for record in result:
            # No nested dicts except for None values
            for value in record.values():
                assert not isinstance(value, dict)

    def test_no_excluded_fields_in_any_record(self, sample_api_response):
        result = transform_api_response(sample_api_response)
        for record in result:
            for field in EXCLUDED_FIELDS:
                assert field not in record

    def test_all_records_have_geometry_fields(self, sample_api_response):
        result = transform_api_response(sample_api_response)
        for record in result:
            assert "geometry_x" in record
            assert "geometry_y" in record

    def test_empty_features_returns_empty_list(self):
        result = transform_api_response({"features": []})
        assert result == []

    def test_single_feature(self):
        response = {
            "features": [
                {
                    "attributes": {
                        "F_OUTAGE_ID": "999",
                        "OBJECTID": 99,
                        "CITY": "Berkeley",
                    },
                    "geometry": {"x": -122.0, "y": 37.8},
                }
            ]
        }
        result = transform_api_response(response)
        assert len(result) == 1
        assert result[0]["F_OUTAGE_ID"] == "999"
        assert result[0]["CITY"] == "Berkeley"
        assert "OBJECTID" not in result[0]

    def test_preserves_record_order(self, sample_api_response):
        result = transform_api_response(sample_api_response)
        assert result[0]["F_OUTAGE_ID"] == "187779"
        assert result[1]["F_OUTAGE_ID"] == "187780"

    def test_raises_on_invalid_response(self):
        with pytest.raises(ValueError):
            transform_api_response({"error": "something went wrong"})


class TestBuildFetchUrl:
    """Tests for build_fetch_url()."""

    def test_contains_base_url(self):
        url = build_fetch_url("test-uuid")
        assert "ags.pge.esriemcs.com" in url
        assert "MapServer/5/query" in url

    def test_contains_required_params(self):
        url = build_fetch_url("test-uuid")
        assert "where=1%3D1" in url
        assert "outFields=*" in url
        assert "f=pjson" in url

    def test_contains_cache_busting_uuid(self):
        url = build_fetch_url("my-unique-id")
        assert "_my-unique-id" in url

    def test_different_uuids_produce_different_urls(self):
        url1 = build_fetch_url("uuid-1")
        url2 = build_fetch_url("uuid-2")
        assert url1 != url2

    def test_url_is_well_formed(self):
        url = build_fetch_url("test")
        assert url.startswith("https://")
        assert "?" in url
        assert "&" in url

    def test_empty_uuid(self):
        url = build_fetch_url("")
        assert url.endswith("&_")
