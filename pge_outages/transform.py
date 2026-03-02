"""Data transformation logic for PG&E outage records.

Replicates the jq transformation from the GitHub Actions workflow that:
1. Extracts the 'features' array from the API response
2. Flattens nested attributes into top-level fields
3. Removes excluded fields (OBJECTID, blueSkyNotificationSubscription)
4. Promotes geometry.x and geometry.y to top-level geometry_x and geometry_y
"""

from typing import Any

# Fields that should be removed during transformation
EXCLUDED_FIELDS = frozenset({"OBJECTID", "blueSkyNotificationSubscription"})


def extract_features(api_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the 'features' array from a raw PG&E API response.

    Args:
        api_response: Raw JSON response from the PG&E ArcGIS MapServer.

    Returns:
        List of feature dictionaries.

    Raises:
        ValueError: If the response does not contain a 'features' key.
    """
    if "features" not in api_response:
        raise ValueError(
            "API response missing 'features' key. "
            f"Available keys: {list(api_response.keys())}"
        )
    features = api_response["features"]
    if not isinstance(features, list):
        raise ValueError(
            f"Expected 'features' to be a list, got {type(features).__name__}"
        )
    return features


def flatten_feature(feature: dict[str, Any]) -> dict[str, Any]:
    """Flatten a single feature record from the PG&E API response.

    Takes a feature with nested 'attributes' and 'geometry' dicts and
    produces a flat dict with:
    - All attribute fields (minus excluded ones)
    - geometry_x and geometry_y promoted to top level

    Args:
        feature: A single feature dict from the API, expected to have
                 'attributes' and optionally 'geometry' keys.

    Returns:
        A flat dictionary with all fields at the top level.

    Raises:
        ValueError: If the feature is missing the 'attributes' key.
    """
    if "attributes" not in feature:
        raise ValueError(
            f"Feature missing 'attributes' key. Available keys: {list(feature.keys())}"
        )

    attributes = feature["attributes"]
    if not isinstance(attributes, dict):
        raise ValueError(
            f"Expected 'attributes' to be a dict, got {type(attributes).__name__}"
        )

    # Start with attributes, excluding specified fields
    result = {
        k: v for k, v in attributes.items() if k not in EXCLUDED_FIELDS
    }

    # Extract geometry coordinates
    geometry = feature.get("geometry") or {}
    result["geometry_x"] = geometry.get("x")
    result["geometry_y"] = geometry.get("y")

    return result


def transform_api_response(api_response: dict[str, Any]) -> list[dict[str, Any]]:
    """Transform a full PG&E API response into flat outage records.

    This is the main entry point that replicates the full jq pipeline
    from the GitHub Actions workflow.

    Args:
        api_response: Raw JSON response from the PG&E ArcGIS MapServer.

    Returns:
        List of flat outage record dictionaries.
    """
    features = extract_features(api_response)
    return [flatten_feature(f) for f in features]


def build_fetch_url(uuid: str) -> str:
    """Build the PG&E API fetch URL with a cache-busting parameter.

    Args:
        uuid: A unique string appended to the URL to bypass CDN caching.

    Returns:
        The full URL for the PG&E outage API query.
    """
    base_url = (
        "https://ags.pge.esriemcs.com/arcgis/rest/services/43/outages/"
        "MapServer/5/query"
    )
    params = "where=1%3D1&outFields=*&f=pjson"
    return f"{base_url}?{params}&_{uuid}"
