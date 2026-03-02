"""
Comprehensive unit tests for the PG&E outage data processor.

Tests cover:
- URL construction with cache-busting
- Single feature normalization (the jq transformation equivalent)
- Full API response transformation
- Outage record validation (required fields, types, ranges)
- Point vs. polygon feature filtering
- Outage statistics computation
- Record diffing (added, removed, changed)
- Edge cases: empty inputs, malformed data, null values, boundary conditions
"""

import pytest

from outage_processor import (
    BASE_URL,
    FIELDS_TO_STRIP,
    NULLABLE_FIELDS,
    NUMERIC_FIELDS,
    REQUIRED_FIELDS,
    build_fetch_url,
    compute_outage_stats,
    filter_point_features,
    normalize_feature,
    records_diff,
    transform_api_response,
    validate_outage_record,
)


# ---------------------------------------------------------------------------
# build_fetch_url
# ---------------------------------------------------------------------------
class TestBuildFetchUrl:
    """Tests for the URL construction utility."""

    def test_default_url_uses_base(self):
        url = build_fetch_url(cache_bust=False)
        assert url.startswith(BASE_URL)

    def test_default_url_contains_required_params(self):
        url = build_fetch_url(cache_bust=False)
        assert "where=1%3D1" in url
        assert "outFields=%2A" in url
        assert "f=pjson" in url

    def test_cache_bust_adds_unique_param(self):
        url = build_fetch_url(cache_bust=True)
        # The cache-busting param starts with '_'
        assert "_" in url.split("?")[1]

    def test_cache_bust_produces_different_urls(self):
        url1 = build_fetch_url(cache_bust=True)
        url2 = build_fetch_url(cache_bust=True)
        assert url1 != url2

    def test_no_cache_bust_produces_stable_url(self):
        url1 = build_fetch_url(cache_bust=False)
        url2 = build_fetch_url(cache_bust=False)
        assert url1 == url2

    def test_custom_base_url(self):
        custom = "https://example.com/api"
        url = build_fetch_url(base_url=custom, cache_bust=False)
        assert url.startswith(custom)

    def test_cache_bust_disabled(self):
        url = build_fetch_url(cache_bust=False)
        # Only the three standard params should be present
        query = url.split("?")[1]
        params = query.split("&")
        assert len(params) == 3


# ---------------------------------------------------------------------------
# normalize_feature
# ---------------------------------------------------------------------------
class TestNormalizeFeature:
    """Tests for single feature normalization (jq transformation equivalent)."""

    def test_strips_objectid(self, sample_raw_feature):
        result = normalize_feature(sample_raw_feature)
        assert "OBJECTID" not in result

    def test_strips_bluesky_notification(self, sample_raw_feature):
        result = normalize_feature(sample_raw_feature)
        assert "blueSkyNotificationSubscription" not in result

    def test_promotes_geometry_x(self, sample_raw_feature):
        result = normalize_feature(sample_raw_feature)
        assert result["geometry_x"] == -13562755.9893

    def test_promotes_geometry_y(self, sample_raw_feature):
        result = normalize_feature(sample_raw_feature)
        assert result["geometry_y"] == 4489124.143

    def test_preserves_all_non_stripped_attributes(self, sample_raw_feature):
        result = normalize_feature(sample_raw_feature)
        for key in sample_raw_feature["attributes"]:
            if key not in FIELDS_TO_STRIP:
                assert key in result
                assert result[key] == sample_raw_feature["attributes"][key]

    def test_result_is_flat_dict(self, sample_raw_feature):
        result = normalize_feature(sample_raw_feature)
        assert isinstance(result, dict)
        # No nested dicts (geometry, attributes should be flattened)
        for value in result.values():
            assert not isinstance(value, dict)

    def test_matches_expected_output(self, sample_raw_feature, sample_normalized_record):
        result = normalize_feature(sample_raw_feature)
        assert result == sample_normalized_record

    def test_missing_geometry_sets_none(self):
        feature = {
            "attributes": {"F_OUTAGE_ID": "123", "OUTAGE_EXTENT": "DEVICE"}
        }
        result = normalize_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_null_geometry_sets_none(self):
        feature = {
            "attributes": {"F_OUTAGE_ID": "123"},
            "geometry": None,
        }
        result = normalize_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_empty_geometry_sets_none(self):
        feature = {
            "attributes": {"F_OUTAGE_ID": "123"},
            "geometry": {},
        }
        result = normalize_feature(feature)
        assert result["geometry_x"] is None
        assert result["geometry_y"] is None

    def test_raises_on_missing_attributes(self):
        with pytest.raises(ValueError, match="missing required 'attributes' key"):
            normalize_feature({"geometry": {"x": 1, "y": 2}})

    def test_raises_on_non_dict_input(self):
        with pytest.raises(ValueError, match="Feature must be a dict"):
            normalize_feature("not a dict")

    def test_raises_on_list_input(self):
        with pytest.raises(ValueError, match="Feature must be a dict"):
            normalize_feature([1, 2, 3])

    def test_raises_on_none_input(self):
        with pytest.raises(ValueError, match="Feature must be a dict"):
            normalize_feature(None)

    def test_empty_attributes_dict(self):
        feature = {"attributes": {}, "geometry": {"x": 1.0, "y": 2.0}}
        result = normalize_feature(feature)
        assert result == {"geometry_x": 1.0, "geometry_y": 2.0}

    def test_only_stripped_fields_in_attributes(self):
        feature = {
            "attributes": {
                "OBJECTID": 42,
                "blueSkyNotificationSubscription": "val",
            },
            "geometry": {"x": 0.0, "y": 0.0},
        }
        result = normalize_feature(feature)
        assert result == {"geometry_x": 0.0, "geometry_y": 0.0}

    def test_preserves_null_attribute_values(self, sample_raw_feature):
        result = normalize_feature(sample_raw_feature)
        assert result["CREW_ETA"] is None
        assert result["COUNTY"] is None
        assert result["ZIP"] is None
        assert result["SPID"] is None

    def test_extra_attributes_preserved(self):
        feature = {
            "attributes": {
                "F_OUTAGE_ID": "123",
                "EXTRA_FIELD": "extra_value",
            },
            "geometry": {"x": 1.0, "y": 2.0},
        }
        result = normalize_feature(feature)
        assert result["EXTRA_FIELD"] == "extra_value"


# ---------------------------------------------------------------------------
# transform_api_response
# ---------------------------------------------------------------------------
class TestTransformApiResponse:
    """Tests for the full API response transformation pipeline."""

    def test_single_feature_response(self, sample_raw_response, sample_normalized_record):
        result = transform_api_response(sample_raw_response)
        assert len(result) == 1
        assert result[0] == sample_normalized_record

    def test_multi_feature_response(self, sample_multi_feature_response):
        result = transform_api_response(sample_multi_feature_response)
        assert len(result) == 3
        # Verify OBJECTID and blueSkyNotificationSubscription stripped from all
        for record in result:
            assert "OBJECTID" not in record
            assert "blueSkyNotificationSubscription" not in record
            assert "geometry_x" in record
            assert "geometry_y" in record

    def test_empty_features_list(self):
        result = transform_api_response({"features": []})
        assert result == []

    def test_raises_on_missing_features_key(self):
        with pytest.raises(ValueError, match="missing required 'features' key"):
            transform_api_response({"data": []})

    def test_raises_on_non_dict_response(self):
        with pytest.raises(ValueError, match="API response must be a dict"):
            transform_api_response("not a dict")

    def test_raises_on_list_response(self):
        with pytest.raises(ValueError, match="API response must be a dict"):
            transform_api_response([{"features": []}])

    def test_raises_on_none_response(self):
        with pytest.raises(ValueError, match="API response must be a dict"):
            transform_api_response(None)

    def test_raises_on_non_list_features(self):
        with pytest.raises(ValueError, match="'features' must be a list"):
            transform_api_response({"features": "not a list"})

    def test_preserves_feature_order(self, sample_multi_feature_response):
        result = transform_api_response(sample_multi_feature_response)
        ids = [r["F_OUTAGE_ID"] for r in result]
        assert ids == ["100001", "100002", "100003"]

    def test_each_result_is_flat(self, sample_multi_feature_response):
        result = transform_api_response(sample_multi_feature_response)
        for record in result:
            for value in record.values():
                assert not isinstance(value, dict)
                assert not isinstance(value, list)

    def test_propagates_normalize_error(self):
        """If a feature inside the list is malformed, the error propagates."""
        with pytest.raises(ValueError, match="missing required 'attributes' key"):
            transform_api_response({"features": [{"geometry": {"x": 1}}]})

    def test_response_with_extra_top_level_keys(self, sample_raw_feature):
        """Extra keys in the API response (e.g., 'exceededTransferLimit') are ignored."""
        response = {
            "features": [sample_raw_feature],
            "exceededTransferLimit": False,
            "objectIdFieldName": "OBJECTID",
        }
        result = transform_api_response(response)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# validate_outage_record
# ---------------------------------------------------------------------------
class TestValidateOutageRecord:
    """Tests for outage record validation."""

    def test_valid_record_passes(self, sample_normalized_record):
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is True
        assert errors == []

    def test_missing_single_required_field(self, sample_normalized_record):
        del sample_normalized_record["F_OUTAGE_ID"]
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("F_OUTAGE_ID" in e for e in errors)

    def test_missing_multiple_required_fields(self, sample_normalized_record):
        del sample_normalized_record["F_OUTAGE_ID"]
        del sample_normalized_record["OUTAGE_CAUSE"]
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("Missing required fields" in e for e in errors)

    def test_all_required_fields_defined(self):
        """Sanity check that REQUIRED_FIELDS is a non-empty set of strings."""
        assert len(REQUIRED_FIELDS) > 0
        for field in REQUIRED_FIELDS:
            assert isinstance(field, str)

    def test_empty_record_fails(self):
        is_valid, errors = validate_outage_record({})
        assert is_valid is False
        assert any("Missing required fields" in e for e in errors)

    def test_non_dict_record_fails(self):
        is_valid, errors = validate_outage_record("not a dict")
        assert is_valid is False
        assert any("must be a dict" in e for e in errors)

    def test_none_record_fails(self):
        is_valid, errors = validate_outage_record(None)
        assert is_valid is False

    def test_list_record_fails(self):
        is_valid, errors = validate_outage_record([])
        assert is_valid is False

    def test_numeric_field_with_string_value(self, sample_normalized_record):
        sample_normalized_record["EST_CUSTOMERS"] = "not_a_number"
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("EST_CUSTOMERS" in e and "numeric" in e for e in errors)

    def test_numeric_field_with_int_value(self, sample_normalized_record):
        sample_normalized_record["EST_CUSTOMERS"] = 100
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is True

    def test_numeric_field_with_float_value(self, sample_normalized_record):
        sample_normalized_record["EST_CUSTOMERS"] = 100.5
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is True

    def test_numeric_field_null_is_ok(self, sample_normalized_record):
        """Null numeric fields should not cause validation failure."""
        sample_normalized_record["AUTO_ETOR"] = None
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is True

    def test_empty_outage_id_fails(self, sample_normalized_record):
        sample_normalized_record["F_OUTAGE_ID"] = ""
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("F_OUTAGE_ID" in e for e in errors)

    def test_whitespace_only_outage_id_fails(self, sample_normalized_record):
        sample_normalized_record["F_OUTAGE_ID"] = "   "
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False

    def test_numeric_outage_id_fails(self, sample_normalized_record):
        sample_normalized_record["F_OUTAGE_ID"] = 12345
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("F_OUTAGE_ID" in e and "non-empty string" in e for e in errors)

    def test_latitude_out_of_range_high(self, sample_normalized_record):
        sample_normalized_record["OUTAGE_LATITUDE"] = 91.0
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("OUTAGE_LATITUDE" in e for e in errors)

    def test_latitude_out_of_range_low(self, sample_normalized_record):
        sample_normalized_record["OUTAGE_LATITUDE"] = -91.0
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False

    def test_longitude_out_of_range_high(self, sample_normalized_record):
        sample_normalized_record["OUTAGE_LONGITUDE"] = 181.0
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("OUTAGE_LONGITUDE" in e for e in errors)

    def test_longitude_out_of_range_low(self, sample_normalized_record):
        sample_normalized_record["OUTAGE_LONGITUDE"] = -181.0
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False

    def test_latitude_boundary_values(self, sample_normalized_record):
        for lat in (-90, 0, 90):
            sample_normalized_record["OUTAGE_LATITUDE"] = lat
            is_valid, _ = validate_outage_record(sample_normalized_record)
            assert is_valid is True, f"Latitude {lat} should be valid"

    def test_longitude_boundary_values(self, sample_normalized_record):
        for lon in (-180, 0, 180):
            sample_normalized_record["OUTAGE_LONGITUDE"] = lon
            is_valid, _ = validate_outage_record(sample_normalized_record)
            assert is_valid is True, f"Longitude {lon} should be valid"

    def test_negative_timestamp_fails(self, sample_normalized_record):
        sample_normalized_record["OUTAGE_START"] = -1
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("OUTAGE_START" in e and "positive" in e for e in errors)

    def test_zero_timestamp_fails(self, sample_normalized_record):
        sample_normalized_record["LAST_UPDATE"] = 0
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("LAST_UPDATE" in e for e in errors)

    def test_negative_customers_fails(self, sample_normalized_record):
        sample_normalized_record["EST_CUSTOMERS"] = -5
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert any("EST_CUSTOMERS" in e for e in errors)

    def test_zero_customers_is_valid(self, sample_normalized_record):
        sample_normalized_record["EST_CUSTOMERS"] = 0
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is True

    def test_multiple_errors_collected(self, sample_normalized_record):
        sample_normalized_record["F_OUTAGE_ID"] = ""
        sample_normalized_record["OUTAGE_LATITUDE"] = 999
        sample_normalized_record["EST_CUSTOMERS"] = "bad"
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is False
        assert len(errors) >= 3

    def test_nullable_fields_can_be_null(self, sample_normalized_record):
        for field in NULLABLE_FIELDS:
            if field in sample_normalized_record:
                sample_normalized_record[field] = None
        is_valid, errors = validate_outage_record(sample_normalized_record)
        assert is_valid is True


# ---------------------------------------------------------------------------
# filter_point_features
# ---------------------------------------------------------------------------
class TestFilterPointFeatures:
    """Tests for point vs. polygon feature filtering."""

    def test_keeps_point_features(self, sample_point_feature):
        result = filter_point_features([sample_point_feature])
        assert len(result) == 1
        assert result[0] is sample_point_feature

    def test_removes_polygon_features(self, sample_polygon_feature):
        result = filter_point_features([sample_polygon_feature])
        assert len(result) == 0

    def test_mixed_features(self, sample_point_feature, sample_polygon_feature):
        features = [sample_point_feature, sample_polygon_feature]
        result = filter_point_features(features)
        assert len(result) == 1
        assert result[0]["attributes"]["F_OUTAGE_ID"] == "100001"

    def test_empty_list(self):
        result = filter_point_features([])
        assert result == []

    def test_no_geometry_excluded(self):
        feature = {"attributes": {"F_OUTAGE_ID": "999"}}
        result = filter_point_features([feature])
        assert len(result) == 0

    def test_null_geometry_excluded(self):
        feature = {"attributes": {"F_OUTAGE_ID": "999"}, "geometry": None}
        result = filter_point_features([feature])
        assert len(result) == 0

    def test_geometry_with_only_x_excluded(self):
        feature = {"attributes": {}, "geometry": {"x": 1.0}}
        result = filter_point_features([feature])
        assert len(result) == 0

    def test_geometry_with_only_y_excluded(self):
        feature = {"attributes": {}, "geometry": {"y": 1.0}}
        result = filter_point_features([feature])
        assert len(result) == 0

    def test_geometry_with_x_y_and_rings_excluded(self):
        """A feature with both point coords and rings is ambiguous; exclude it."""
        feature = {
            "attributes": {},
            "geometry": {"x": 1.0, "y": 2.0, "rings": [[]]},
        }
        result = filter_point_features([feature])
        assert len(result) == 0

    def test_multiple_point_features(self):
        features = [
            {"attributes": {"id": "1"}, "geometry": {"x": 1.0, "y": 2.0}},
            {"attributes": {"id": "2"}, "geometry": {"x": 3.0, "y": 4.0}},
            {"attributes": {"id": "3"}, "geometry": {"x": 5.0, "y": 6.0}},
        ]
        result = filter_point_features(features)
        assert len(result) == 3

    def test_preserves_order(self):
        features = [
            {"attributes": {"id": "A"}, "geometry": {"x": 1.0, "y": 2.0}},
            {"attributes": {"id": "B"}, "geometry": {"rings": [[]]}},
            {"attributes": {"id": "C"}, "geometry": {"x": 3.0, "y": 4.0}},
        ]
        result = filter_point_features(features)
        ids = [f["attributes"]["id"] for f in result]
        assert ids == ["A", "C"]


# ---------------------------------------------------------------------------
# compute_outage_stats
# ---------------------------------------------------------------------------
class TestComputeOutageStats:
    """Tests for outage statistics computation."""

    def test_empty_records(self):
        stats = compute_outage_stats([])
        assert stats["total_outages"] == 0
        assert stats["total_customers_affected"] == 0
        assert stats["outages_by_cause"] == {}
        assert stats["outages_by_city"] == {}
        assert stats["outages_by_crew_status"] == {}

    def test_single_record(self, sample_normalized_record):
        stats = compute_outage_stats([sample_normalized_record])
        assert stats["total_outages"] == 1
        assert stats["total_customers_affected"] == 68
        assert stats["outages_by_cause"] == {"PLNND SHUTDOWN": 1}
        assert stats["outages_by_city"] == {"San Jose": 1}
        assert stats["outages_by_crew_status"] == {"Crew On Site": 1}

    def test_multiple_records(self, sample_multi_feature_response):
        records = transform_api_response(sample_multi_feature_response)
        stats = compute_outage_stats(records)
        assert stats["total_outages"] == 3
        assert stats["total_customers_affected"] == 200  # 50 + 120 + 30
        assert stats["outages_by_cause"] == {"PLNND SHUTDOWN": 2, "EQUIP FAIL": 1}
        assert stats["outages_by_city"] == {
            "San Jose": 1,
            "Sacramento": 1,
            "San Francisco": 1,
        }
        assert stats["outages_by_crew_status"] == {
            "Crew On Site": 1,
            "Crew En Route": 1,
            "Assigned": 1,
        }

    def test_null_customers_ignored(self):
        records = [
            {"F_OUTAGE_ID": "1", "EST_CUSTOMERS": None, "OUTAGE_CAUSE": "X", "CITY": "Y", "CREW_CURRENT_STATUS": "Z"},
            {"F_OUTAGE_ID": "2", "EST_CUSTOMERS": 10, "OUTAGE_CAUSE": "X", "CITY": "Y", "CREW_CURRENT_STATUS": "Z"},
        ]
        stats = compute_outage_stats(records)
        assert stats["total_customers_affected"] == 10

    def test_missing_cause_defaults_to_unknown(self):
        records = [{"F_OUTAGE_ID": "1", "EST_CUSTOMERS": 5, "CITY": "A", "CREW_CURRENT_STATUS": "B"}]
        stats = compute_outage_stats(records)
        assert stats["outages_by_cause"] == {"UNKNOWN": 1}

    def test_missing_city_defaults_to_unknown(self):
        records = [{"F_OUTAGE_ID": "1", "EST_CUSTOMERS": 5, "OUTAGE_CAUSE": "X", "CREW_CURRENT_STATUS": "B"}]
        stats = compute_outage_stats(records)
        assert stats["outages_by_city"] == {"UNKNOWN": 1}

    def test_missing_crew_status_defaults_to_unknown(self):
        records = [{"F_OUTAGE_ID": "1", "EST_CUSTOMERS": 5, "OUTAGE_CAUSE": "X", "CITY": "A"}]
        stats = compute_outage_stats(records)
        assert stats["outages_by_crew_status"] == {"UNKNOWN": 1}

    def test_non_numeric_customers_ignored(self):
        records = [
            {"F_OUTAGE_ID": "1", "EST_CUSTOMERS": "bad", "OUTAGE_CAUSE": "X", "CITY": "Y", "CREW_CURRENT_STATUS": "Z"},
        ]
        stats = compute_outage_stats(records)
        assert stats["total_customers_affected"] == 0

    def test_counts_are_correct_with_duplicates(self):
        records = [
            {"OUTAGE_CAUSE": "A", "CITY": "X", "CREW_CURRENT_STATUS": "S1", "EST_CUSTOMERS": 10},
            {"OUTAGE_CAUSE": "A", "CITY": "X", "CREW_CURRENT_STATUS": "S1", "EST_CUSTOMERS": 20},
            {"OUTAGE_CAUSE": "B", "CITY": "X", "CREW_CURRENT_STATUS": "S2", "EST_CUSTOMERS": 30},
        ]
        stats = compute_outage_stats(records)
        assert stats["total_outages"] == 3
        assert stats["total_customers_affected"] == 60
        assert stats["outages_by_cause"] == {"A": 2, "B": 1}
        assert stats["outages_by_city"] == {"X": 3}
        assert stats["outages_by_crew_status"] == {"S1": 2, "S2": 1}


# ---------------------------------------------------------------------------
# records_diff
# ---------------------------------------------------------------------------
class TestRecordsDiff:
    """Tests for the record diffing logic."""

    def test_no_changes(self):
        records = [
            {"F_OUTAGE_ID": "1", "status": "active"},
            {"F_OUTAGE_ID": "2", "status": "active"},
        ]
        diff = records_diff(records, records)
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["changed"] == []

    def test_added_record(self):
        old = [{"F_OUTAGE_ID": "1", "status": "active"}]
        new = [
            {"F_OUTAGE_ID": "1", "status": "active"},
            {"F_OUTAGE_ID": "2", "status": "new"},
        ]
        diff = records_diff(old, new)
        assert len(diff["added"]) == 1
        assert diff["added"][0]["F_OUTAGE_ID"] == "2"
        assert diff["removed"] == []
        assert diff["changed"] == []

    def test_removed_record(self):
        old = [
            {"F_OUTAGE_ID": "1", "status": "active"},
            {"F_OUTAGE_ID": "2", "status": "active"},
        ]
        new = [{"F_OUTAGE_ID": "1", "status": "active"}]
        diff = records_diff(old, new)
        assert diff["added"] == []
        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["F_OUTAGE_ID"] == "2"
        assert diff["changed"] == []

    def test_changed_record(self):
        old = [{"F_OUTAGE_ID": "1", "status": "active", "customers": 50}]
        new = [{"F_OUTAGE_ID": "1", "status": "restored", "customers": 50}]
        diff = records_diff(old, new)
        assert diff["added"] == []
        assert diff["removed"] == []
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["key"] == "1"
        assert diff["changed"][0]["changes"]["status"] == {
            "old": "active",
            "new": "restored",
        }

    def test_multiple_field_changes(self):
        old = [{"F_OUTAGE_ID": "1", "status": "active", "customers": 50, "crew": "En Route"}]
        new = [{"F_OUTAGE_ID": "1", "status": "restored", "customers": 0, "crew": "Complete"}]
        diff = records_diff(old, new)
        changes = diff["changed"][0]["changes"]
        assert "status" in changes
        assert "customers" in changes
        assert "crew" in changes

    def test_added_and_removed_simultaneously(self):
        old = [{"F_OUTAGE_ID": "1", "val": "a"}]
        new = [{"F_OUTAGE_ID": "2", "val": "b"}]
        diff = records_diff(old, new)
        assert len(diff["added"]) == 1
        assert len(diff["removed"]) == 1
        assert diff["added"][0]["F_OUTAGE_ID"] == "2"
        assert diff["removed"][0]["F_OUTAGE_ID"] == "1"

    def test_all_operations(self):
        old = [
            {"F_OUTAGE_ID": "1", "val": "unchanged"},
            {"F_OUTAGE_ID": "2", "val": "will_change"},
            {"F_OUTAGE_ID": "3", "val": "will_remove"},
        ]
        new = [
            {"F_OUTAGE_ID": "1", "val": "unchanged"},
            {"F_OUTAGE_ID": "2", "val": "changed"},
            {"F_OUTAGE_ID": "4", "val": "new_record"},
        ]
        diff = records_diff(old, new)
        assert len(diff["added"]) == 1
        assert diff["added"][0]["F_OUTAGE_ID"] == "4"
        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["F_OUTAGE_ID"] == "3"
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["key"] == "2"

    def test_empty_old_records(self):
        new = [{"F_OUTAGE_ID": "1", "val": "a"}]
        diff = records_diff([], new)
        assert len(diff["added"]) == 1
        assert diff["removed"] == []

    def test_empty_new_records(self):
        old = [{"F_OUTAGE_ID": "1", "val": "a"}]
        diff = records_diff(old, [])
        assert diff["added"] == []
        assert len(diff["removed"]) == 1

    def test_both_empty(self):
        diff = records_diff([], [])
        assert diff == {"added": [], "removed": [], "changed": []}

    def test_custom_key_field(self):
        old = [{"id": "A", "val": 1}]
        new = [{"id": "A", "val": 2}]
        diff = records_diff(old, new, key_field="id")
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["key"] == "A"

    def test_missing_key_field_in_old_raises(self):
        old = [{"name": "oops"}]
        new = [{"F_OUTAGE_ID": "1"}]
        with pytest.raises(ValueError, match="missing key field"):
            records_diff(old, new)

    def test_missing_key_field_in_new_raises(self):
        old = [{"F_OUTAGE_ID": "1"}]
        new = [{"name": "oops"}]
        with pytest.raises(ValueError, match="missing key field"):
            records_diff(old, new)

    def test_change_null_to_value(self):
        old = [{"F_OUTAGE_ID": "1", "CREW_ETA": None}]
        new = [{"F_OUTAGE_ID": "1", "CREW_ETA": 1772490000000}]
        diff = records_diff(old, new)
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["changes"]["CREW_ETA"] == {
            "old": None,
            "new": 1772490000000,
        }

    def test_change_value_to_null(self):
        old = [{"F_OUTAGE_ID": "1", "CREW_ETA": 1772490000000}]
        new = [{"F_OUTAGE_ID": "1", "CREW_ETA": None}]
        diff = records_diff(old, new)
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["changes"]["CREW_ETA"] == {
            "old": 1772490000000,
            "new": None,
        }

    def test_new_field_added_to_record(self):
        old = [{"F_OUTAGE_ID": "1", "a": 1}]
        new = [{"F_OUTAGE_ID": "1", "a": 1, "b": 2}]
        diff = records_diff(old, new)
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["changes"]["b"] == {"old": None, "new": 2}

    def test_field_removed_from_record(self):
        old = [{"F_OUTAGE_ID": "1", "a": 1, "b": 2}]
        new = [{"F_OUTAGE_ID": "1", "a": 1}]
        diff = records_diff(old, new)
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["changes"]["b"] == {"old": 2, "new": None}

    def test_results_sorted_by_key(self):
        old = [
            {"F_OUTAGE_ID": "3", "val": "x"},
            {"F_OUTAGE_ID": "1", "val": "x"},
        ]
        new = [
            {"F_OUTAGE_ID": "2", "val": "y"},
            {"F_OUTAGE_ID": "4", "val": "y"},
        ]
        diff = records_diff(old, new)
        added_ids = [r["F_OUTAGE_ID"] for r in diff["added"]]
        removed_ids = [r["F_OUTAGE_ID"] for r in diff["removed"]]
        assert added_ids == ["2", "4"]
        assert removed_ids == ["1", "3"]


# ---------------------------------------------------------------------------
# Integration-style tests: transform → validate pipeline
# ---------------------------------------------------------------------------
class TestTransformAndValidatePipeline:
    """Tests that verify the full transform → validate pipeline works end-to-end."""

    def test_transformed_records_pass_validation(self, sample_raw_response):
        records = transform_api_response(sample_raw_response)
        for record in records:
            is_valid, errors = validate_outage_record(record)
            assert is_valid is True, f"Validation failed: {errors}"

    def test_multi_feature_all_pass_validation(self, sample_multi_feature_response):
        records = transform_api_response(sample_multi_feature_response)
        assert len(records) == 3
        for record in records:
            is_valid, errors = validate_outage_record(record)
            assert is_valid is True, f"Record {record.get('F_OUTAGE_ID')} failed: {errors}"

    def test_transform_diff_pipeline(self, sample_multi_feature_response):
        """Simulate a snapshot-to-snapshot diff using transformed records."""
        records_v1 = transform_api_response(sample_multi_feature_response)

        # Simulate a second snapshot where one outage is resolved and one new appears
        v2_response = {
            "features": sample_multi_feature_response["features"][:2]
            + [
                {
                    "attributes": {
                        "OBJECTID": 4,
                        "blueSkyNotificationSubscription": "w",
                        "F_OUTAGE_ID": "100004",
                        "OUTAGE_EXTENT": "DEVICE",
                        "OUTAGE_DEVICE_ID": "dev-004",
                        "OUTAGE_CIRCUIT_ID": 4004,
                        "CREW_ETA": None,
                        "CREW_CURRENT_STATUS": "Crew On Site",
                        "OUTAGE_CAUSE": "WEATHER",
                        "EST_CUSTOMERS": 200,
                        "OUTAGE_LATITUDE": 37.9,
                        "OUTAGE_LONGITUDE": -122.3,
                        "CITY": "Oakland",
                        "COUNTY": "Alameda",
                        "ZIP": "94612",
                        "DEVICE_COUNT": 0,
                        "OUTAGE_START": 1772485000000,
                        "OUTAGE_START_TEXT": "2026-03-02T20:56:40Z",
                        "LAST_UPDATE": 1772486000000,
                        "LAST_UPDATE_TEXT": "2026-03-02T21:13:20Z",
                        "CURRENT_ETOR": 1772500000000,
                        "CURRENT_ETOR_TEXT": "2026-03-03T01:06:40Z",
                        "AUTO_ETOR": 1772500000000,
                        "SPID": None,
                        "fts_flag": "N",
                    },
                    "geometry": {"x": -13620000.0, "y": 4540000.0},
                }
            ]
        }
        records_v2 = transform_api_response(v2_response)

        diff = records_diff(records_v1, records_v2)
        assert len(diff["added"]) == 1
        assert diff["added"][0]["F_OUTAGE_ID"] == "100004"
        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["F_OUTAGE_ID"] == "100003"


# ---------------------------------------------------------------------------
# Constants verification tests
# ---------------------------------------------------------------------------
class TestConstants:
    """Tests that verify the module constants are correctly defined."""

    def test_fields_to_strip_contains_objectid(self):
        assert "OBJECTID" in FIELDS_TO_STRIP

    def test_fields_to_strip_contains_bluesky(self):
        assert "blueSkyNotificationSubscription" in FIELDS_TO_STRIP

    def test_fields_to_strip_count(self):
        assert len(FIELDS_TO_STRIP) == 2

    def test_required_fields_includes_outage_id(self):
        assert "F_OUTAGE_ID" in REQUIRED_FIELDS

    def test_numeric_fields_includes_est_customers(self):
        assert "EST_CUSTOMERS" in NUMERIC_FIELDS

    def test_numeric_fields_includes_coordinates(self):
        assert "OUTAGE_LATITUDE" in NUMERIC_FIELDS
        assert "OUTAGE_LONGITUDE" in NUMERIC_FIELDS
        assert "geometry_x" in NUMERIC_FIELDS
        assert "geometry_y" in NUMERIC_FIELDS

    def test_nullable_fields_are_subset_of_known_fields(self):
        """All nullable fields should be fields we know about."""
        all_known = REQUIRED_FIELDS | NUMERIC_FIELDS | NULLABLE_FIELDS | {
            "CITY", "CREW_ETA", "fts_flag", "geometry_x", "geometry_y",
            "OUTAGE_DEVICE_ID", "OUTAGE_EXTENT", "DEVICE_COUNT",
        }
        for field in NULLABLE_FIELDS:
            assert isinstance(field, str)
