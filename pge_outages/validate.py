"""Validate PG&E outage records for structural and data integrity.

Provides functions to check that outage records conform to the expected
schema — required fields are present, data types are correct, and
coordinate values fall within plausible ranges.
"""

from typing import Any

# Fields that must be present in every outage record
REQUIRED_FIELDS: frozenset[str] = frozenset({
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
    "geometry_x",
    "geometry_y",
})

# Fields that are allowed to be null/None
NULLABLE_FIELDS: frozenset[str] = frozenset({
    "CREW_ETA",
    "COUNTY",
    "ZIP",
    "SPID",
    "CURRENT_ETOR",
    "CURRENT_ETOR_TEXT",
    "AUTO_ETOR",
    "geometry_x",
    "geometry_y",
})

# Valid California latitude range (approximate)
CA_LATITUDE_MIN = 32.0
CA_LATITUDE_MAX = 42.5

# Valid California longitude range (approximate)
CA_LONGITUDE_MIN = -125.0
CA_LONGITUDE_MAX = -114.0


class ValidationError(Exception):
    """Raised when an outage record fails validation."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"Validation error on '{field}': {message}")


def get_required_fields() -> frozenset[str]:
    """Return the set of field names required in every outage record.

    Returns:
        A frozen set of required field name strings.
    """
    return REQUIRED_FIELDS


def get_nullable_fields() -> frozenset[str]:
    """Return the set of field names that are allowed to be null.

    Returns:
        A frozen set of nullable field name strings.
    """
    return NULLABLE_FIELDS


def validate_coordinates(record: dict[str, Any]) -> list[ValidationError]:
    """Validate geographic coordinate fields in an outage record.

    Checks that ``OUTAGE_LATITUDE`` and ``OUTAGE_LONGITUDE`` are numeric
    and fall within plausible ranges for California.

    Args:
        record: A single flat outage record dictionary.

    Returns:
        A list of :class:`ValidationError` instances (empty if valid).
    """
    errors: list[ValidationError] = []

    lat = record.get("OUTAGE_LATITUDE")
    lon = record.get("OUTAGE_LONGITUDE")

    if lat is not None:
        if not isinstance(lat, (int, float)):
            errors.append(
                ValidationError("OUTAGE_LATITUDE", f"Expected numeric, got {type(lat).__name__}")
            )
        elif not (CA_LATITUDE_MIN <= lat <= CA_LATITUDE_MAX):
            errors.append(
                ValidationError(
                    "OUTAGE_LATITUDE",
                    f"Value {lat} outside California range [{CA_LATITUDE_MIN}, {CA_LATITUDE_MAX}]",
                )
            )

    if lon is not None:
        if not isinstance(lon, (int, float)):
            errors.append(
                ValidationError("OUTAGE_LONGITUDE", f"Expected numeric, got {type(lon).__name__}")
            )
        elif not (CA_LONGITUDE_MIN <= lon <= CA_LONGITUDE_MAX):
            errors.append(
                ValidationError(
                    "OUTAGE_LONGITUDE",
                    f"Value {lon} outside California range [{CA_LONGITUDE_MIN}, {CA_LONGITUDE_MAX}]",
                )
            )

    return errors


def validate_record(record: dict[str, Any]) -> list[ValidationError]:
    """Validate a single outage record.

    Checks for required fields, non-null constraints, and coordinate
    plausibility.

    Args:
        record: A single flat outage record dictionary.

    Returns:
        A list of :class:`ValidationError` instances (empty if valid).

    Raises:
        TypeError: If *record* is not a dictionary.
    """
    if not isinstance(record, dict):
        raise TypeError(f"Expected dict for record, got {type(record).__name__}")

    errors: list[ValidationError] = []

    # Check required fields are present
    missing = REQUIRED_FIELDS - record.keys()
    for field in sorted(missing):
        errors.append(ValidationError(field, "Required field is missing"))

    # Check non-nullable fields are not None
    for field in sorted(REQUIRED_FIELDS - NULLABLE_FIELDS):
        if field in record and record[field] is None:
            errors.append(ValidationError(field, "Field must not be null"))

    # Validate EST_CUSTOMERS is non-negative when present
    est = record.get("EST_CUSTOMERS")
    if est is not None:
        if not isinstance(est, (int, float)):
            errors.append(
                ValidationError("EST_CUSTOMERS", f"Expected numeric, got {type(est).__name__}")
            )
        elif est < 0:
            errors.append(
                ValidationError("EST_CUSTOMERS", f"Value {est} must not be negative")
            )

    # Validate coordinates
    errors.extend(validate_coordinates(record))

    return errors


def validate_outages(records: list[dict[str, Any]]) -> dict[int, list[ValidationError]]:
    """Validate a list of outage records.

    Args:
        records: A list of flat outage record dictionaries.

    Returns:
        A dictionary mapping record index to a list of validation errors.
        Only records with errors are included.  An empty dict means all
        records are valid.

    Raises:
        TypeError: If *records* is not a list.
    """
    if not isinstance(records, list):
        raise TypeError(f"Expected list for records, got {type(records).__name__}")

    errors_by_index: dict[int, list[ValidationError]] = {}
    for i, record in enumerate(records):
        record_errors = validate_record(record)
        if record_errors:
            errors_by_index[i] = record_errors

    return errors_by_index
