from __future__ import annotations


def make_remote_ref(tracker_type: str, remote_issue_key: str) -> str:
    return f"tracker:{tracker_type}:{remote_issue_key}"


def make_local_task_ref(task_id: str) -> str:
    return f"workx:task:{task_id}"


def validate_typed_ref(value: str) -> bool:
    parts = value.split(":")
    return len(parts) >= 3 and all(parts)
