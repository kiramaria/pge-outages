"""Tests for pge_outages.fetch module.

Tests URL construction, HTTP error handling, and the fetch-and-transform
pipeline.  Network calls are mocked so tests run offline.
"""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from pge_outages.fetch import (
    BASE_URL,
    DEFAULT_PARAMS,
    DEFAULT_TIMEOUT,
    build_api_url,
    fetch_and_transform,
    fetch_outages_raw,
)


# ---------------------------------------------------------------------------
# build_api_url
# ---------------------------------------------------------------------------


class TestBuildApiUrl:
    """Tests for build_api_url()."""

    def test_contains_base_url(self):
        url = build_api_url(cache_bust_id="test-id")
        assert url.startswith(BASE_URL)

    def test_contains_params(self):
        url = build_api_url(cache_bust_id="test-id")
        assert DEFAULT_PARAMS in url

    def test_explicit_cache_bust(self):
        url = build_api_url(cache_bust_id="my-unique-id")
        assert url.endswith("&_my-unique-id")

    def test_auto_cache_bust_is_unique(self):
        url1 = build_api_url()
        url2 = build_api_url()
        # Each call should produce a different UUID
        assert url1 != url2

    def test_auto_cache_bust_format(self):
        """Auto-generated UUID should be in standard UUID4 format."""
        url = build_api_url()
        # Extract the cache-bust portion after &_
        cache_id = url.split("&_")[-1]
        # UUID4 format: 8-4-4-4-12 hex characters
        parts = cache_id.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]

    def test_empty_string_cache_bust(self):
        url = build_api_url(cache_bust_id="")
        assert url.endswith("&_")

    def test_url_is_string(self):
        assert isinstance(build_api_url(), str)


# ---------------------------------------------------------------------------
# fetch_outages_raw
# ---------------------------------------------------------------------------


class TestFetchOutagesRaw:
    """Tests for fetch_outages_raw()."""

    def _mock_urlopen(self, body: str, status: int = 200):
        """Create a mock for urllib.request.urlopen."""
        response = MagicMock()
        response.read.return_value = body.encode("utf-8")
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        response.status = status
        return response

    @patch("pge_outages.fetch.urlopen")
    def test_successful_fetch(self, mock_urlopen):
        payload = {"features": [{"attributes": {"F_OUTAGE_ID": "1"}, "geometry": None}]}
        mock_urlopen.return_value = self._mock_urlopen(json.dumps(payload))

        result = fetch_outages_raw(url="http://example.com/api")
        assert result == payload

    @patch("pge_outages.fetch.urlopen")
    def test_uses_default_url_when_none(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen('{"features": []}')

        fetch_outages_raw()
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert BASE_URL in request_obj.full_url

    @patch("pge_outages.fetch.urlopen")
    def test_passes_timeout(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen('{"features": []}')

        fetch_outages_raw(url="http://example.com/api", timeout=60)
        call_args = mock_urlopen.call_args
        assert call_args[1].get("timeout") == 60 or call_args[0][1] == 60

    @patch("pge_outages.fetch.urlopen")
    def test_connection_error_on_network_failure(self, mock_urlopen):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")

        with pytest.raises(ConnectionError, match="Failed to fetch"):
            fetch_outages_raw(url="http://example.com/api")

    @patch("pge_outages.fetch.urlopen")
    def test_connection_error_on_os_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Network unreachable")

        with pytest.raises(ConnectionError, match="Failed to fetch"):
            fetch_outages_raw(url="http://example.com/api")

    @patch("pge_outages.fetch.urlopen")
    def test_value_error_on_invalid_json(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen("not valid json {{{")

        with pytest.raises(ValueError, match="Invalid JSON"):
            fetch_outages_raw(url="http://example.com/api")

    @patch("pge_outages.fetch.urlopen")
    def test_value_error_on_empty_body(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen("")

        with pytest.raises(ValueError, match="Invalid JSON"):
            fetch_outages_raw(url="http://example.com/api")

    @patch("pge_outages.fetch.urlopen")
    def test_returns_dict(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen('{"features": []}')

        result = fetch_outages_raw(url="http://example.com/api")
        assert isinstance(result, dict)

    @patch("pge_outages.fetch.urlopen")
    def test_user_agent_header(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen('{"features": []}')

        fetch_outages_raw(url="http://example.com/api")
        request_obj = mock_urlopen.call_args[0][0]
        assert request_obj.get_header("User-agent") == "pge-outages/0.1"


# ---------------------------------------------------------------------------
# fetch_and_transform
# ---------------------------------------------------------------------------


class TestFetchAndTransform:
    """Tests for fetch_and_transform()."""

    def _mock_urlopen(self, body: str):
        response = MagicMock()
        response.read.return_value = body.encode("utf-8")
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        return response

    @patch("pge_outages.fetch.urlopen")
    def test_fetches_and_transforms(self, mock_urlopen):
        payload = {
            "features": [
                {
                    "attributes": {
                        "F_OUTAGE_ID": "1",
                        "OBJECTID": 99,
                        "blueSkyNotificationSubscription": "x",
                        "CITY": "SF",
                    },
                    "geometry": {"x": -100.0, "y": 50.0},
                }
            ]
        }
        mock_urlopen.return_value = self._mock_urlopen(json.dumps(payload))

        result = fetch_and_transform(url="http://example.com/api")
        assert len(result) == 1
        assert result[0]["F_OUTAGE_ID"] == "1"
        assert result[0]["CITY"] == "SF"
        assert result[0]["geometry_x"] == -100.0
        assert "OBJECTID" not in result[0]
        assert "blueSkyNotificationSubscription" not in result[0]

    @patch("pge_outages.fetch.urlopen")
    def test_empty_features(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_urlopen('{"features": []}')

        result = fetch_and_transform(url="http://example.com/api")
        assert result == []

    @patch("pge_outages.fetch.urlopen")
    def test_propagates_connection_error(self, mock_urlopen):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("fail")

        with pytest.raises(ConnectionError):
            fetch_and_transform(url="http://example.com/api")

    @patch("pge_outages.fetch.urlopen")
    def test_propagates_transform_error(self, mock_urlopen):
        # Valid JSON but missing 'features' key
        mock_urlopen.return_value = self._mock_urlopen('{"data": []}')

        with pytest.raises(KeyError, match="features"):
            fetch_and_transform(url="http://example.com/api")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for module-level constants."""

    def test_base_url_is_https(self):
        assert BASE_URL.startswith("https://")

    def test_base_url_is_arcgis(self):
        assert "arcgis" in BASE_URL

    def test_default_params_include_all_fields(self):
        assert "outFields=*" in DEFAULT_PARAMS

    def test_default_params_request_json(self):
        assert "f=pjson" in DEFAULT_PARAMS

    def test_default_timeout_is_positive(self):
        assert DEFAULT_TIMEOUT > 0
