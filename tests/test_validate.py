"""Tests for pge_outages.validate module.

Covers record validation including required fields, nullable constraints,
coordinate range checks, and batch validation.
"""

import pytest

from pge_outages.validate import (
    CA_LATITUDE_MAX,
    CA_LATITUDE_MIN,
    CA_LONGITUDE_MAX,
    CA_LONGITUDE_MIN,
    NULLABLE_FIELDS,
    REQUIRED_FIELDS,
    ValidationError,
    get_nullable_fields,
    get_required_fields,
    validate_coordinates,
    validate_outages,
    validate_record,
)


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------


class TestValidationError:
    """Tests for the ValidationError exception class."""

    def test_stores_field_and_message(self):
        err = ValidationError("CITY", "is missing")
        assert err.field == "CITY"
        assert err.message == "is missing"

    def test_str_representation(self):
        err = ValidationError("CITY", "is missing")
        assert "CITY" in str(err)
        assert "is missing" in str(err)

    def test_is_exception(self):
        assert issubclass(ValidationError, Exception)


# ---------------------------------------------------------------------------
# get_required_fields / get_nullable_fields
# ---------------------------------------------------------------------------


class TestFieldConstants:
    """Tests for field constant accessors."""

    def test_required_fields_is_frozenset(self):
        assert isinstance(get_required_fields(), frozenset)

    def test_nullable_fields_is_frozenset(self):
        assert isinstance(get_nullable_fields(), frozenset)

    def test_required_fields_contains_key_fields(self):
        required = get_required_fields()
        assert "F_OUTAGE_ID" in required
        assert "OUTAGE_LATITUDE" in required
        assert "OUTAGE_LONGITUDE" in required
        assert "CITY" in required
        assert "geometry_x" in required
        assert "geometry_y" in required

    def test_nullable_fields_contains_optional_fields(self):
        nullable = get_nullable_fields()
        assert "CREW_ETA" in nullable
        assert "COUNTY" in nullable
        assert "ZIP" in nullable
        assert "SPID" in nullable

    def test_nullable_is_not_superset_of_required(self):
        """Not all required fields should be nullable."""
        non_nullable_required = REQUIRED_FIELDS - NULLABLE_FIELDS
        assert len(non_nullable_required) > 0

    def test_f_outage_id_not_nullable(self):
        assert "F_OUTAGE_ID" not in NULLABLE_FIELDS


# ---------------------------------------------------------------------------
# validate_coordinates
# ---------------------------------------------------------------------------


class TestValidateCoordinates:
    """Tests for validate_coordinates()."""

    def test_valid_coordinates(self, sample_flat_record):
        errors = validate_coordinates(sample_flat_record)
        assert errors == []

    def test_latitude_too_low(self):
        record = {"OUTAGE_LATITUDE": 20.0, "OUTAGE_LONGITUDE": -121.0}
        errors = validate_coordinates(record)
        assert len(errors) == 1
        assert errors[0].field == "OUTAGE_LATITUDE"
        assert "outside California range" in errors[0].message

    def test_latitude_too_high(self):
        record = {"OUTAGE_LATITUDE": 50.0, "OUTAGE_LONGITUDE": -121.0}
        errors = validate_coordinates(record)
        assert len(errors) == 1
        assert errors[0].field == "OUTAGE_LATITUDE"

    def test_longitude_too_low(self):
        record = {"OUTAGE_LATITUDE": 37.0, "OUTAGE_LONGITUDE": -130.0}
        errors = validate_coordinates(record)
        assert len(errors) == 1
        assert errors[0].field == "OUTAGE_LONGITUDE"

    def test_longitude_too_high(self):
        record = {"OUTAGE_LATITUDE": 37.0, "OUTAGE_LONGITUDE": -100.0}
        errors = validate_coordinates(record)
        assert len(errors) == 1
        assert errors[0].field == "OUTAGE_LONGITUDE"

    def test_both_coordinates_out_of_range(self):
        record = {"OUTAGE_LATITUDE": 0.0, "OUTAGE_LONGITUDE": 0.0}
        errors = validate_coordinates(record)
        assert len(errors) == 2
        fields = {e.field for e in errors}
        assert fields == {"OUTAGE_LATITUDE", "OUTAGE_LONGITUDE"}

    def test_boundary_latitude_min(self):
        record = {"OUTAGE_LATITUDE": CA_LATITUDE_MIN, "OUTAGE_LONGITUDE": -121.0}
        errors = validate_coordinates(record)
        assert errors == []

    def test_boundary_latitude_max(self):
        record = {"OUTAGE_LATITUDE": CA_LATITUDE_MAX, "OUTAGE_LONGITUDE": -121.0}
        errors = validate_coordinates(record)
        assert errors == []

    def test_boundary_longitude_min(self):
        record = {"OUTAGE_LATITUDE": 37.0, "OUTAGE_LONGITUDE": CA_LONGITUDE_MIN}
        errors = validate_coordinates(record)
        assert errors == []

    def test_boundary_longitude_max(self):
        record = {"OUTAGE_LATITUDE": 37.0, "OUTAGE_LONGITUDE": CA_LONGITUDE_MAX}
        errors = validate_coordinates(record)
        assert errors == []

    def test_none_latitude_skips_check(self):
        record = {"OUTAGE_LATITUDE": None, "OUTAGE_LONGITUDE": -121.0}
        errors = validate_coordinates(record)
        assert errors == []

    def test_none_longitude_skips_check(self):
        record = {"OUTAGE_LATITUDE": 37.0, "OUTAGE_LONGITUDE": None}
        errors = validate_coordinates(record)
        assert errors == []

    def test_string_latitude_errors(self):
        record = {"OUTAGE_LATITUDE": "37.0", "OUTAGE_LONGITUDE": -121.0}
        errors = validate_coordinates(record)
        assert len(errors) == 1
        assert "Expected numeric" in errors[0].message

    def test_string_longitude_errors(self):
        record = {"OUTAGE_LATITUDE": 37.0, "OUTAGE_LONGITUDE": "bad"}
        errors = validate_coordinates(record)
        assert len(errors) == 1
        assert "Expected numeric" in errors[0].message

    def test_missing_both_coordinates(self):
        """Missing keys (not present at all) should not error."""
        errors = validate_coordinates({})
        assert errors == []

    def test_integer_coordinates_accepted(self):
        record = {"OUTAGE_LATITUDE": 37, "OUTAGE_LONGITUDE": -121}
        errors = validate_coordinates(record)
        assert errors == []


# ---------------------------------------------------------------------------
# validate_record
# ---------------------------------------------------------------------------


class TestValidateRecord:
    """Tests for validate_record()."""

    def test_valid_record_no_errors(self, sample_flat_record):
        errors = validate_record(sample_flat_record)
        assert errors == []

    def test_missing_required_field(self, sample_flat_record):
        del sample_flat_record["F_OUTAGE_ID"]
        errors = validate_record(sample_flat_record)
        fields = {e.field for e in errors}
        assert "F_OUTAGE_ID" in fields

    def test_multiple_missing_fields(self):
        errors = validate_record({})
        assert len(errors) >= len(REQUIRED_FIELDS)

    def test_null_non_nullable_field(self, sample_flat_record):
        sample_flat_record["F_OUTAGE_ID"] = None
        errors = validate_record(sample_flat_record)
        error_fields = {e.field for e in errors}
        assert "F_OUTAGE_ID" in error_fields

    def test_null_nullable_field_ok(self, sample_flat_record):
        sample_flat_record["CREW_ETA"] = None
        errors = validate_record(sample_flat_record)
        # No errors related to CREW_ETA
        crew_eta_errors = [e for e in errors if e.field == "CREW_ETA"]
        assert crew_eta_errors == []

    def test_negative_est_customers(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = -5
        errors = validate_record(sample_flat_record)
        est_errors = [e for e in errors if e.field == "EST_CUSTOMERS"]
        assert len(est_errors) == 1
        assert "negative" in est_errors[0].message

    def test_zero_est_customers_ok(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = 0
        errors = validate_record(sample_flat_record)
        est_errors = [e for e in errors if e.field == "EST_CUSTOMERS"]
        assert est_errors == []

    def test_string_est_customers(self, sample_flat_record):
        sample_flat_record["EST_CUSTOMERS"] = "many"
        errors = validate_record(sample_flat_record)
        est_errors = [e for e in errors if e.field == "EST_CUSTOMERS"]
        assert len(est_errors) == 1
        assert "Expected numeric" in est_errors[0].message

    def test_none_est_customers_triggers_non_null_error(self, sample_flat_record):
        """EST_CUSTOMERS is required and non-nullable; None triggers an error."""
        sample_flat_record["EST_CUSTOMERS"] = None
        errors = validate_record(sample_flat_record)
        est_errors = [e for e in errors if e.field == "EST_CUSTOMERS"]
        assert len(est_errors) == 1
        assert "must not be null" in est_errors[0].message

    def test_invalid_coordinates_caught(self, sample_flat_record):
        sample_flat_record["OUTAGE_LATITUDE"] = 0.0
        sample_flat_record["OUTAGE_LONGITUDE"] = 0.0
        errors = validate_record(sample_flat_record)
        coord_errors = [
            e for e in errors if e.field in ("OUTAGE_LATITUDE", "OUTAGE_LONGITUDE")
        ]
        assert len(coord_errors) == 2

    def test_extra_fields_ignored(self, sample_flat_record):
        sample_flat_record["EXTRA_FIELD"] = "surprise"
        errors = validate_record(sample_flat_record)
        assert errors == []

    def test_non_dict_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            validate_record("not a record")

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            validate_record(None)

    def test_list_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected dict"):
            validate_record([])


# ---------------------------------------------------------------------------
# validate_outages
# ---------------------------------------------------------------------------


class TestValidateOutages:
    """Tests for validate_outages()."""

    def test_all_valid(self, sample_flat_record):
        result = validate_outages([sample_flat_record])
        assert result == {}

    def test_empty_list(self):
        result = validate_outages([])
        assert result == {}

    def test_single_invalid_record(self):
        result = validate_outages([{}])
        assert 0 in result
        assert len(result[0]) > 0

    def test_mixed_valid_and_invalid(self, sample_flat_record):
        records = [sample_flat_record, {}]
        result = validate_outages(records)
        assert 0 not in result  # First record is valid
        assert 1 in result  # Second record has errors

    def test_multiple_invalid_records(self):
        result = validate_outages([{}, {"F_OUTAGE_ID": "1"}])
        assert 0 in result
        assert 1 in result

    def test_returns_correct_indices(self, sample_flat_record):
        records = [sample_flat_record, sample_flat_record, {}, sample_flat_record]
        result = validate_outages(records)
        assert list(result.keys()) == [2]

    def test_non_list_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected list"):
            validate_outages("not a list")

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected list"):
            validate_outages(None)

    def test_dict_raises_type_error(self):
        with pytest.raises(TypeError, match="Expected list"):
            validate_outages({})
