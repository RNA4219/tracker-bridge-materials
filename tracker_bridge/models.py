from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TrackerConnection:
    id: str
    tracker_type: str
    name: str
    base_url: str
    workspace_key: str | None
    project_key: str | None
    secret_ref: str | None
    is_enabled: bool
    created_at: str
    updated_at: str
    metadata_json: str | None = None


@dataclass(slots=True)
class IssueCache:
    id: str
    tracker_connection_id: str
    remote_issue_id: str
    remote_issue_key: str
    title: str
    status: str | None
    assignee: str | None
    reporter: str | None
    labels_json: str | None
    issue_type: str | None
    priority: str | None
    raw_json: str
    last_seen_at: str
    created_at: str
    updated_at: str


@dataclass(slots=True)
class EntityLink:
    id: str
    local_ref: str
    remote_ref: str
    link_role: str
    created_at: str
    updated_at: str
    metadata_json: str | None = None


@dataclass(slots=True)
class SyncEvent:
    id: str
    tracker_connection_id: str
    direction: str
    remote_ref: str
    local_ref: str | None
    event_type: str
    fingerprint: str | None
    payload_json: str
    status: str
    error_message: str | None
    occurred_at: str
    processed_at: str | None
    created_at: str


@dataclass(slots=True)
class NormalizedIssue:
    remote_issue_id: str
    remote_issue_key: str
    title: str
    status: str | None
    assignee: str | None
    reporter: str | None
    labels: list[str]
    issue_type: str | None
    priority: str | None
    raw: dict[str, Any]
