"""Compute structured diffs between outage snapshots.

Wraps the ``csv-diff`` library to compare two lists of outage records
by their ``F_OUTAGE_ID`` key and produce a structured diff suitable
for use as a Git commit message.
"""

import io
import json
from typing import Any

from csv_diff import compare, load_json

DEFAULT_KEY = "F_OUTAGE_ID"


def compute_diff(
    old_records: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    key: str = DEFAULT_KEY,
) -> dict[str, Any]:
    """Compute a structured diff between two outage snapshots.

    Uses ``csv-diff``'s :func:`compare` to find added, removed, and
    changed records based on the given key field.

    Args:
        old_records: The previous list of outage records.
        new_records: The current list of outage records.
        key: The field name used to match records across snapshots.
            Defaults to ``F_OUTAGE_ID``.

    Returns:
        A dictionary with ``added``, ``removed``, and ``changed`` keys
        describing the differences.

    Raises:
        TypeError: If either argument is not a list.
        ValueError: If a record is missing the specified key field.
    """
    if not isinstance(old_records, list):
        raise TypeError(f"Expected list for old_records, got {type(old_records).__name__}")
    if not isinstance(new_records, list):
        raise TypeError(f"Expected list for new_records, got {type(new_records).__name__}")

    # Validate that key field exists in all records
    for i, record in enumerate(old_records):
        if key not in record:
            raise ValueError(f"old_records[{i}] is missing key field '{key}'")
    for i, record in enumerate(new_records):
        if key not in record:
            raise ValueError(f"new_records[{i}] is missing key field '{key}'")

    # csv_diff.compare() raises StopIteration when either side is empty
    # because it tries to read column names from the first record.
    # Handle those edge cases explicitly.
    if not old_records and not new_records:
        return {"added": [], "removed": [], "changed": [], "columns_added": [], "columns_removed": []}
    if not old_records:
        return {
            "added": [{str(r[key]): r} for r in new_records],
            "removed": [],
            "changed": [],
            "columns_added": [],
            "columns_removed": [],
        }
    if not new_records:
        return {
            "added": [],
            "removed": [{str(r[key]): r} for r in old_records],
            "changed": [],
            "columns_added": [],
            "columns_removed": [],
        }

    def _to_file(records: list[dict[str, Any]]) -> io.StringIO:
        return io.StringIO(json.dumps(records))

    result = compare(
        load_json(_to_file(old_records), key=key),
        load_json(_to_file(new_records), key=key),
    )

    return result


def format_diff_message(diff_result: dict[str, Any]) -> str:
    """Format a diff result as a human-readable commit message.

    Produces a summary string indicating the number of added, removed,
    and changed rows, matching the style used in the fetch workflow's
    ``csv-diff --format json`` output.

    Args:
        diff_result: The output of :func:`compute_diff`.

    Returns:
        A formatted string suitable for a Git commit message.
        Returns an empty string if there are no changes.
    """
    parts: list[str] = []

    added = diff_result.get("added", [])
    removed = diff_result.get("removed", [])
    changed = diff_result.get("changed", [])

    if added:
        count = len(added)
        parts.append(f"{count} row{'s' if count != 1 else ''} added")

    if removed:
        count = len(removed)
        parts.append(f"{count} row{'s' if count != 1 else ''} removed")

    if changed:
        count = len(changed)
        parts.append(f"{count} row{'s' if count != 1 else ''} changed")

    return ", ".join(parts)


def diff_to_json(diff_result: dict[str, Any]) -> str:
    """Serialize a diff result to a JSON string.

    This mirrors the ``csv-diff --format json`` output used by the
    fetch workflow to generate commit messages.

    Args:
        diff_result: The output of :func:`compute_diff`.

    Returns:
        A JSON-formatted string.
    """
    return json.dumps(diff_result, indent=2)
