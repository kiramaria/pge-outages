"""Diff utilities for comparing PG&E outage snapshots.

Provides logic for comparing two snapshots of outage data to identify
additions, removals, and changes — replicating the csv-diff comparison
used in the GitHub Actions workflow.
"""

import json
from typing import Any

# The field used as the unique key for matching records across snapshots
OUTAGE_KEY = "F_OUTAGE_ID"


def records_by_key(
    records: list[dict[str, Any]], key: str = OUTAGE_KEY
) -> dict[str, dict[str, Any]]:
    """Index a list of outage records by their key field.

    Args:
        records: List of outage record dictionaries.
        key: The field name to use as the unique identifier.

    Returns:
        Dict mapping key values to their record dictionaries.

    Raises:
        ValueError: If a record is missing the key field.
    """
    indexed = {}
    for record in records:
        if key not in record:
            raise ValueError(f"Record missing key field '{key}': {record}")
        key_value = str(record[key])
        indexed[key_value] = record
    return indexed


def find_added(
    old_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    key: str = OUTAGE_KEY,
) -> list[dict[str, Any]]:
    """Find records present in new snapshot but not in old.

    Args:
        old_records: Previous snapshot records.
        new_records: Current snapshot records.
        key: The field to use as unique identifier.

    Returns:
        List of newly added records.
    """
    old_keys = {str(r[key]) for r in old_records if key in r}
    return [r for r in new_records if key in r and str(r[key]) not in old_keys]


def find_removed(
    old_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    key: str = OUTAGE_KEY,
) -> list[dict[str, Any]]:
    """Find records present in old snapshot but not in new.

    Args:
        old_records: Previous snapshot records.
        new_records: Current snapshot records.
        key: The field to use as unique identifier.

    Returns:
        List of removed records.
    """
    new_keys = {str(r[key]) for r in new_records if key in r}
    return [r for r in old_records if key in r and str(r[key]) not in new_keys]


def find_changed(
    old_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    key: str = OUTAGE_KEY,
) -> list[dict[str, list[dict[str, Any]]]]:
    """Find records present in both snapshots but with changed values.

    Args:
        old_records: Previous snapshot records.
        new_records: Current snapshot records.
        key: The field to use as unique identifier.

    Returns:
        List of dicts with 'key', 'changes' (list of field changes),
        'old', and 'new' for each changed record.
    """
    old_indexed = records_by_key(old_records, key)
    new_indexed = records_by_key(new_records, key)

    changed = []
    for key_value in old_indexed:
        if key_value not in new_indexed:
            continue
        old_rec = old_indexed[key_value]
        new_rec = new_indexed[key_value]

        all_fields = sorted(set(old_rec.keys()) | set(new_rec.keys()))
        changes = []
        for field in all_fields:
            old_val = old_rec.get(field)
            new_val = new_rec.get(field)
            if old_val != new_val:
                changes.append({
                    "field": field,
                    "old": old_val,
                    "new": new_val,
                })

        if changes:
            changed.append({
                "key": key_value,
                "changes": changes,
                "old": old_rec,
                "new": new_rec,
            })

    return changed


def compute_diff(
    old_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    key: str = OUTAGE_KEY,
) -> dict[str, Any]:
    """Compute a full diff between two outage snapshots.

    This replicates the functionality of:
        csv-diff outages.json outages-new.json --key F_OUTAGE_ID --format json

    Args:
        old_records: Previous snapshot records.
        new_records: Current snapshot records.
        key: The field to use as unique identifier.

    Returns:
        Dict with 'added', 'removed', 'changed' keys and summary stats.
    """
    added = find_added(old_records, new_records, key)
    removed = find_removed(old_records, new_records, key)
    changed = find_changed(old_records, new_records, key)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": {
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
            "total_old": len(old_records),
            "total_new": len(new_records),
        },
    }


def format_diff_summary(diff: dict[str, Any]) -> str:
    """Format a diff result into a human-readable summary string.

    Args:
        diff: The result of compute_diff().

    Returns:
        A multi-line summary string.
    """
    summary = diff["summary"]
    lines = []

    if summary["added_count"]:
        lines.append(f"{summary['added_count']} row(s) added")
    if summary["removed_count"]:
        lines.append(f"{summary['removed_count']} row(s) removed")
    if summary["changed_count"]:
        lines.append(f"{summary['changed_count']} row(s) changed")

    if not lines:
        return "No changes detected"

    return ", ".join(lines)


def load_records_from_json(file_path: str) -> list[dict[str, Any]]:
    """Load outage records from a JSON file.

    Args:
        file_path: Path to the JSON file containing an array of records.

    Returns:
        List of outage record dictionaries.

    Raises:
        ValueError: If the file does not contain a JSON array.
    """
    with open(file_path, "r") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            f"Expected JSON array at top level, got {type(data).__name__}"
        )
    return data
