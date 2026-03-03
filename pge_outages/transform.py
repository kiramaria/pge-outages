"""Transform raw PG&E ArcGIS API responses into flat outage records.

This module replicates the jq transformation logic from the GitHub Actions
workflow (fetch.yml), converting nested API feature objects into flat
dictionaries suitable for storage in outages.json.

The jq equivalent:
    .features | map({
        attributes: (.attributes | del(.blueSkyNotificationSubscription, .OBJECTID)),
        geometry_x: .geometry.x,
        geometry_y: .geometry.y
    } | .attributes + {geometry_x: .geometry_x, geometry_y: .geometry_y})
"""

from typing import Any

# Fields that should be stripped from each feature's attributes
EXCLUDED_FIELDS = frozenset({"blueSkyNotificationSubscription", "OBJECTID"})


def remove_excluded_fields(attributes: dict[str, Any]) -> dict[str, Any]:
    """Remove fields that should not appear in the output records.

    Strips ``OBJECTID`` and ``blueSkyNotificationSubscription`` from the
    attributes dictionary, matching the ``del()`` call in the jq pipeline.

    Args:
        attributes: The raw attributes dictionary from a single API feature.

    Returns:
        A new dictionary with excluded fields removed.

    Raises:
        TypeError: If *attributes* is not a dictionary.
    """
    if not isinstance(attributes, dict):
        raise TypeError(f"Expected dict for attributes, got {type(attributes).__name__}")
    return {k: v for k, v in attributes.items() if k not in EXCLUDED_FIELDS}


def extract_geometry(feature: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extract geometry coordinates from a feature.

    Reads ``geometry.x`` and ``geometry.y`` from the feature's geometry
    object.  If the geometry key is missing or ``None``, both coordinates
    are returned as ``None``.

    Args:
        feature: A single feature object from the API response.

    Returns:
        A ``(geometry_x, geometry_y)`` tuple.
    """
    geometry = feature.get("geometry")
    if geometry is None:
        return None, None
    return geometry.get("x"), geometry.get("y")


def flatten_feature(feature: dict[str, Any]) -> dict[str, Any]:
    """Flatten a single API feature into a flat outage record.

    Combines the cleaned attributes with top-level ``geometry_x`` and
    ``geometry_y`` fields, producing the same shape written to
    ``outages.json``.

    Args:
        feature: A single feature object from the API ``features`` array.

    Returns:
        A flat dictionary representing one outage record.

    Raises:
        TypeError: If *feature* is not a dictionary.
        KeyError: If *feature* is missing the ``attributes`` key.
    """
    if not isinstance(feature, dict):
        raise TypeError(f"Expected dict for feature, got {type(feature).__name__}")
    if "attributes" not in feature:
        raise KeyError("Feature is missing required 'attributes' key")

    attributes = remove_excluded_fields(feature["attributes"])
    geometry_x, geometry_y = extract_geometry(feature)

    return {**attributes, "geometry_x": geometry_x, "geometry_y": geometry_y}


def transform_api_response(raw_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform a full API response into a list of flat outage records.

    This is the main entry point that mirrors the complete jq pipeline
    used in the fetch workflow.

    Args:
        raw_data: The parsed JSON response from the PG&E ArcGIS API.
            Must contain a ``features`` key with a list of feature objects.

    Returns:
        A list of flat outage record dictionaries.

    Raises:
        TypeError: If *raw_data* is not a dictionary.
        KeyError: If *raw_data* is missing the ``features`` key.
        ValueError: If ``features`` is not a list.
    """
    if not isinstance(raw_data, dict):
        raise TypeError(f"Expected dict for raw_data, got {type(raw_data).__name__}")
    if "features" not in raw_data:
        raise KeyError("API response is missing required 'features' key")
    features = raw_data["features"]
    if not isinstance(features, list):
        raise ValueError(f"Expected list for 'features', got {type(features).__name__}")

    return [flatten_feature(f) for f in features]
