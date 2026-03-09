from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
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


@dataclass
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


@dataclass
class EntityLink:
    id: str
    local_ref: str  # canonical typed_ref, e.g. agent-taskstate:task:local:*
    remote_ref: str  # canonical typed_ref, e.g. tracker:issue:jira:*
    link_role: str
    created_at: str
    updated_at: str
    metadata_json: str | None = None  # optional tracker_connection_id for disambiguation


@dataclass
class SyncEvent:
    id: str
    tracker_connection_id: str
    direction: str
    remote_ref: str  # canonical typed_ref, e.g. tracker:issue:jira:*
    local_ref: str | None  # canonical typed_ref, e.g. agent-taskstate:task:local:*
    event_type: str
    fingerprint: str | None
    payload_json: str
    status: str
    error_message: str | None
    occurred_at: str
    processed_at: str | None
    created_at: str


@dataclass
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


# P3: State History and Bundle Audit Models


@dataclass
class StateTransition:
    """状態遷移履歴（append-only）"""

    id: str
    entity_type: str  # 'sync_event', 'issue_cache', 'entity_link'
    entity_id: str
    from_status: str | None
    to_status: str
    reason: str | None
    actor_type: str  # 'system', 'user', 'agent'
    actor_id: str | None
    run_id: str | None
    changed_at: str
    created_at: str
    metadata_json: str | None = None


@dataclass
class ContextBundle:
    """監査情報付きコンテキストバンドル"""

    id: str
    purpose: str  # 'resume', 'handoff', 'checkpoint', 'audit'
    summary: str
    rebuild_level: str  # 'full', 'summary', 'minimal'
    raw_included: bool
    generator_version: str
    generated_at: str
    created_at: str
    decision_digest: str | None = None
    open_question_digest: str | None = None
    diagnostics_json: str | None = None


@dataclass
class ContextBundleSource:
    """バンドルのソース参照（append-only）"""

    id: str
    context_bundle_id: str
    typed_ref: str  # canonical 4-segment format
    source_kind: str  # 'evidence', 'artifact', 'decision', 'tracker_issue', 'task'
    selected_raw: bool
    created_at: str
    metadata_json: str | None = None
