"""Tests for pge_outages.diff module.

Covers structured diff computation between outage snapshots, including
additions, removals, modifications, and commit message formatting.
"""

import json

import pytest

from pge_outages.diff import (
    DEFAULT_KEY,
    compute_diff,
    diff_to_json,
    format_diff_message,
)


# ---------------------------------------------------------------------------
# compute_diff
# ---------------------------------------------------------------------------


class TestComputeDiff:
    """Tests for compute_diff()."""

    def test_identical_snapshots(self, sample_flat_records):
        result = compute_diff(sample_flat_records, sample_flat_records)
        assert result["added"] == []
        assert result["removed"] == []
        assert result["changed"] == []

    def test_added_record(self, sample_flat_records):
        old = [sample_flat_records[0]]
        new = sample_flat_records[:]
        result = compute_diff(old, new)
        assert len(result["added"]) == 1
        assert result["added"][0]["F_OUTAGE_ID"] == "100002"
        assert result["removed"] == []

    def test_removed_record(self, sample_flat_records):
        old = sample_flat_records[:]
        new = [sample_flat_records[0]]
        result = compute_diff(old, new)
        assert len(result["removed"]) == 1
        assert result["removed"][0]["F_OUTAGE_ID"] == "100002"
        assert result["added"] == []

    def test_changed_record(self, sample_flat_records):
        old = sample_flat_records[:]
        new = [r.copy() for r in sample_flat_records]
        new[0]["EST_CUSTOMERS"] = 200  # Change a field
        result = compute_diff(old, new)
        assert len(result["changed"]) == 1
        assert result["added"] == []
        assert result["removed"] == []

    def test_all_records_added(self, sample_flat_records):
        """When old is empty, all new records appear as added."""
        result = compute_diff([], sample_flat_records)
        assert len(result["added"]) == 2
        assert result["removed"] == []
        assert result["changed"] == []
        # Each added entry is a dict mapping the key value to the record
        added_keys = {list(a.keys())[0] for a in result["added"]}
        assert added_keys == {"100001", "100002"}

    def test_all_records_removed(self, sample_flat_records):
        """When new is empty, all old records appear as removed."""
        result = compute_diff(sample_flat_records, [])
        assert len(result["removed"]) == 2
        assert result["added"] == []
        assert result["changed"] == []
        removed_keys = {list(r.keys())[0] for r in result["removed"]}
        assert removed_keys == {"100001", "100002"}

    def test_both_empty(self):
        result = compute_diff([], [])
        assert result["added"] == []
        assert result["removed"] == []
        assert result["changed"] == []

    def test_simultaneous_add_remove_change(self, sample_flat_records):
        old = sample_flat_records[:]
        # Remove record 100002, modify 100001, add a new one
        modified = sample_flat_records[0].copy()
        modified["EST_CUSTOMERS"] = 999
        new_record = sample_flat_records[1].copy()
        new_record["F_OUTAGE_ID"] = "100003"
        new = [modified, new_record]

        result = compute_diff(old, new)
        assert len(result["added"]) == 1
        assert len(result["removed"]) == 1
        assert len(result["changed"]) == 1

    def test_custom_key(self):
        old = [{"id": "A", "value": 1}]
        new = [{"id": "A", "value": 2}]
        result = compute_diff(old, new, key="id")
        assert len(result["changed"]) == 1

    def test_missing_key_in_old_raises(self):
        old = [{"NOT_THE_KEY": "1"}]
        new = [{"F_OUTAGE_ID": "1"}]
        with pytest.raises(ValueError, match="missing key field"):
            compute_diff(old, new)

    def test_missing_key_in_new_raises(self):
        old = [{"F_OUTAGE_ID": "1"}]
        new = [{"NOT_THE_KEY": "1"}]
        with pytest.raises(ValueError, match="missing key field"):
            compute_diff(old, new)

    def test_non_list_old_raises(self):
        with pytest.raises(TypeError, match="Expected list"):
            compute_diff("not a list", [])

    def test_non_list_new_raises(self):
        with pytest.raises(TypeError, match="Expected list"):
            compute_diff([], "not a list")

    def test_default_key_is_f_outage_id(self):
        assert DEFAULT_KEY == "F_OUTAGE_ID"


# ---------------------------------------------------------------------------
# format_diff_message
# ---------------------------------------------------------------------------


class TestFormatDiffMessage:
    """Tests for format_diff_message()."""

    def test_no_changes(self):
        diff = {"added": [], "removed": [], "changed": []}
        assert format_diff_message(diff) == ""

    def test_one_row_added(self):
        diff = {"added": [{"F_OUTAGE_ID": "1"}], "removed": [], "changed": []}
        result = format_diff_message(diff)
        assert result == "1 row added"

    def test_multiple_rows_added(self):
        diff = {
            "added": [{"F_OUTAGE_ID": "1"}, {"F_OUTAGE_ID": "2"}],
            "removed": [],
            "changed": [],
        }
        result = format_diff_message(diff)
        assert result == "2 rows added"

    def test_one_row_removed(self):
        diff = {"added": [], "removed": [{"F_OUTAGE_ID": "1"}], "changed": []}
        assert format_diff_message(diff) == "1 row removed"

    def test_multiple_rows_removed(self):
        diff = {
            "added": [],
            "removed": [{"F_OUTAGE_ID": "1"}, {"F_OUTAGE_ID": "2"}, {"F_OUTAGE_ID": "3"}],
            "changed": [],
        }
        assert format_diff_message(diff) == "3 rows removed"

    def test_one_row_changed(self):
        diff = {"added": [], "removed": [], "changed": [{"key": "1", "changes": {}}]}
        assert format_diff_message(diff) == "1 row changed"

    def test_combined_message(self):
        diff = {
            "added": [{"F_OUTAGE_ID": "1"}],
            "removed": [{"F_OUTAGE_ID": "2"}],
            "changed": [{"key": "3", "changes": {}}],
        }
        result = format_diff_message(diff)
        assert result == "1 row added, 1 row removed, 1 row changed"

    def test_added_and_changed(self):
        diff = {
            "added": [{"id": "1"}, {"id": "2"}],
            "removed": [],
            "changed": [{"key": "3", "changes": {}}],
        }
        result = format_diff_message(diff)
        assert result == "2 rows added, 1 row changed"

    def test_missing_keys_treated_as_empty(self):
        """Gracefully handle diff results without all keys."""
        result = format_diff_message({})
        assert result == ""


# ---------------------------------------------------------------------------
# diff_to_json
# ---------------------------------------------------------------------------


class TestDiffToJson:
    """Tests for diff_to_json()."""

    def test_produces_valid_json(self):
        diff = {"added": [], "removed": [], "changed": []}
        result = diff_to_json(diff)
        parsed = json.loads(result)
        assert parsed == diff

    def test_preserves_content(self, sample_flat_records):
        diff = {
            "added": [sample_flat_records[0]],
            "removed": [],
            "changed": [],
        }
        result = diff_to_json(diff)
        parsed = json.loads(result)
        assert parsed["added"][0]["F_OUTAGE_ID"] == "100001"

    def test_indented_output(self):
        diff = {"added": [], "removed": [], "changed": []}
        result = diff_to_json(diff)
        # Indented JSON should have newlines
        assert "\n" in result

    def test_empty_diff(self):
        result = diff_to_json({})
        assert json.loads(result) == {}
