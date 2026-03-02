"""Validation logic for PG&E outage records.

Provides schema validation for outage records to ensure data integrity.
Validates required fields, field types, and value constraints based on
the known structure of PG&E outage data.
"""

from typing import Any

# Required fields that must be present in every outage record
REQUIRED_FIELDS = frozenset({
    "F_OUTAGE_ID",
    "OUTAGE_EXTENT",
    "OUTAGE_DEVICE_ID",
    "OUTAGE_CIRCUIT_ID",
    "CREW_CURRENT_STATUS",
    "OUTAGE_CAUSE",
    "EST_CUSTOMERS",
    "OUTAGE_LATITUDE",
    "OUTAGE_LONGITUDE",
    "CITY",
    "OUTAGE_START",
    "OUTAGE_START_TEXT",
    "LAST_UPDATE",
    "LAST_UPDATE_TEXT",
    "CURRENT_ETOR",
    "CURRENT_ETOR_TEXT",
    "AUTO_ETOR",
    "fts_flag",
    "geometry_x",
    "geometry_y",
})

# Fields that should be numeric (int or float) when not null
NUMERIC_FIELDS = frozenset({
    "OUTAGE_CIRCUIT_ID",
    "EST_CUSTOMERS",
    "OUTAGE_LATITUDE",
    "OUTAGE_LONGITUDE",
    "OUTAGE_START",
    "LAST_UPDATE",
    "CURRENT_ETOR",
    "AUTO_ETOR",
    "DEVICE_COUNT",
    "geometry_x",
    "geometry_y",
})

# Fields that may be nullable
NULLABLE_FIELDS = frozenset({
    "CREW_ETA",
    "COUNTY",
    "ZIP",
    "SPID",
    "geometry_x",
    "geometry_y",
    "AUTO_ETOR",
    "CURRENT_ETOR",
    "CURRENT_ETOR_TEXT",
})

# Known valid values for categorical fields
VALID_OUTAGE_EXTENTS = frozenset({"DEVICE", "CIRCUIT", "SUBSTATION"})

VALID_CREW_STATUSES = frozenset({
    "Crew On Site",
    "Crew En Route",
    "Crew Assigned",
    "Assessing",
    "Pending",
})

# Fields that should not be present in transformed records
# (they should have been stripped during transformation)
EXCLUDED_FIELDS = frozenset({"OBJECTID", "blueSkyNotificationSubscription"})


class ValidationError:
    """Represents a single validation error for an outage record."""

    def __init__(self, field: str, message: str, record_id: str | None = None):
        self.field = field
        self.message = message
        self.record_id = record_id

    def __repr__(self) -> str:
        prefix = f"[{self.record_id}] " if self.record_id else ""
        return f"ValidationError({prefix}{self.field}: {self.message})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValidationError):
            return NotImplemented
        return (
            self.field == other.field
            and self.message == other.message
            and self.record_id == other.record_id
        )


def validate_required_fields(record: dict[str, Any]) -> list[ValidationError]:
    """Check that all required fields are present in the record.

    Args:
        record: A flat outage record dictionary.

    Returns:
        List of ValidationError for each missing required field.
    """
    record_id = record.get("F_OUTAGE_ID")
    errors = []
    for field in sorted(REQUIRED_FIELDS):
        if field not in record:
            errors.append(
                ValidationError(field, "Missing required field", record_id)
            )
    return errors


def validate_no_excluded_fields(record: dict[str, Any]) -> list[ValidationError]:
    """Check that excluded fields have been properly stripped.

    Args:
        record: A flat outage record dictionary.

    Returns:
        List of ValidationError for each excluded field still present.
    """
    record_id = record.get("F_OUTAGE_ID")
    errors = []
    for field in sorted(EXCLUDED_FIELDS):
        if field in record:
            errors.append(
                ValidationError(
                    field,
                    "Field should have been removed during transformation",
                    record_id,
                )
            )
    return errors


def validate_numeric_fields(record: dict[str, Any]) -> list[ValidationError]:
    """Check that numeric fields contain numeric values (or null if nullable).

    Args:
        record: A flat outage record dictionary.

    Returns:
        List of ValidationError for each field with an invalid type.
    """
    record_id = record.get("F_OUTAGE_ID")
    errors = []
    for field in sorted(NUMERIC_FIELDS):
        if field not in record:
            continue
        value = record[field]
        if value is None:
            if field not in NULLABLE_FIELDS:
                errors.append(
                    ValidationError(
                        field,
                        "Non-nullable numeric field is null",
                        record_id,
                    )
                )
            continue
        if not isinstance(value, (int, float)):
            errors.append(
                ValidationError(
                    field,
                    f"Expected numeric type, got {type(value).__name__}",
                    record_id,
                )
            )
    return errors


def validate_coordinate_ranges(record: dict[str, Any]) -> list[ValidationError]:
    """Check that latitude/longitude values are within valid California ranges.

    PG&E serves California, so coordinates should be roughly within:
    - Latitude: 32.0 to 42.5
    - Longitude: -125.0 to -114.0

    Args:
        record: A flat outage record dictionary.

    Returns:
        List of ValidationError for out-of-range coordinates.
    """
    record_id = record.get("F_OUTAGE_ID")
    errors = []

    lat = record.get("OUTAGE_LATITUDE")
    if lat is not None and isinstance(lat, (int, float)):
        if not (32.0 <= lat <= 42.5):
            errors.append(
                ValidationError(
                    "OUTAGE_LATITUDE",
                    f"Latitude {lat} outside California range (32.0-42.5)",
                    record_id,
                )
            )

    lon = record.get("OUTAGE_LONGITUDE")
    if lon is not None and isinstance(lon, (int, float)):
        if not (-125.0 <= lon <= -114.0):
            errors.append(
                ValidationError(
                    "OUTAGE_LONGITUDE",
                    f"Longitude {lon} outside California range (-125.0 to -114.0)",
                    record_id,
                )
            )

    return errors


def validate_timestamps(record: dict[str, Any]) -> list[ValidationError]:
    """Check that timestamp fields are positive and in milliseconds.

    PG&E timestamps are Unix epoch milliseconds. They should be positive
    and in a reasonable range (after year 2000 = 946684800000).

    Args:
        record: A flat outage record dictionary.

    Returns:
        List of ValidationError for invalid timestamps.
    """
    record_id = record.get("F_OUTAGE_ID")
    errors = []
    min_timestamp_ms = 946684800000  # 2000-01-01 in ms

    timestamp_fields = ["OUTAGE_START", "LAST_UPDATE", "CURRENT_ETOR", "AUTO_ETOR"]
    for field in timestamp_fields:
        value = record.get(field)
        if value is None:
            continue
        if not isinstance(value, (int, float)):
            continue  # Type errors caught by validate_numeric_fields
        if value < min_timestamp_ms:
            errors.append(
                ValidationError(
                    field,
                    f"Timestamp {value} appears to be in seconds, not milliseconds",
                    record_id,
                )
            )

    return errors


def validate_customer_count(record: dict[str, Any]) -> list[ValidationError]:
    """Check that EST_CUSTOMERS is non-negative.

    Args:
        record: A flat outage record dictionary.

    Returns:
        List of ValidationError if customer count is negative.
    """
    record_id = record.get("F_OUTAGE_ID")
    errors = []
    est = record.get("EST_CUSTOMERS")
    if est is not None and isinstance(est, (int, float)):
        if est < 0:
            errors.append(
                ValidationError(
                    "EST_CUSTOMERS",
                    f"Estimated customers cannot be negative: {est}",
                    record_id,
                )
            )
    return errors


def validate_record(record: dict[str, Any]) -> list[ValidationError]:
    """Run all validations on a single outage record.

    Args:
        record: A flat outage record dictionary.

    Returns:
        List of all ValidationErrors found.
    """
    errors = []
    errors.extend(validate_required_fields(record))
    errors.extend(validate_no_excluded_fields(record))
    errors.extend(validate_numeric_fields(record))
    errors.extend(validate_coordinate_ranges(record))
    errors.extend(validate_timestamps(record))
    errors.extend(validate_customer_count(record))
    return errors


def validate_outages(records: list[dict[str, Any]]) -> dict[str, list[ValidationError]]:
    """Validate a full list of outage records.

    Args:
        records: List of flat outage record dictionaries.

    Returns:
        Dict mapping record IDs (or index) to their validation errors.
        Only records with errors are included.
    """
    result = {}
    for i, record in enumerate(records):
        errors = validate_record(record)
        if errors:
            key = record.get("F_OUTAGE_ID", f"index_{i}")
            result[key] = errors
    return result


def validate_unique_ids(records: list[dict[str, Any]]) -> list[ValidationError]:
    """Check that all F_OUTAGE_ID values are unique.

    Args:
        records: List of flat outage record dictionaries.

    Returns:
        List of ValidationErrors for duplicate IDs.
    """
    seen: dict[str, int] = {}
    errors = []
    for i, record in enumerate(records):
        outage_id = record.get("F_OUTAGE_ID")
        if outage_id is None:
            continue
        outage_id_str = str(outage_id)
        if outage_id_str in seen:
            errors.append(
                ValidationError(
                    "F_OUTAGE_ID",
                    f"Duplicate ID '{outage_id_str}' found at indices "
                    f"{seen[outage_id_str]} and {i}",
                    outage_id_str,
                )
            )
        else:
            seen[outage_id_str] = i
    return errors
