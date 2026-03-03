"""Fetch outage data from the PG&E ArcGIS MapServer API.

Constructs the query URL (with a cache-busting UUID parameter),
issues the HTTP request, and optionally transforms the response
into flat outage records.
"""

import json
import uuid
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from pge_outages.transform import transform_api_response

# Base URL for the PG&E ArcGIS outage endpoint (layer 5 – point locations)
BASE_URL = (
    "https://ags.pge.esriemcs.com/arcgis/rest/services/43/outages/MapServer/5/query"
)

# Default query parameters: fetch all records with all fields in JSON format
DEFAULT_PARAMS = "where=1%3D1&outFields=*&f=pjson"

# Request timeout in seconds
DEFAULT_TIMEOUT = 30


def build_api_url(cache_bust_id: str | None = None) -> str:
    """Build the full API URL with cache-busting parameter.

    Appends a unique identifier to the query string so that CDN and
    server-side caches are bypassed on every request.

    Args:
        cache_bust_id: An explicit cache-bust value.  When ``None``
            (the default), a random UUID4 is generated automatically.

    Returns:
        The complete URL string ready for an HTTP GET request.
    """
    if cache_bust_id is None:
        cache_bust_id = str(uuid.uuid4())
    return f"{BASE_URL}?{DEFAULT_PARAMS}&_{cache_bust_id}"


def fetch_outages_raw(
    url: str | None = None, timeout: int = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Fetch the raw JSON response from the PG&E outage API.

    Args:
        url: The full URL to fetch.  Defaults to :func:`build_api_url`.
        timeout: HTTP request timeout in seconds.

    Returns:
        The parsed JSON response as a dictionary.

    Raises:
        ConnectionError: If the HTTP request fails.
        ValueError: If the response is not valid JSON.
    """
    if url is None:
        url = build_api_url()

    request = Request(url, headers={"User-Agent": "pge-outages/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (URLError, OSError) as exc:
        raise ConnectionError(f"Failed to fetch outage data: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in API response: {exc}") from exc


def fetch_and_transform(
    url: str | None = None, timeout: int = DEFAULT_TIMEOUT
) -> list[dict[str, Any]]:
    """Fetch outage data and transform it into flat records.

    Convenience wrapper that calls :func:`fetch_outages_raw` followed by
    :func:`~pge_outages.transform.transform_api_response`.

    Args:
        url: The full URL to fetch.  Defaults to :func:`build_api_url`.
        timeout: HTTP request timeout in seconds.

    Returns:
        A list of flat outage record dictionaries.
    """
    raw_data = fetch_outages_raw(url=url, timeout=timeout)
    return transform_api_response(raw_data)
