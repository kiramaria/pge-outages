"""Shared test fixtures for PG&E outage tests."""

import pytest


@pytest.fixture()
def sample_api_response():
    """A minimal but realistic PG&E ArcGIS API response."""
    return {
        "features": [
            {
                "attributes": {
                    "F_OUTAGE_ID": "100001",
                    "OBJECTID": 12345,
                    "blueSkyNotificationSubscription": "some_value",
                    "OUTAGE_EXTENT": "DEVICE",
                    "OUTAGE_DEVICE_ID": "083531104-2101916543",
                    "OUTAGE_CIRCUIT_ID": 83531104,
                    "CREW_ETA": None,
                    "CREW_CURRENT_STATUS": "Crew On Site",
                    "OUTAGE_CAUSE": "PLNND SHUTDOWN",
                    "EST_CUSTOMERS": 68,
                    "OUTAGE_LATITUDE": 37.358,
                    "OUTAGE_LONGITUDE": -121.836,
                    "CITY": "San Jose",
                    "COUNTY": None,
                    "ZIP": None,
                    "DEVICE_COUNT": 0,
                    "OUTAGE_START": 1772473320000,
                    "OUTAGE_START_TEXT": "2026-03-02T17:42:00Z",
                    "LAST_UPDATE": 1772480947000,
                    "LAST_UPDATE_TEXT": "2026-03-02T19:49:07Z",
                    "CURRENT_ETOR": 1772478000000,
                    "CURRENT_ETOR_TEXT": "2026-03-02T19:00:00Z",
                    "AUTO_ETOR": 1772478000000,
                    "SPID": None,
                    "fts_flag": "N",
                },
                "geometry": {"x": -13562755.9893, "y": 4489124.143},
            },
            {
                "attributes": {
                    "F_OUTAGE_ID": "100002",
                    "OBJECTID": 12346,
                    "blueSkyNotificationSubscription": None,
                    "OUTAGE_EXTENT": "DEVICE",
                    "OUTAGE_DEVICE_ID": "099887766-5544332211",
                    "OUTAGE_CIRCUIT_ID": 99887766,
                    "CREW_ETA": 1772490000000,
                    "CREW_CURRENT_STATUS": "Crew En Route",
                    "OUTAGE_CAUSE": "EQUIPMENT",
                    "EST_CUSTOMERS": 150,
                    "OUTAGE_LATITUDE": 38.581,
                    "OUTAGE_LONGITUDE": -121.494,
                    "CITY": "Sacramento",
                    "COUNTY": "Sacramento",
                    "ZIP": "95814",
                    "DEVICE_COUNT": 1,
                    "OUTAGE_START": 1772470000000,
                    "OUTAGE_START_TEXT": "2026-03-02T16:46:40Z",
                    "LAST_UPDATE": 1772485000000,
                    "LAST_UPDATE_TEXT": "2026-03-02T20:56:40Z",
                    "CURRENT_ETOR": 1772496000000,
                    "CURRENT_ETOR_TEXT": "2026-03-03T00:00:00Z",
                    "AUTO_ETOR": 1772493000000,
                    "SPID": "SP12345",
                    "fts_flag": "N",
                },
                "geometry": {"x": -13527268.0, "y": 4658055.0},
            },
        ]
    }


@pytest.fixture()
def sample_flat_record():
    """A single flat outage record as it would appear in outages.json."""
    return {
        "F_OUTAGE_ID": "100001",
        "OUTAGE_EXTENT": "DEVICE",
        "OUTAGE_DEVICE_ID": "083531104-2101916543",
        "OUTAGE_CIRCUIT_ID": 83531104,
        "CREW_ETA": None,
        "CREW_CURRENT_STATUS": "Crew On Site",
        "OUTAGE_CAUSE": "PLNND SHUTDOWN",
        "EST_CUSTOMERS": 68,
        "OUTAGE_LATITUDE": 37.358,
        "OUTAGE_LONGITUDE": -121.836,
        "CITY": "San Jose",
        "COUNTY": None,
        "ZIP": None,
        "DEVICE_COUNT": 0,
        "OUTAGE_START": 1772473320000,
        "OUTAGE_START_TEXT": "2026-03-02T17:42:00Z",
        "LAST_UPDATE": 1772480947000,
        "LAST_UPDATE_TEXT": "2026-03-02T19:49:07Z",
        "CURRENT_ETOR": 1772478000000,
        "CURRENT_ETOR_TEXT": "2026-03-02T19:00:00Z",
        "AUTO_ETOR": 1772478000000,
        "SPID": None,
        "fts_flag": "N",
        "geometry_x": -13562755.9893,
        "geometry_y": 4489124.143,
    }


@pytest.fixture()
def sample_flat_records():
    """Two flat outage records for diff testing."""
    return [
        {
            "F_OUTAGE_ID": "100001",
            "OUTAGE_EXTENT": "DEVICE",
            "OUTAGE_DEVICE_ID": "083531104-2101916543",
            "OUTAGE_CIRCUIT_ID": 83531104,
            "CREW_CURRENT_STATUS": "Crew On Site",
            "OUTAGE_CAUSE": "PLNND SHUTDOWN",
            "EST_CUSTOMERS": 68,
            "OUTAGE_LATITUDE": 37.358,
            "OUTAGE_LONGITUDE": -121.836,
            "CITY": "San Jose",
            "OUTAGE_START": 1772473320000,
            "OUTAGE_START_TEXT": "2026-03-02T17:42:00Z",
            "LAST_UPDATE": 1772480947000,
            "LAST_UPDATE_TEXT": "2026-03-02T19:49:07Z",
            "geometry_x": -13562755.9893,
            "geometry_y": 4489124.143,
        },
        {
            "F_OUTAGE_ID": "100002",
            "OUTAGE_EXTENT": "DEVICE",
            "OUTAGE_DEVICE_ID": "099887766-5544332211",
            "OUTAGE_CIRCUIT_ID": 99887766,
            "CREW_CURRENT_STATUS": "Crew En Route",
            "OUTAGE_CAUSE": "EQUIPMENT",
            "EST_CUSTOMERS": 150,
            "OUTAGE_LATITUDE": 38.581,
            "OUTAGE_LONGITUDE": -121.494,
            "CITY": "Sacramento",
            "OUTAGE_START": 1772470000000,
            "OUTAGE_START_TEXT": "2026-03-02T16:46:40Z",
            "LAST_UPDATE": 1772485000000,
            "LAST_UPDATE_TEXT": "2026-03-02T20:56:40Z",
            "geometry_x": -13527268.0,
            "geometry_y": 4658055.0,
        },
    ]
