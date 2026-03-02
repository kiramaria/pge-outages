"""
Shared test fixtures for PG&E outage processor tests.
"""

import pytest


@pytest.fixture
def sample_raw_feature():
    """A single raw ArcGIS feature as returned by the API."""
    return {
        "attributes": {
            "OBJECTID": 42,
            "blueSkyNotificationSubscription": "some_value",
            "F_OUTAGE_ID": "187779",
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
        "geometry": {
            "x": -13562755.9893,
            "y": 4489124.143,
        },
    }


@pytest.fixture
def sample_raw_response(sample_raw_feature):
    """A minimal raw ArcGIS API response with one feature."""
    return {"features": [sample_raw_feature]}


@pytest.fixture
def sample_normalized_record():
    """An expected normalized/flat outage record after transformation."""
    return {
        "F_OUTAGE_ID": "187779",
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


@pytest.fixture
def sample_multi_feature_response():
    """A raw API response with multiple features including different cities/causes."""
    return {
        "features": [
            {
                "attributes": {
                    "OBJECTID": 1,
                    "blueSkyNotificationSubscription": "x",
                    "F_OUTAGE_ID": "100001",
                    "OUTAGE_EXTENT": "DEVICE",
                    "OUTAGE_DEVICE_ID": "dev-001",
                    "OUTAGE_CIRCUIT_ID": 1001,
                    "CREW_ETA": None,
                    "CREW_CURRENT_STATUS": "Crew On Site",
                    "OUTAGE_CAUSE": "PLNND SHUTDOWN",
                    "EST_CUSTOMERS": 50,
                    "OUTAGE_LATITUDE": 37.5,
                    "OUTAGE_LONGITUDE": -122.0,
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
                "geometry": {"x": -13562755.0, "y": 4489124.0},
            },
            {
                "attributes": {
                    "OBJECTID": 2,
                    "blueSkyNotificationSubscription": "y",
                    "F_OUTAGE_ID": "100002",
                    "OUTAGE_EXTENT": "DEVICE",
                    "OUTAGE_DEVICE_ID": "dev-002",
                    "OUTAGE_CIRCUIT_ID": 2002,
                    "CREW_ETA": 1772490000000,
                    "CREW_CURRENT_STATUS": "Crew En Route",
                    "OUTAGE_CAUSE": "EQUIP FAIL",
                    "EST_CUSTOMERS": 120,
                    "OUTAGE_LATITUDE": 38.0,
                    "OUTAGE_LONGITUDE": -121.5,
                    "CITY": "Sacramento",
                    "COUNTY": "Sacramento",
                    "ZIP": "95814",
                    "DEVICE_COUNT": 1,
                    "OUTAGE_START": 1772470000000,
                    "OUTAGE_START_TEXT": "2026-03-02T16:46:40Z",
                    "LAST_UPDATE": 1772481000000,
                    "LAST_UPDATE_TEXT": "2026-03-02T19:50:00Z",
                    "CURRENT_ETOR": 1772495000000,
                    "CURRENT_ETOR_TEXT": "2026-03-02T23:43:20Z",
                    "AUTO_ETOR": None,
                    "SPID": "SP12345",
                    "fts_flag": "Y",
                },
                "geometry": {"x": -13530000.0, "y": 4550000.0},
            },
            {
                "attributes": {
                    "OBJECTID": 3,
                    "blueSkyNotificationSubscription": "z",
                    "F_OUTAGE_ID": "100003",
                    "OUTAGE_EXTENT": "DEVICE",
                    "OUTAGE_DEVICE_ID": "dev-003",
                    "OUTAGE_CIRCUIT_ID": 3003,
                    "CREW_ETA": None,
                    "CREW_CURRENT_STATUS": "Assigned",
                    "OUTAGE_CAUSE": "PLNND SHUTDOWN",
                    "EST_CUSTOMERS": 30,
                    "OUTAGE_LATITUDE": 37.8,
                    "OUTAGE_LONGITUDE": -122.4,
                    "CITY": "San Francisco",
                    "COUNTY": "San Francisco",
                    "ZIP": "94102",
                    "DEVICE_COUNT": 0,
                    "OUTAGE_START": 1772475000000,
                    "OUTAGE_START_TEXT": "2026-03-02T18:10:00Z",
                    "LAST_UPDATE": 1772482000000,
                    "LAST_UPDATE_TEXT": "2026-03-02T20:06:40Z",
                    "CURRENT_ETOR": 1772500000000,
                    "CURRENT_ETOR_TEXT": "2026-03-03T01:06:40Z",
                    "AUTO_ETOR": 1772500000000,
                    "SPID": None,
                    "fts_flag": "N",
                },
                "geometry": {"x": -13627000.0, "y": 4547000.0},
            },
        ]
    }


@pytest.fixture
def sample_polygon_feature():
    """A raw ArcGIS polygon feature (should be filtered out)."""
    return {
        "attributes": {
            "OBJECTID": 99,
            "F_OUTAGE_ID": "999999",
            "OUTAGE_EXTENT": "AREA",
        },
        "geometry": {
            "rings": [
                [[-122.0, 37.0], [-122.0, 38.0], [-121.0, 38.0], [-121.0, 37.0]]
            ]
        },
    }


@pytest.fixture
def sample_point_feature():
    """A raw ArcGIS point feature (should be kept)."""
    return {
        "attributes": {
            "OBJECTID": 1,
            "F_OUTAGE_ID": "100001",
            "OUTAGE_EXTENT": "DEVICE",
        },
        "geometry": {
            "x": -13562755.0,
            "y": 4489124.0,
        },
    }
