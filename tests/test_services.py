"""Tests for service layer integration flows."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from tracker_bridge.adapters.jira import MockJiraAdapter
from tracker_bridge.models import IssueCache, NormalizedIssue
from tracker_bridge.repositories.connection import TrackerConnectionRepository
from tracker_bridge.repositories.entity_link import EntityLinkRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
from tracker_bridge.repositories.state_transition import StateTransitionRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository
from tracker_bridge.services.issue_service import IssueService
from tracker_bridge.services.state_transition_service import StateTransitionService
from tracker_bridge.services.tracker_integration_service import TrackerIntegrationService


def now_iso(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()


@pytest.fixture
def conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute(
        """
        CREATE TABLE tracker_connection (
            id TEXT PRIMARY KEY,
            tracker_type TEXT NOT NULL,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            workspace_key TEXT,
            project_key TEXT,
            secret_ref TEXT,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT,
            CHECK (tracker_type IN ('jira', 'github', 'linear', 'backlog', 'redmine')),
            CHECK (is_enabled IN (0, 1))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE issue_cache (
            id TEXT PRIMARY KEY,
            tracker_connection_id TEXT NOT NULL,
            remote_issue_id TEXT NOT NULL,
            remote_issue_key TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT,
            assignee TEXT,
            reporter TEXT,
            labels_json TEXT,
            issue_type TEXT,
            priority TEXT,
            raw_json TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(tracker_connection_id, remote_issue_key),
            FOREIGN KEY (tracker_connection_id) REFERENCES tracker_connection(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE entity_link (
            id TEXT PRIMARY KEY,
            local_ref TEXT NOT NULL,
            remote_ref TEXT NOT NULL,
            link_role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT,
            CHECK (link_role IN ('primary', 'related', 'duplicate', 'blocks', 'caused_by'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE sync_event (
            id TEXT PRIMARY KEY,
            tracker_connection_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            remote_ref TEXT NOT NULL,
            local_ref TEXT,
            event_type TEXT NOT NULL,
            fingerprint TEXT,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            occurred_at TEXT NOT NULL,
            processed_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (tracker_connection_id) REFERENCES tracker_connection(id) ON DELETE CASCADE,
            CHECK (direction IN ('inbound', 'outbound')),
            CHECK (status IN ('pending', 'applied', 'failed', 'skipped'))
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX idx_sync_event_fingerprint
            ON sync_event(tracker_connection_id, fingerprint)
            WHERE fingerprint IS NOT NULL
        """
    )
    conn.execute(
        """
        CREATE TABLE state_transition (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            reason TEXT,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            run_id TEXT,
            changed_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT
        )
        """
    )
    return conn


@pytest.fixture
def setup_connection(conn: sqlite3.Connection) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO tracker_connection
        (id, tracker_type, name, base_url, is_enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("conn-1", "jira", "Test Jira", "https://example.atlassian.net", 1, ts, ts),
    )


class TestIssueService:
    def test_import_normalized_issue_is_idempotent(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        service = IssueService(
            connection_repo=TrackerConnectionRepository(conn),
            issue_repo=IssueCacheRepository(conn),
            sync_repo=SyncEventRepository(conn),
        )
        normalized_issue = NormalizedIssue(
            remote_issue_id="10001",
            remote_issue_key="PROJ-123",
            title="Investigate sync drift",
            status="Open",
            assignee="alice",
            reporter="bob",
            labels=["bug"],
            issue_type="Bug",
            priority="High",
            raw={"id": "10001", "key": "PROJ-123", "updated": "2026-03-09T00:00:00Z"},
        )

        first = service.import_normalized_issue(
            tracker_connection_id="conn-1",
            normalized_issue=normalized_issue,
        )
        second = service.import_normalized_issue(
            tracker_connection_id="conn-1",
            normalized_issue=normalized_issue,
        )

        assert first.remote_issue_key == "PROJ-123"
        assert second.remote_issue_key == "PROJ-123"

        events = SyncEventRepository(conn).list()
        assert len(events) == 1
        assert events[0].remote_ref == "tracker:issue:jira:PROJ-123"


class TestTrackerIntegrationService:
    def test_minimum_integration_flow(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        issue_repo = IssueCacheRepository(conn)
        link_repo = EntityLinkRepository(conn)
        sync_repo = SyncEventRepository(conn)
        transition_service = StateTransitionService(StateTransitionRepository(conn))
        service = TrackerIntegrationService(
            issue_repo=issue_repo,
            link_repo=link_repo,
            sync_repo=sync_repo,
            transition_service=transition_service,
        )
        adapter = MockJiraAdapter(
            {
                "PROJ-123": {
                    "id": "10001",
                    "key": "PROJ-123",
                    "fields": {
                        "summary": "Investigate sync drift",
                        "status": {"name": "In Progress"},
                        "assignee": {"displayName": "alice"},
                        "reporter": {"displayName": "bob"},
                        "labels": ["bug"],
                        "issuetype": {"name": "Bug"},
                        "priority": {"name": "High"},
                    },
                }
            }
        )
        service.register_adapter("jira", adapter)

        issue = service.import_issue(
            connection_id="conn-1",
            tracker_type="jira",
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
        )
        link = service.create_link(
            tracker_type="jira",
            remote_issue_key="PROJ-123",
            task_id="task-123",
            connection_id="conn-1",
        )
        linked = service.get_linked_issues("task-123")
        snapshot = service.export_issue_snapshot(
            tracker_type="jira",
            remote_issue_key="PROJ-123",
            connection_id="conn-1",
        )

        assert issue.remote_issue_key == "PROJ-123"
        assert link.local_ref == "agent-taskstate:task:local:task-123"
        assert link.remote_ref == "tracker:issue:jira:PROJ-123"
        assert link.metadata_json == '{"tracker_connection_id": "conn-1"}'
        assert len(linked) == 1
        assert linked[0][1] is not None
        assert linked[0][1].title == "Investigate sync drift"
        assert snapshot is not None
        assert snapshot["remote_ref"] == "tracker:issue:jira:PROJ-123"
        assert snapshot["tracker_connection_id"] == "conn-1"
        assert snapshot["last_sync_result"] == "applied"

        history = transition_service.get_history("issue_cache", issue.id)
        assert len(history) == 1
        assert history[0].to_status == "imported"

    def test_get_linked_issues_uses_link_connection_metadata(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        issue_repo = IssueCacheRepository(conn)
        link_repo = EntityLinkRepository(conn)
        sync_repo = SyncEventRepository(conn)
        service = TrackerIntegrationService(
            issue_repo=issue_repo,
            link_repo=link_repo,
            sync_repo=sync_repo,
        )
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO tracker_connection
            (id, tracker_type, name, base_url, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("conn-2", "jira", "Second Jira", "https://second.example.com", 1, ts, ts),
        )
        issue_repo.upsert(
            IssueCache(
                id="issue-1",
                tracker_connection_id="conn-1",
                remote_issue_id="10001",
                remote_issue_key="PROJ-123",
                title="Primary connection issue",
                status="Open",
                assignee=None,
                reporter=None,
                labels_json=None,
                issue_type=None,
                priority=None,
                raw_json='{}',
                last_seen_at=ts,
                created_at=ts,
                updated_at=ts,
            )
        )
        issue_repo.upsert(
            IssueCache(
                id="issue-2",
                tracker_connection_id="conn-2",
                remote_issue_id="20002",
                remote_issue_key="PROJ-123",
                title="Secondary connection issue",
                status="Open",
                assignee=None,
                reporter=None,
                labels_json=None,
                issue_type=None,
                priority=None,
                raw_json='{}',
                last_seen_at=ts,
                created_at=ts,
                updated_at=ts,
            )
        )

        service.create_link(
            tracker_type="jira",
            remote_issue_key="PROJ-123",
            task_id="task-123",
            connection_id="conn-2",
        )
        linked = service.get_linked_issues("task-123")

        assert len(linked) == 1
        assert linked[0][1] is not None
        assert linked[0][1].tracker_connection_id == "conn-2"
        assert linked[0][1].title == "Secondary connection issue"

    def test_post_outbound_comment_skips_duplicate_side_effect(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        issue_repo = IssueCacheRepository(conn)
        link_repo = EntityLinkRepository(conn)
        sync_repo = SyncEventRepository(conn)
        service = TrackerIntegrationService(
            issue_repo=issue_repo,
            link_repo=link_repo,
            sync_repo=sync_repo,
        )
        adapter = MockJiraAdapter({"PROJ-123": {"id": "10001", "key": "PROJ-123"}})
        service.register_adapter("jira", adapter)

        first = service.post_outbound_comment(
            connection_id="conn-1",
            tracker_type="jira",
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
            comment="done しました",
            task_id="task-123",
        )
        second = service.post_outbound_comment(
            connection_id="conn-1",
            tracker_type="jira",
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
            comment="done しました",
            task_id="task-123",
        )

        assert first.id == second.id
        assert adapter.comments["PROJ-123"] == ["done しました"]
