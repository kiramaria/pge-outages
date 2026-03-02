"""Tests for the diff utilities module."""

import json
import os
import tempfile

import pytest

from pge_outages.diff_utils import (
    OUTAGE_KEY,
    compute_diff,
    find_added,
    find_changed,
    find_removed,
    format_diff_summary,
    load_records_from_json,
    records_by_key,
)


class TestRecordsByKey:
    """Tests for records_by_key()."""

    def test_indexes_by_default_key(self, sample_flat_records):
        indexed = records_by_key(sample_flat_records)
        assert "187779" in indexed
        assert "187780" in indexed
        assert indexed["187779"]["CITY"] == "San Jose"

    def test_indexes_by_custom_key(self):
        records = [
            {"CITY": "Oakland", "ZIP": "94601"},
            {"CITY": "Berkeley", "ZIP": "94702"},
        ]
        indexed = records_by_key(records, key="CITY")
        assert "Oakland" in indexed
        assert "Berkeley" in indexed

    def test_empty_list_returns_empty_dict(self):
        assert records_by_key([]) == {}

    def test_raises_on_missing_key(self):
        records = [{"CITY": "Oakland"}]
        with pytest.raises(ValueError, match="missing key field"):
            records_by_key(records, key="F_OUTAGE_ID")

    def test_key_values_are_strings(self):
        records = [{"F_OUTAGE_ID": 12345, "CITY": "Test"}]
        indexed = records_by_key(records)
        assert "12345" in indexed


class TestFindAdded:
    """Tests for find_added()."""

    def test_no_additions(self, sample_flat_records):
        added = find_added(sample_flat_records, sample_flat_records)
        assert added == []

    def test_new_record_detected(self, sample_flat_records):
        old = [sample_flat_records[0]]
        new = sample_flat_records
        added = find_added(old, new)
        assert len(added) == 1
        assert added[0]["F_OUTAGE_ID"] == "187780"

    def test_all_new_records(self, sample_flat_records):
        added = find_added([], sample_flat_records)
        assert len(added) == 2

    def test_empty_new_records(self, sample_flat_records):
        added = find_added(sample_flat_records, [])
        assert added == []

    def test_both_empty(self):
        assert find_added([], []) == []


class TestFindRemoved:
    """Tests for find_removed()."""

    def test_no_removals(self, sample_flat_records):
        removed = find_removed(sample_flat_records, sample_flat_records)
        assert removed == []

    def test_record_removed_detected(self, sample_flat_records):
        old = sample_flat_records
        new = [sample_flat_records[0]]
        removed = find_removed(old, new)
        assert len(removed) == 1
        assert removed[0]["F_OUTAGE_ID"] == "187780"

    def test_all_records_removed(self, sample_flat_records):
        removed = find_removed(sample_flat_records, [])
        assert len(removed) == 2

    def test_empty_old_records(self, sample_flat_records):
        removed = find_removed([], sample_flat_records)
        assert removed == []

    def test_both_empty(self):
        assert find_removed([], []) == []


class TestFindChanged:
    """Tests for find_changed()."""

    def test_no_changes(self, sample_flat_records):
        changed = find_changed(sample_flat_records, sample_flat_records)
        assert changed == []

    def test_field_value_changed(self, sample_flat_records):
        import copy
        new_records = copy.deepcopy(sample_flat_records)
        new_records[0]["EST_CUSTOMERS"] = 100  # was 68
        changed = find_changed(sample_flat_records, new_records)
        assert len(changed) == 1
        assert changed[0]["key"] == "187779"
        field_changes = {c["field"]: c for c in changed[0]["changes"]}
        assert "EST_CUSTOMERS" in field_changes
        assert field_changes["EST_CUSTOMERS"]["old"] == 68
        assert field_changes["EST_CUSTOMERS"]["new"] == 100

    def test_multiple_fields_changed(self, sample_flat_records):
        import copy
        new_records = copy.deepcopy(sample_flat_records)
        new_records[0]["EST_CUSTOMERS"] = 100
        new_records[0]["CREW_CURRENT_STATUS"] = "Crew En Route"
        changed = find_changed(sample_flat_records, new_records)
        assert len(changed) == 1
        assert len(changed[0]["changes"]) == 2

    def test_multiple_records_changed(self, sample_flat_records):
        import copy
        new_records = copy.deepcopy(sample_flat_records)
        new_records[0]["EST_CUSTOMERS"] = 100
        new_records[1]["CITY"] = "Davis"
        changed = find_changed(sample_flat_records, new_records)
        assert len(changed) == 2

    def test_added_record_not_in_changed(self, sample_flat_records):
        old = [sample_flat_records[0]]
        new = sample_flat_records
        changed = find_changed(old, new)
        assert changed == []

    def test_removed_record_not_in_changed(self, sample_flat_records):
        old = sample_flat_records
        new = [sample_flat_records[0]]
        changed = find_changed(old, new)
        assert changed == []

    def test_null_to_value_detected(self, sample_flat_records):
        import copy
        new_records = copy.deepcopy(sample_flat_records)
        new_records[0]["CREW_ETA"] = 1772490000000  # was None
        changed = find_changed(sample_flat_records, new_records)
        assert len(changed) == 1
        field_changes = {c["field"]: c for c in changed[0]["changes"]}
        assert "CREW_ETA" in field_changes
        assert field_changes["CREW_ETA"]["old"] is None

    def test_value_to_null_detected(self, sample_flat_records):
        import copy
        new_records = copy.deepcopy(sample_flat_records)
        new_records[1]["CREW_ETA"] = None  # was 1772490000000
        changed = find_changed(sample_flat_records, new_records)
        assert len(changed) == 1
        field_changes = {c["field"]: c for c in changed[0]["changes"]}
        assert "CREW_ETA" in field_changes
        assert field_changes["CREW_ETA"]["new"] is None

    def test_both_empty_no_changes(self):
        assert find_changed([], []) == []

    def test_includes_old_and_new_records(self, sample_flat_records):
        import copy
        new_records = copy.deepcopy(sample_flat_records)
        new_records[0]["EST_CUSTOMERS"] = 100
        changed = find_changed(sample_flat_records, new_records)
        assert "old" in changed[0]
        assert "new" in changed[0]
        assert changed[0]["old"]["EST_CUSTOMERS"] == 68
        assert changed[0]["new"]["EST_CUSTOMERS"] == 100


class TestComputeDiff:
    """Tests for compute_diff()."""

    def test_no_changes_diff(self, sample_flat_records):
        diff = compute_diff(sample_flat_records, sample_flat_records)
        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["changed"] == []
        assert diff["summary"]["added_count"] == 0
        assert diff["summary"]["removed_count"] == 0
        assert diff["summary"]["changed_count"] == 0

    def test_additions_in_diff(self, sample_flat_records):
        diff = compute_diff([], sample_flat_records)
        assert diff["summary"]["added_count"] == 2
        assert diff["summary"]["total_old"] == 0
        assert diff["summary"]["total_new"] == 2

    def test_removals_in_diff(self, sample_flat_records):
        diff = compute_diff(sample_flat_records, [])
        assert diff["summary"]["removed_count"] == 2

    def test_mixed_changes(self, sample_flat_records):
        import copy
        new_records = copy.deepcopy(sample_flat_records)
        # Change first record
        new_records[0]["EST_CUSTOMERS"] = 100
        # Remove second, add a new one
        new_records[1] = {
            "F_OUTAGE_ID": "999999",
            "CITY": "New City",
            "EST_CUSTOMERS": 50,
        }
        diff = compute_diff(sample_flat_records, new_records)
        assert diff["summary"]["added_count"] == 1
        assert diff["summary"]["removed_count"] == 1
        assert diff["summary"]["changed_count"] == 1

    def test_both_empty(self):
        diff = compute_diff([], [])
        assert diff["summary"]["added_count"] == 0
        assert diff["summary"]["removed_count"] == 0
        assert diff["summary"]["changed_count"] == 0

    def test_summary_totals(self, sample_flat_records):
        diff = compute_diff(sample_flat_records, sample_flat_records)
        assert diff["summary"]["total_old"] == 2
        assert diff["summary"]["total_new"] == 2


class TestFormatDiffSummary:
    """Tests for format_diff_summary()."""

    def test_no_changes(self):
        diff = {
            "added": [], "removed": [], "changed": [],
            "summary": {
                "added_count": 0, "removed_count": 0, "changed_count": 0,
                "total_old": 5, "total_new": 5,
            },
        }
        assert format_diff_summary(diff) == "No changes detected"

    def test_only_additions(self):
        diff = {
            "added": [{}], "removed": [], "changed": [],
            "summary": {
                "added_count": 1, "removed_count": 0, "changed_count": 0,
                "total_old": 5, "total_new": 6,
            },
        }
        assert "1 row(s) added" in format_diff_summary(diff)
        assert "removed" not in format_diff_summary(diff)

    def test_only_removals(self):
        diff = {
            "added": [], "removed": [{}], "changed": [],
            "summary": {
                "added_count": 0, "removed_count": 1, "changed_count": 0,
                "total_old": 5, "total_new": 4,
            },
        }
        assert "1 row(s) removed" in format_diff_summary(diff)
        assert "added" not in format_diff_summary(diff)

    def test_only_changes(self):
        diff = {
            "added": [], "removed": [], "changed": [{}],
            "summary": {
                "added_count": 0, "removed_count": 0, "changed_count": 1,
                "total_old": 5, "total_new": 5,
            },
        }
        assert "1 row(s) changed" in format_diff_summary(diff)

    def test_all_types(self):
        diff = {
            "added": [{}] * 3, "removed": [{}] * 2, "changed": [{}] * 1,
            "summary": {
                "added_count": 3, "removed_count": 2, "changed_count": 1,
                "total_old": 10, "total_new": 11,
            },
        }
        summary = format_diff_summary(diff)
        assert "3 row(s) added" in summary
        assert "2 row(s) removed" in summary
        assert "1 row(s) changed" in summary

    def test_multiple_counts(self):
        diff = {
            "added": [{}] * 10, "removed": [], "changed": [{}] * 5,
            "summary": {
                "added_count": 10, "removed_count": 0, "changed_count": 5,
                "total_old": 20, "total_new": 25,
            },
        }
        summary = format_diff_summary(diff)
        assert "10 row(s) added" in summary
        assert "5 row(s) changed" in summary
        assert "removed" not in summary


class TestLoadRecordsFromJson:
    """Tests for load_records_from_json()."""

    def test_loads_valid_json_array(self, tmp_path):
        data = [{"F_OUTAGE_ID": "1", "CITY": "Test"}]
        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(data))
        result = load_records_from_json(str(file_path))
        assert result == data

    def test_loads_empty_array(self, tmp_path):
        file_path = tmp_path / "empty.json"
        file_path.write_text("[]")
        result = load_records_from_json(str(file_path))
        assert result == []

    def test_raises_on_non_array(self, tmp_path):
        file_path = tmp_path / "obj.json"
        file_path.write_text('{"key": "value"}')
        with pytest.raises(ValueError, match="Expected JSON array"):
            load_records_from_json(str(file_path))

    def test_raises_on_invalid_json(self, tmp_path):
        file_path = tmp_path / "bad.json"
        file_path.write_text("not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_records_from_json(str(file_path))

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_records_from_json("/nonexistent/path.json")

    def test_loads_actual_outages_file(self):
        """Integration test: verify the actual outages.json can be loaded."""
        outages_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "outages.json"
        )
        if os.path.exists(outages_path):
            records = load_records_from_json(outages_path)
            assert isinstance(records, list)
            # Verify each record has the key field
            for record in records:
                assert "F_OUTAGE_ID" in record
