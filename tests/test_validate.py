"""Tests for the validation module."""

import pytest

from pge_outages.validate import (
    EXCLUDED_FIELDS,
    NULLABLE_FIELDS,
    NUMERIC_FIELDS,
    REQUIRED_FIELDS,
    ValidationError,
    validate_coordinate_ranges,
    validate_customer_count,
    validate_no_excluded_fields,
    validate_numeric_fields,
    validate_outages,
    validate_record,
    validate_required_fields,
    validate_timestamps,
    validate_unique_ids,
)


class TestValidationError:
    """Tests for the ValidationError class."""

    def test_creation(self):
        err = ValidationError("CITY", "Missing required field", "12345")
        assert err.field == "CITY"
        assert err.message == "Missing required field"
        assert err.record_id == "12345"

    def test_creation_without_record_id(self):
        err = ValidationError("CITY", "Missing")
        assert err.record_id is None

    def test_repr_with_record_id(self):
        err = ValidationError("CITY", "Missing", "12345")
        assert "[12345]" in repr(err)
        assert "CITY" in repr(err)

    def test_repr_without_record_id(self):
        err = ValidationError("CITY", "Missing")
        assert "[" not in repr(err)

    def test_equality(self):
        err1 = ValidationError("CITY", "Missing", "12345")
        err2 = ValidationError("CITY", "Missing", "12345")
        assert err1 == err2

    def test_inequality_different_field(self):
        err1 = ValidationError("CITY", "Missing", "12345")
        err2 = ValidationError("ZIP", "Missing", "12345")
        assert err1 != err2

    def test_inequality_different_message(self):
        err1 = ValidationError("CITY", "Missing", "12345")
        err2 = ValidationError("CITY", "Invalid", "12345")
        assert err1 != err2

    def test_inequality_different_record_id(self):
        err1 = ValidationError("CITY", "Missing", "12345")
        err2 = ValidationError("CITY", "Missing", "99999")
        assert err1 != err2

    def test_equality_with_non_validation_error(self):
        err = ValidationError("CITY", "Missing")
        assert err != "not a ValidationError"
        assert err.__eq__("not a ValidationError") is NotImplemented


class TestValidateRequiredFields:
    """Tests for validate_required_fields()."""

    def test_valid_record_has_no_errors(self, sample_flat_record):
        errors = validate_required_fields(sample_flat_record)
        assert errors == []

    def test_missing_single_field(self, sample_flat_record):
        del sample_flat_record["CITY"]
        errors = validate_required_fields(sample_flat_record)
        assert len(errors) == 1
        assert errors[0].field == "CITY"
        assert "Missing required field" in errors[0].message

    def test_missing_multiple_fields(self, sample_flat_record):
        del sample_flat_record["CITY"]
        del sample_flat_record["EST_CUSTOMERS"]
        errors = validate_required_fields(sample_flat_record)
        assert len(errors) == 2
        fields = {e.field for e in errors}
        assert "CITY" in fields
        assert "EST_CUSTOMERS" in fields

    def test_empty_record(self):
        errors = validate_required_fields({})
        assert len(errors) == len(REQUIRED_FIELDS)

    def test_error_includes_record_id(self, sample_flat_record):
        del sample_flat_record["CITY"]
        errors = validate_required_fields(sample_flat_record)
        assert errors[0].record_id == "187779"

    def test_missing_record_id_field(self):
        record = {"CITY": "Test"}
        errors = validate_required_fields(record)
        # Should still report errors, record_id will be None
        assert len(errors) > 0
        missing_id_errors = [e for e in errors if e.field == "F_OUTAGE_ID"]
        assert len(missing_id_errors) == 1

    def test_all_required_fields_checked(self):
        """Ensure every field in REQUIRED_FIELDS triggers an error when absent."""
        for field in REQUIRED_FIELDS:
            record = {f: "value" for f in REQUIRED_FIELDS if f != field}
            errors = validate_required_fields(record)
            error_fields = {e.field for e in errors}
            assert field in error_fields, f"Field {field} not flagged when missing"


class TestValidateNoExcludedFields:
    """Tests for validate_no_excluded_fields()."""

    def test_clean_record_has_no_errors(self, sample_flat_record):
        errors = validate_no_excluded_fields(sample_flat_record)
        assert errors == []

    def test_objectid_present(self, sample_flat_record):
        sample_flat_record["OBJECTID"] = 42
        errors = validate_no_excluded_fields(sample_flat_record)
        assert len(errors) == 1
        assert errors[0].field == "OBJECTID"

    def test_bluesky_present(self, sample_flat_record):
        sample_flat_record["blueSkyNotificationSubscription"] = "test"
        errors = validate_no_excluded_fields(sample_flat_record)
        assert len(errors) == 1
        assert errors[0].field == "blueSkyNotificationSubscription"

    def test_both_excluded_present(self, sample_flat_record):
        sample_flat_record["OBJECTID"] = 42
        sample_flat_record["blueSkyNotificationSubscription"] = "test"
        errors = validate_no_excluded_fields(sample_flat_record)
        assert len(errors) == 2

    def test_error_message_mentions_transformation(self, sample_flat_record):
        sample_flat_record["OBJECTID"] = 1
        errors = validate_no_excluded_fields(sample_flat_record)
        assert "removed during transformation" in errors[0].message


class TestValidateNumericFields:
    """Tests for validate_numeric_fields()."""

    def test_valid_numeric_fields(self, sample_flat_record):
        errors = validate_numeric_fields(sample_flat_record)
        assert errors == []

    def test_string_in_numeric_field(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = "sixty-eight"
        errors = validate_numeric_fields(sample_flat_record)
        assert len(errors) == 1
        assert errors[0].field == "EST_CUSTOMERS"
        assert "Expected numeric type" in errors[0].message

    def test_nullable_field_with_none(self, sample_flat_record):
        sample_flat_record["geometry_x"] = None
        errors = validate_numeric_fields(sample_flat_record)
        assert errors == []

    def test_non_nullable_field_with_none(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = None
        errors = validate_numeric_fields(sample_flat_record)
        assert len(errors) == 1
        assert "Non-nullable numeric field is null" in errors[0].message

    def test_int_and_float_both_valid(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = 100
        sample_flat_record["OUTAGE_LATITUDE"] = 37.5
        errors = validate_numeric_fields(sample_flat_record)
        assert errors == []

    def test_missing_numeric_field_no_error(self):
        """Missing fields are handled by validate_required_fields, not here."""
        record = {"F_OUTAGE_ID": "123"}
        errors = validate_numeric_fields(record)
        assert errors == []

    def test_boolean_in_numeric_field(self, sample_flat_record):
        # In Python, bool is a subclass of int, so True/False are technically int
        # This test documents the behavior
        sample_flat_record["EST_CUSTOMERS"] = True
        errors = validate_numeric_fields(sample_flat_record)
        # bool isinstance(True, int) is True in Python, so no error
        assert errors == []


class TestValidateCoordinateRanges:
    """Tests for validate_coordinate_ranges()."""

    def test_valid_california_coordinates(self, sample_flat_record):
        errors = validate_coordinate_ranges(sample_flat_record)
        assert errors == []

    def test_latitude_too_low(self, sample_flat_record):
        sample_flat_record["OUTAGE_LATITUDE"] = 20.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert len(errors) == 1
        assert errors[0].field == "OUTAGE_LATITUDE"
        assert "outside California range" in errors[0].message

    def test_latitude_too_high(self, sample_flat_record):
        sample_flat_record["OUTAGE_LATITUDE"] = 50.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert len(errors) == 1

    def test_longitude_too_low(self, sample_flat_record):
        sample_flat_record["OUTAGE_LONGITUDE"] = -130.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert len(errors) == 1
        assert errors[0].field == "OUTAGE_LONGITUDE"

    def test_longitude_too_high(self, sample_flat_record):
        sample_flat_record["OUTAGE_LONGITUDE"] = -100.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert len(errors) == 1

    def test_boundary_latitude_lower(self, sample_flat_record):
        sample_flat_record["OUTAGE_LATITUDE"] = 32.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert errors == []

    def test_boundary_latitude_upper(self, sample_flat_record):
        sample_flat_record["OUTAGE_LATITUDE"] = 42.5
        errors = validate_coordinate_ranges(sample_flat_record)
        assert errors == []

    def test_boundary_longitude_lower(self, sample_flat_record):
        sample_flat_record["OUTAGE_LONGITUDE"] = -125.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert errors == []

    def test_boundary_longitude_upper(self, sample_flat_record):
        sample_flat_record["OUTAGE_LONGITUDE"] = -114.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert errors == []

    def test_both_out_of_range(self, sample_flat_record):
        sample_flat_record["OUTAGE_LATITUDE"] = 0.0
        sample_flat_record["OUTAGE_LONGITUDE"] = 0.0
        errors = validate_coordinate_ranges(sample_flat_record)
        assert len(errors) == 2

    def test_null_coordinates_no_error(self, sample_flat_record):
        sample_flat_record["OUTAGE_LATITUDE"] = None
        sample_flat_record["OUTAGE_LONGITUDE"] = None
        errors = validate_coordinate_ranges(sample_flat_record)
        assert errors == []

    def test_non_numeric_coordinates_no_error(self, sample_flat_record):
        """Non-numeric types are caught by validate_numeric_fields, not here."""
        sample_flat_record["OUTAGE_LATITUDE"] = "invalid"
        errors = validate_coordinate_ranges(sample_flat_record)
        assert errors == []

    def test_missing_coordinates_no_error(self):
        record = {"F_OUTAGE_ID": "123"}
        errors = validate_coordinate_ranges(record)
        assert errors == []


class TestValidateTimestamps:
    """Tests for validate_timestamps()."""

    def test_valid_timestamps(self, sample_flat_record):
        errors = validate_timestamps(sample_flat_record)
        assert errors == []

    def test_timestamp_in_seconds_flagged(self, sample_flat_record):
        # 1772473320 is seconds, should be 1772473320000 (ms)
        sample_flat_record["OUTAGE_START"] = 1772473320
        errors = validate_timestamps(sample_flat_record)
        assert len(errors) == 1
        assert "not milliseconds" in errors[0].message

    def test_null_timestamp_no_error(self, sample_flat_record):
        sample_flat_record["CURRENT_ETOR"] = None
        errors = validate_timestamps(sample_flat_record)
        assert errors == []

    def test_zero_timestamp_flagged(self, sample_flat_record):
        sample_flat_record["OUTAGE_START"] = 0
        errors = validate_timestamps(sample_flat_record)
        assert len(errors) == 1

    def test_negative_timestamp_flagged(self, sample_flat_record):
        sample_flat_record["OUTAGE_START"] = -1000
        errors = validate_timestamps(sample_flat_record)
        assert len(errors) == 1

    def test_all_timestamp_fields_checked(self, sample_flat_record):
        timestamp_fields = ["OUTAGE_START", "LAST_UPDATE", "CURRENT_ETOR", "AUTO_ETOR"]
        for field in timestamp_fields:
            record = sample_flat_record.copy()
            record[field] = 100  # clearly in seconds, not ms
            errors = validate_timestamps(record)
            error_fields = {e.field for e in errors}
            assert field in error_fields, f"{field} not validated"

    def test_non_numeric_timestamp_skipped(self, sample_flat_record):
        """Non-numeric types are caught by validate_numeric_fields, not here."""
        sample_flat_record["OUTAGE_START"] = "not-a-timestamp"
        errors = validate_timestamps(sample_flat_record)
        assert errors == []

    def test_boundary_timestamp_year_2000(self, sample_flat_record):
        # Exactly at the boundary
        sample_flat_record["OUTAGE_START"] = 946684800000
        errors = validate_timestamps(sample_flat_record)
        assert errors == []

    def test_just_below_boundary_flagged(self, sample_flat_record):
        sample_flat_record["OUTAGE_START"] = 946684799999
        errors = validate_timestamps(sample_flat_record)
        assert len(errors) == 1


class TestValidateCustomerCount:
    """Tests for validate_customer_count()."""

    def test_valid_positive_count(self, sample_flat_record):
        errors = validate_customer_count(sample_flat_record)
        assert errors == []

    def test_zero_count_valid(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = 0
        errors = validate_customer_count(sample_flat_record)
        assert errors == []

    def test_negative_count_flagged(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = -5
        errors = validate_customer_count(sample_flat_record)
        assert len(errors) == 1
        assert "cannot be negative" in errors[0].message

    def test_null_count_no_error(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = None
        errors = validate_customer_count(sample_flat_record)
        assert errors == []

    def test_missing_count_no_error(self):
        record = {"F_OUTAGE_ID": "123"}
        errors = validate_customer_count(record)
        assert errors == []

    def test_large_count_valid(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = 1000000
        errors = validate_customer_count(sample_flat_record)
        assert errors == []

    def test_non_numeric_no_error(self, sample_flat_record):
        """Non-numeric types caught elsewhere."""
        sample_flat_record["EST_CUSTOMERS"] = "many"
        errors = validate_customer_count(sample_flat_record)
        assert errors == []


class TestValidateRecord:
    """Tests for validate_record() — the combined validator."""

    def test_valid_record_no_errors(self, sample_flat_record):
        errors = validate_record(sample_flat_record)
        assert errors == []

    def test_multiple_error_types(self):
        record = {
            "F_OUTAGE_ID": "999",
            "OBJECTID": 1,  # should be excluded
            "EST_CUSTOMERS": -5,  # negative
            "OUTAGE_LATITUDE": 0.0,  # out of range
            "OUTAGE_LONGITUDE": -121.0,
            "OUTAGE_START": 100,  # in seconds not ms
        }
        errors = validate_record(record)
        assert len(errors) > 3  # Should catch multiple issues

    def test_empty_record_catches_all_missing_fields(self):
        errors = validate_record({})
        required_errors = [e for e in errors if "Missing required field" in e.message]
        assert len(required_errors) == len(REQUIRED_FIELDS)


class TestValidateOutages:
    """Tests for validate_outages() — bulk validator."""

    def test_valid_records_empty_result(self, sample_flat_records):
        result = validate_outages(sample_flat_records)
        assert result == {}

    def test_invalid_record_included(self, sample_flat_records):
        sample_flat_records[0]["EST_CUSTOMERS"] = -1
        result = validate_outages(sample_flat_records)
        assert "187779" in result
        assert "187780" not in result

    def test_multiple_invalid_records(self, sample_flat_records):
        sample_flat_records[0]["EST_CUSTOMERS"] = -1
        sample_flat_records[1]["EST_CUSTOMERS"] = -2
        result = validate_outages(sample_flat_records)
        assert "187779" in result
        assert "187780" in result

    def test_empty_list_empty_result(self):
        result = validate_outages([])
        assert result == {}

    def test_record_without_id_uses_index(self):
        records = [{"CITY": "Test"}]
        result = validate_outages(records)
        assert "index_0" in result


class TestValidateUniqueIds:
    """Tests for validate_unique_ids()."""

    def test_unique_ids_no_errors(self, sample_flat_records):
        errors = validate_unique_ids(sample_flat_records)
        assert errors == []

    def test_duplicate_ids_detected(self, sample_flat_records):
        sample_flat_records[1]["F_OUTAGE_ID"] = "187779"  # duplicate
        errors = validate_unique_ids(sample_flat_records)
        assert len(errors) == 1
        assert "Duplicate ID" in errors[0].message
        assert "187779" in errors[0].message

    def test_empty_list_no_errors(self):
        errors = validate_unique_ids([])
        assert errors == []

    def test_single_record_no_errors(self, sample_flat_record):
        errors = validate_unique_ids([sample_flat_record])
        assert errors == []

    def test_record_missing_id_skipped(self):
        records = [{"CITY": "Test"}, {"CITY": "Test2"}]
        errors = validate_unique_ids(records)
        assert errors == []

    def test_multiple_duplicates(self):
        records = [
            {"F_OUTAGE_ID": "1"},
            {"F_OUTAGE_ID": "1"},
            {"F_OUTAGE_ID": "2"},
            {"F_OUTAGE_ID": "2"},
        ]
        errors = validate_unique_ids(records)
        assert len(errors) == 2

    def test_duplicate_error_includes_indices(self):
        records = [
            {"F_OUTAGE_ID": "100"},
            {"F_OUTAGE_ID": "200"},
            {"F_OUTAGE_ID": "100"},
        ]
        errors = validate_unique_ids(records)
        assert len(errors) == 1
        assert "0" in errors[0].message
        assert "2" in errors[0].message
