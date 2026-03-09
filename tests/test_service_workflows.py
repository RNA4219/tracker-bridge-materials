"""Tests for service workflow modules."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from tracker_bridge.errors import ValidationError
from tracker_bridge.repositories.connection import TrackerConnectionRepository
from tracker_bridge.repositories.entity_link import EntityLinkRepository
from tracker_bridge.repositories.state_transition import StateTransitionRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository
from tracker_bridge.services.connection_service import ConnectionService
from tracker_bridge.services.link_service import LinkService
from tracker_bridge.services.state_transition_service import StateTransitionService
from tracker_bridge.services.sync_service import SyncService
from tracker_bridge.services.tracker_integration_service import TrackerIntegrationService


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class TestConnectionService:
    def test_create_list_enable_disable(self, conn: sqlite3.Connection) -> None:
        service = ConnectionService(TrackerConnectionRepository(conn))
        connection = service.create_connection(
            tracker_type="jira",
            name="Primary Jira",
            base_url="https://example.atlassian.net",
            project_key="PROJ",
        )

        connections = service.list_connections()
        assert len(connections) == 1
        assert connection.project_key == "PROJ"

        service.disable_connection(connection.id)
        assert service.list_connections()[0].is_enabled is False

        service.enable_connection(connection.id)
        assert service.list_connections()[0].is_enabled is True


class TestLinkService:
    def test_create_and_list_links(self, conn: sqlite3.Connection) -> None:
        service = LinkService(EntityLinkRepository(conn))
        link = service.create_link(
            local_ref="agent-taskstate:task:task-123",
            remote_ref="tracker:jira:PROJ-123",
        )

        assert link.local_ref == "agent-taskstate:task:local:task-123"
        assert link.remote_ref == "tracker:issue:jira:PROJ-123"
        assert len(service.list_by_local_ref("agent-taskstate:task:task-123")) == 1
        assert len(service.list_by_remote_ref("tracker:jira:PROJ-123")) == 1

    def test_create_link_rejects_invalid_refs(self, conn: sqlite3.Connection) -> None:
        service = LinkService(EntityLinkRepository(conn))
        with pytest.raises(ValidationError):
            service.create_link(local_ref="invalid", remote_ref="tracker:jira:PROJ-123")


class TestSyncService:
    def test_sync_lifecycle_with_state_transitions(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        transition_service = StateTransitionService(StateTransitionRepository(conn))
        service = SyncService(SyncEventRepository(conn), transition_service)

        pending = service.emit_outbound_event(
            tracker_connection_id="conn-1",
            remote_ref="tracker:issue:jira:PROJ-123",
            local_ref="agent-taskstate:task:local:task-123",
            event_type="status_changed",
            payload={"status": "Done"},
            uniqueness_source="status-done",
        )
        assert service.list_pending()[0].id == pending.id

        service.mark_applied(pending.id)
        history = service.get_transition_history(pending.id)
        assert len(history) == 2
        assert {transition.to_status for transition in history} == {"pending", "applied"}

        failed = service.emit_outbound_event(
            tracker_connection_id="conn-1",
            remote_ref="tracker:issue:jira:PROJ-456",
            local_ref=None,
            event_type="comment_posted",
            payload={"comment": "need review"},
            uniqueness_source="comment-1",
        )
        service.mark_failed(failed.id, "timeout", reason="retry later")
        assert service.list_failed()[0].id == failed.id

        skipped = service.emit_outbound_event(
            tracker_connection_id="conn-1",
            remote_ref="tracker:issue:jira:PROJ-789",
            local_ref=None,
            event_type="comment_posted",
            payload={"comment": "duplicate"},
            uniqueness_source="comment-2",
        )
        service.mark_skipped(skipped.id, "duplicate")
        skipped_history = service.get_transition_history(skipped.id)
        assert {transition.to_status for transition in skipped_history} == {"pending", "skipped"}

    def test_get_transition_history_without_transition_service(self, conn: sqlite3.Connection) -> None:
        service = SyncService(SyncEventRepository(conn), transition_service=None)
        assert service.get_transition_history("event-1") == []


class TestTrackerIntegrationServiceSuggestions:
    def test_suggest_status_update(self, conn: sqlite3.Connection) -> None:
        service = TrackerIntegrationService(
            issue_repo=None,  # type: ignore[arg-type]
            link_repo=None,  # type: ignore[arg-type]
            sync_repo=None,  # type: ignore[arg-type]
        )

        suggestion = service.suggest_status_update(
            connection_id="conn-1",
            tracker_type="jira",
            remote_issue_key="PROJ-123",
            current_task_status="done",
        )
        assert suggestion is not None
        assert suggestion["suggested_status"] == "Done"

        assert (
            service.suggest_status_update(
                connection_id="conn-1",
                tracker_type="github",
                remote_issue_key="PROJ-123",
                current_task_status="unknown",
            )
            is None
        )



