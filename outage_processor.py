"""
Core business logic for PG&E outage data processing.

Extracts the data transformation, validation, and utility logic that was
previously embedded as shell commands (curl | jq) in the GitHub Actions
workflow into testable Python functions.
"""

import uuid
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs

# The base PG&E ArcGIS endpoint for point-location outage data
BASE_URL = (
    "https://ags.pge.esriemcs.com/arcgis/rest/services/43/outages/MapServer/5/query"
)

DEFAULT_QUERY_PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "f": "pjson",
}

# Fields that are removed during the jq transformation step
FIELDS_TO_STRIP = {"OBJECTID", "blueSkyNotificationSubscription"}

# Required fields every valid outage record must contain
REQUIRED_FIELDS = {
    "F_OUTAGE_ID",
    "OUTAGE_EXTENT",
    "OUTAGE_DEVICE_ID",
    "OUTAGE_CIRCUIT_ID",
    "CREW_CURRENT_STATUS",
    "OUTAGE_CAUSE",
    "EST_CUSTOMERS",
    "OUTAGE_LATITUDE",
    "OUTAGE_LONGITUDE",
    "OUTAGE_START",
    "OUTAGE_START_TEXT",
    "LAST_UPDATE",
    "LAST_UPDATE_TEXT",
    "CURRENT_ETOR",
    "CURRENT_ETOR_TEXT",
}

# Fields that must be numeric (int or float) when present and non-null
NUMERIC_FIELDS = {
    "EST_CUSTOMERS",
    "OUTAGE_LATITUDE",
    "OUTAGE_LONGITUDE",
    "OUTAGE_START",
    "LAST_UPDATE",
    "CURRENT_ETOR",
    "AUTO_ETOR",
    "OUTAGE_CIRCUIT_ID",
    "DEVICE_COUNT",
    "geometry_x",
    "geometry_y",
}

# Fields that are allowed to be null
NULLABLE_FIELDS = {
    "CREW_ETA",
    "COUNTY",
    "ZIP",
    "SPID",
    "AUTO_ETOR",
}


def build_fetch_url(base_url=None, cache_bust=True):
    """
    Build the URL for fetching outage data from the PG&E ArcGIS endpoint.

    Appends a unique cache-busting parameter (similar to `_$(uuidgen)` in
    the shell workflow) to bypass CDN caching.

    Args:
        base_url: The base API URL. Defaults to the PG&E endpoint.
        cache_bust: Whether to append a UUID cache-busting parameter.

    Returns:
        The fully constructed URL string.
    """
    if base_url is None:
        base_url = BASE_URL

    params = dict(DEFAULT_QUERY_PARAMS)

    if cache_bust:
        params[f"_{uuid.uuid4().hex[:8]}"] = ""

    return f"{base_url}?{urlencode(params, doseq=True)}"


def normalize_feature(feature):
    """
    Normalize a single raw ArcGIS feature into a flat outage record.

    This replicates the jq transformation:
    - Extracts attributes, removing OBJECTID and blueSkyNotificationSubscription
    - Promotes geometry.x and geometry.y to top-level geometry_x and geometry_y
    - Merges everything into a flat dictionary

    Args:
        feature: A raw feature dict from the ArcGIS API response, expected
                 to have 'attributes' and optionally 'geometry' keys.

    Returns:
        A flat dictionary representing the outage record.

    Raises:
        ValueError: If the feature is missing the 'attributes' key.
    """
    if not isinstance(feature, dict):
        raise ValueError(f"Feature must be a dict, got {type(feature).__name__}")

    if "attributes" not in feature:
        raise ValueError("Feature is missing required 'attributes' key")

    attributes = {
        k: v
        for k, v in feature["attributes"].items()
        if k not in FIELDS_TO_STRIP
    }

    geometry = feature.get("geometry", {}) or {}
    geometry_x = geometry.get("x")
    geometry_y = geometry.get("y")

    record = {**attributes}
    record["geometry_x"] = geometry_x
    record["geometry_y"] = geometry_y

    return record


def transform_api_response(raw_response):
    """
    Transform a raw ArcGIS API response into a list of flat outage records.

    This is the Python equivalent of the full jq pipeline in fetch.yml:
        .features | map({
            attributes: (.attributes | del(.blueSkyNotificationSubscription, .OBJECTID)),
            geometry_x: .geometry.x,
            geometry_y: .geometry.y
        } | .attributes + {geometry_x: .geometry_x, geometry_y: .geometry_y})

    Args:
        raw_response: The parsed JSON response from the ArcGIS API.
                      Expected to have a 'features' key containing an array.

    Returns:
        A list of flat outage record dictionaries.

    Raises:
        ValueError: If the response is malformed or missing 'features'.
    """
    if not isinstance(raw_response, dict):
        raise ValueError(
            f"API response must be a dict, got {type(raw_response).__name__}"
        )

    if "features" not in raw_response:
        raise ValueError("API response is missing required 'features' key")

    features = raw_response["features"]

    if not isinstance(features, list):
        raise ValueError(
            f"'features' must be a list, got {type(features).__name__}"
        )

    return [normalize_feature(f) for f in features]


def validate_outage_record(record):
    """
    Validate that an outage record has all required fields with correct types.

    Args:
        record: A flat outage record dictionary.

    Returns:
        A tuple of (is_valid: bool, errors: list[str]).
    """
    errors = []

    if not isinstance(record, dict):
        return False, [f"Record must be a dict, got {type(record).__name__}"]

    # Check for required fields
    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        errors.append(f"Missing required fields: {sorted(missing)}")

    # Check numeric fields have correct types
    for field in NUMERIC_FIELDS:
        if field in record and record[field] is not None:
            if not isinstance(record[field], (int, float)):
                errors.append(
                    f"Field '{field}' must be numeric, got "
                    f"{type(record[field]).__name__}: {record[field]!r}"
                )

    # Validate F_OUTAGE_ID is a non-empty string when present
    if "F_OUTAGE_ID" in record:
        fid = record["F_OUTAGE_ID"]
        if not isinstance(fid, str) or not fid.strip():
            errors.append(
                f"F_OUTAGE_ID must be a non-empty string, got {fid!r}"
            )

    # Validate latitude/longitude ranges when present and non-null
    lat = record.get("OUTAGE_LATITUDE")
    lon = record.get("OUTAGE_LONGITUDE")
    if lat is not None and isinstance(lat, (int, float)):
        if not (-90 <= lat <= 90):
            errors.append(f"OUTAGE_LATITUDE {lat} is out of range [-90, 90]")
    if lon is not None and isinstance(lon, (int, float)):
        if not (-180 <= lon <= 180):
            errors.append(f"OUTAGE_LONGITUDE {lon} is out of range [-180, 180]")

    # Validate timestamps are positive when present and non-null
    for ts_field in ("OUTAGE_START", "LAST_UPDATE", "CURRENT_ETOR", "AUTO_ETOR"):
        val = record.get(ts_field)
        if val is not None and isinstance(val, (int, float)):
            if val <= 0:
                errors.append(f"Timestamp '{ts_field}' must be positive, got {val}")

    # Validate EST_CUSTOMERS is non-negative when present and non-null
    est = record.get("EST_CUSTOMERS")
    if est is not None and isinstance(est, (int, float)):
        if est < 0:
            errors.append(f"EST_CUSTOMERS must be non-negative, got {est}")

    return len(errors) == 0, errors


def filter_point_features(features):
    """
    Filter a list of raw ArcGIS features to include only point-location data.

    Point features have a geometry object with 'x' and 'y' coordinates.
    Polygon features have a 'rings' key instead. This repo only archives
    point-location data.

    Args:
        features: A list of raw feature dicts from the ArcGIS API.

    Returns:
        A list containing only the point-location features.
    """
    point_features = []
    for feature in features:
        geometry = feature.get("geometry")
        if geometry is None:
            continue
        # Point features have x/y coordinates; polygon features have 'rings'
        if "x" in geometry and "y" in geometry and "rings" not in geometry:
            point_features.append(feature)
    return point_features


def compute_outage_stats(records):
    """
    Compute summary statistics from a list of outage records.

    Args:
        records: A list of flat outage record dictionaries.

    Returns:
        A dictionary containing:
        - total_outages: Total count of outage records
        - total_customers_affected: Sum of EST_CUSTOMERS across all records
        - outages_by_cause: Dict mapping OUTAGE_CAUSE to count
        - outages_by_city: Dict mapping CITY to count
        - outages_by_crew_status: Dict mapping CREW_CURRENT_STATUS to count
    """
    stats = {
        "total_outages": len(records),
        "total_customers_affected": 0,
        "outages_by_cause": {},
        "outages_by_city": {},
        "outages_by_crew_status": {},
    }

    for record in records:
        est = record.get("EST_CUSTOMERS")
        if est is not None and isinstance(est, (int, float)):
            stats["total_customers_affected"] += est

        cause = record.get("OUTAGE_CAUSE", "UNKNOWN")
        stats["outages_by_cause"][cause] = (
            stats["outages_by_cause"].get(cause, 0) + 1
        )

        city = record.get("CITY", "UNKNOWN")
        stats["outages_by_city"][city] = (
            stats["outages_by_city"].get(city, 0) + 1
        )

        crew = record.get("CREW_CURRENT_STATUS", "UNKNOWN")
        stats["outages_by_crew_status"][crew] = (
            stats["outages_by_crew_status"].get(crew, 0) + 1
        )

    return stats


def records_diff(old_records, new_records, key_field="F_OUTAGE_ID"):
    """
    Compute the diff between two lists of outage records.

    This is a pure-Python equivalent of the csv-diff logic, identifying
    added, removed, and changed records by their key field.

    Args:
        old_records: List of outage record dicts (previous snapshot).
        new_records: List of outage record dicts (new snapshot).
        key_field: The field to use as a unique identifier.

    Returns:
        A dictionary with keys:
        - added: List of records in new but not in old
        - removed: List of records in old but not in new
        - changed: List of dicts with 'key', 'changes' showing field diffs

    Raises:
        ValueError: If key_field is missing from any record.
    """
    old_by_key = {}
    for r in old_records:
        if key_field not in r:
            raise ValueError(f"Record missing key field '{key_field}': {r}")
        old_by_key[r[key_field]] = r

    new_by_key = {}
    for r in new_records:
        if key_field not in r:
            raise ValueError(f"Record missing key field '{key_field}': {r}")
        new_by_key[r[key_field]] = r

    old_keys = set(old_by_key.keys())
    new_keys = set(new_by_key.keys())

    added = [new_by_key[k] for k in sorted(new_keys - old_keys)]
    removed = [old_by_key[k] for k in sorted(old_keys - new_keys)]

    changed = []
    for key in sorted(old_keys & new_keys):
        old_rec = old_by_key[key]
        new_rec = new_by_key[key]
        changes = {}
        all_fields = set(old_rec.keys()) | set(new_rec.keys())
        for field in sorted(all_fields):
            old_val = old_rec.get(field)
            new_val = new_rec.get(field)
            if old_val != new_val:
                changes[field] = {"old": old_val, "new": new_val}
        if changes:
            changed.append({"key": key, "changes": changes})

    return {"added": added, "removed": removed, "changed": changed}
