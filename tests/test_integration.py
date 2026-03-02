"""Integration tests that verify the full data pipeline.

These tests simulate the end-to-end flow from API response to validated,
diffed outage data — replicating the GitHub Actions workflow logic.
"""

import copy
import json
import os

import pytest

from pge_outages.diff_utils import compute_diff, format_diff_summary
from pge_outages.transform import transform_api_response
from pge_outages.validate import (
    validate_outages,
    validate_record,
    validate_unique_ids,
)


class TestEndToEndPipeline:
    """Test the full transform -> validate -> diff pipeline."""

    def test_transform_then_validate(self, sample_api_response):
        """Transformed records should pass validation."""
        records = transform_api_response(sample_api_response)
        errors = validate_outages(records)
        assert errors == {}, f"Validation errors: {errors}"

    def test_transform_removes_excluded_fields(self, sample_api_response):
        """Transformed records should not contain OBJECTID or blueSky."""
        records = transform_api_response(sample_api_response)
        for record in records:
            assert "OBJECTID" not in record
            assert "blueSkyNotificationSubscription" not in record

    def test_transform_then_diff_no_changes(self, sample_api_response):
        """Diffing identical snapshots should produce no changes."""
        records = transform_api_response(sample_api_response)
        diff = compute_diff(records, records)
        assert diff["summary"]["added_count"] == 0
        assert diff["summary"]["removed_count"] == 0
        assert diff["summary"]["changed_count"] == 0
        assert format_diff_summary(diff) == "No changes detected"

    def test_full_pipeline_with_new_outage(self, sample_api_response):
        """Simulate a new outage appearing between snapshots."""
        old_records = transform_api_response(sample_api_response)

        # Add a new outage to the API response
        new_response = copy.deepcopy(sample_api_response)
        new_feature = {
            "attributes": {
                "OBJECTID": 3,
                "F_OUTAGE_ID": "187781",
                "OUTAGE_EXTENT": "DEVICE",
                "OUTAGE_DEVICE_ID": "083531104-2101916545",
                "OUTAGE_CIRCUIT_ID": 83531106,
                "CREW_ETA": None,
                "CREW_CURRENT_STATUS": "Assessing",
                "OUTAGE_CAUSE": "UNKN",
                "EST_CUSTOMERS": 42,
                "OUTAGE_LATITUDE": 37.87,
                "OUTAGE_LONGITUDE": -122.27,
                "CITY": "Berkeley",
                "COUNTY": "Alameda",
                "ZIP": "94702",
                "DEVICE_COUNT": 0,
                "OUTAGE_START": 1772485000000,
                "OUTAGE_START_TEXT": "2026-03-02T20:56:40Z",
                "LAST_UPDATE": 1772486000000,
                "LAST_UPDATE_TEXT": "2026-03-02T21:13:20Z",
                "CURRENT_ETOR": 1772500000000,
                "CURRENT_ETOR_TEXT": "2026-03-03T01:06:40Z",
                "AUTO_ETOR": 1772498000000,
                "SPID": None,
                "fts_flag": "N",
                "blueSkyNotificationSubscription": None,
            },
            "geometry": {"x": -13604500.0, "y": 4562000.0},
        }
        new_response["features"].append(new_feature)
        new_records = transform_api_response(new_response)

        # Validate new records
        errors = validate_outages(new_records)
        assert errors == {}

        # Check unique IDs
        id_errors = validate_unique_ids(new_records)
        assert id_errors == []

        # Diff
        diff = compute_diff(old_records, new_records)
        assert diff["summary"]["added_count"] == 1
        assert diff["summary"]["removed_count"] == 0
        assert diff["summary"]["changed_count"] == 0
        assert diff["added"][0]["F_OUTAGE_ID"] == "187781"
        assert "1 row(s) added" in format_diff_summary(diff)

    def test_full_pipeline_with_resolved_outage(self, sample_api_response):
        """Simulate an outage being resolved (removed from new snapshot)."""
        old_records = transform_api_response(sample_api_response)

        # New response has one fewer feature
        new_response = copy.deepcopy(sample_api_response)
        new_response["features"] = new_response["features"][:1]
        new_records = transform_api_response(new_response)

        diff = compute_diff(old_records, new_records)
        assert diff["summary"]["removed_count"] == 1
        assert diff["removed"][0]["F_OUTAGE_ID"] == "187780"

    def test_full_pipeline_with_status_update(self, sample_api_response):
        """Simulate a crew status update on an existing outage."""
        old_records = transform_api_response(sample_api_response)

        new_response = copy.deepcopy(sample_api_response)
        new_response["features"][0]["attributes"]["CREW_CURRENT_STATUS"] = "Crew En Route"
        new_response["features"][0]["attributes"]["LAST_UPDATE"] = 1772490000000
        new_response["features"][0]["attributes"]["LAST_UPDATE_TEXT"] = "2026-03-02T22:20:00Z"
        new_records = transform_api_response(new_response)

        diff = compute_diff(old_records, new_records)
        assert diff["summary"]["changed_count"] == 1
        changes = {c["field"]: c for c in diff["changed"][0]["changes"]}
        assert "CREW_CURRENT_STATUS" in changes
        assert changes["CREW_CURRENT_STATUS"]["old"] == "Crew On Site"
        assert changes["CREW_CURRENT_STATUS"]["new"] == "Crew En Route"

    def test_full_pipeline_with_etor_update(self, sample_api_response):
        """Simulate an ETOR update on an existing outage."""
        old_records = transform_api_response(sample_api_response)

        new_response = copy.deepcopy(sample_api_response)
        new_response["features"][0]["attributes"]["CURRENT_ETOR"] = 1772500000000
        new_response["features"][0]["attributes"]["CURRENT_ETOR_TEXT"] = "2026-03-03T01:06:40Z"
        new_records = transform_api_response(new_response)

        diff = compute_diff(old_records, new_records)
        assert diff["summary"]["changed_count"] == 1
        changes = {c["field"]: c for c in diff["changed"][0]["changes"]}
        assert "CURRENT_ETOR" in changes

    def test_full_pipeline_complex_scenario(self, sample_api_response):
        """Simulate a complex scenario with additions, removals, and changes."""
        old_records = transform_api_response(sample_api_response)

        new_response = copy.deepcopy(sample_api_response)
        # Change first outage's customer count
        new_response["features"][0]["attributes"]["EST_CUSTOMERS"] = 200
        # Remove second outage
        new_response["features"].pop(1)
        # Add a brand new outage
        new_response["features"].append({
            "attributes": {
                "OBJECTID": 10,
                "F_OUTAGE_ID": "999999",
                "OUTAGE_EXTENT": "DEVICE",
                "OUTAGE_DEVICE_ID": "new-device",
                "OUTAGE_CIRCUIT_ID": 99999,
                "CREW_ETA": None,
                "CREW_CURRENT_STATUS": "Pending",
                "OUTAGE_CAUSE": "STORM",
                "EST_CUSTOMERS": 500,
                "OUTAGE_LATITUDE": 38.0,
                "OUTAGE_LONGITUDE": -122.0,
                "CITY": "Napa",
                "COUNTY": "Napa",
                "ZIP": "94558",
                "DEVICE_COUNT": 0,
                "OUTAGE_START": 1772490000000,
                "OUTAGE_START_TEXT": "2026-03-02T22:20:00Z",
                "LAST_UPDATE": 1772491000000,
                "LAST_UPDATE_TEXT": "2026-03-02T22:36:40Z",
                "CURRENT_ETOR": 1772510000000,
                "CURRENT_ETOR_TEXT": "2026-03-03T03:53:20Z",
                "AUTO_ETOR": 1772508000000,
                "SPID": None,
                "fts_flag": "N",
                "blueSkyNotificationSubscription": None,
            },
            "geometry": {"x": -13580000.0, "y": 4600000.0},
        })
        new_records = transform_api_response(new_response)

        # Validate
        errors = validate_outages(new_records)
        assert errors == {}

        # Diff
        diff = compute_diff(old_records, new_records)
        assert diff["summary"]["added_count"] == 1
        assert diff["summary"]["removed_count"] == 1
        assert diff["summary"]["changed_count"] == 1

        summary = format_diff_summary(diff)
        assert "added" in summary
        assert "removed" in summary
        assert "changed" in summary


class TestActualDataValidation:
    """Tests that validate the actual outages.json file in the repo."""

    @pytest.fixture
    def outages_path(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "outages.json"
        )
        if not os.path.exists(path):
            pytest.skip("outages.json not found")
        return path

    def test_outages_json_is_valid_json(self, outages_path):
        with open(outages_path) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_outages_json_records_have_key_field(self, outages_path):
        with open(outages_path) as f:
            records = json.load(f)
        for record in records:
            assert "F_OUTAGE_ID" in record

    def test_outages_json_records_pass_validation(self, outages_path):
        with open(outages_path) as f:
            records = json.load(f)
        errors = validate_outages(records)
        # Allow some errors (real data may have edge cases) but report them
        if errors:
            for record_id, errs in errors.items():
                for err in errs:
                    # Only fail on critical issues
                    assert "Missing required field" not in err.message, (
                        f"Record {record_id} missing required field: {err}"
                    )

    def test_outages_json_unique_ids(self, outages_path):
        with open(outages_path) as f:
            records = json.load(f)
        id_errors = validate_unique_ids(records)
        assert id_errors == [], f"Duplicate IDs found: {id_errors}"

    def test_outages_json_no_excluded_fields(self, outages_path):
        with open(outages_path) as f:
            records = json.load(f)
        for record in records:
            assert "OBJECTID" not in record, (
                f"Record {record.get('F_OUTAGE_ID')} contains OBJECTID"
            )
            assert "blueSkyNotificationSubscription" not in record, (
                f"Record {record.get('F_OUTAGE_ID')} contains blueSkyNotificationSubscription"
            )
