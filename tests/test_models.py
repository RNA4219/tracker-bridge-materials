"""Tests for models module."""
from __future__ import annotations

from tracker_bridge.models import (
    EntityLink,
    IssueCache,
    NormalizedIssue,
    SyncEvent,
    TrackerConnection,
)


class TestTrackerConnection:
    def test_create_minimal(self) -> None:
        model = TrackerConnection(
            id="test-id",
            tracker_type="jira",
            name="Test Connection",
            base_url="https://example.atlassian.net",
            workspace_key=None,
            project_key=None,
            secret_ref=None,
            is_enabled=True,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        assert model.id == "test-id"
        assert model.tracker_type == "jira"
        assert model.is_enabled is True

    def test_create_with_options(self) -> None:
        model = TrackerConnection(
            id="test-id-2",
            tracker_type="github",
            name="GitHub Connection",
            base_url="https://api.github.com",
            workspace_key="myorg",
            project_key="myrepo",
            secret_ref="GITHUB_TOKEN",
            is_enabled=True,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            metadata_json='{"extra": "data"}',
        )
        assert model.workspace_key == "myorg"
        assert model.project_key == "myrepo"
        assert model.secret_ref == "GITHUB_TOKEN"
        assert model.metadata_json == '{"extra": "data"}'


class TestIssueCache:
    def test_create(self) -> None:
        model = IssueCache(
            id="issue-1",
            tracker_connection_id="conn-1",
            remote_issue_id="12345",
            remote_issue_key="PROJ-123",
            title="Test Issue",
            status="Open",
            assignee="user1",
            reporter="user2",
            labels_json='["bug", "urgent"]',
            issue_type="Bug",
            priority="High",
            raw_json='{"key": "PROJ-123"}',
            last_seen_at="2025-01-01T00:00:00Z",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        assert model.remote_issue_key == "PROJ-123"
        assert model.title == "Test Issue"


class TestEntityLink:
    def test_create(self) -> None:
        model = EntityLink(
            id="link-1",
            local_ref="agent-taskstate:task:abc123",
            remote_ref="tracker:jira:PROJ-123",
            link_role="primary",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        assert model.local_ref == "agent-taskstate:task:abc123"
        assert model.remote_ref == "tracker:jira:PROJ-123"
        assert model.link_role == "primary"


class TestSyncEvent:
    def test_create_inbound(self) -> None:
        model = SyncEvent(
            id="event-1",
            tracker_connection_id="conn-1",
            direction="inbound",
            remote_ref="tracker:jira:PROJ-123",
            local_ref=None,
            event_type="issue_updated",
            fingerprint="abc123",
            payload_json='{"updated": true}',
            status="applied",
            error_message=None,
            occurred_at="2025-01-01T00:00:00Z",
            processed_at="2025-01-01T00:00:01Z",
            created_at="2025-01-01T00:00:00Z",
        )
        assert model.direction == "inbound"
        assert model.status == "applied"

    def test_create_failed(self) -> None:
        model = SyncEvent(
            id="event-2",
            tracker_connection_id="conn-1",
            direction="outbound",
            remote_ref="tracker:jira:PROJ-456",
            local_ref="agent-taskstate:task:def456",
            event_type="status_changed",
            fingerprint=None,
            payload_json='{"status": "Done"}',
            status="failed",
            error_message="Connection timeout",
            occurred_at="2025-01-01T00:00:00Z",
            processed_at="2025-01-01T00:00:01Z",
            created_at="2025-01-01T00:00:00Z",
        )
        assert model.status == "failed"
        assert model.error_message == "Connection timeout"


class TestNormalizedIssue:
    def test_create(self) -> None:
        issue = NormalizedIssue(
            remote_issue_id="12345",
            remote_issue_key="PROJ-123",
            title="Test Issue",
            status="Open",
            assignee="John Doe",
            reporter="Jane Doe",
            labels=["bug", "frontend"],
            issue_type="Bug",
            priority="High",
            raw={"id": "12345", "key": "PROJ-123"},
        )
        assert issue.remote_issue_key == "PROJ-123"
        assert issue.labels == ["bug", "frontend"]
