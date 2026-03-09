"""Tests for repository layer with in-memory database."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from tracker_bridge.errors import DuplicateError, NotFoundError
from tracker_bridge.models import EntityLink, IssueCache, SyncEvent, TrackerConnection
from tracker_bridge.repositories.connection import TrackerConnectionRepository
from tracker_bridge.repositories.entity_link import EntityLinkRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def conn() -> sqlite3.Connection:
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # Create tables
    conn.execute("""
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
    """)

    conn.execute("""
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
    """)

    conn.execute("""
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
    """)

    conn.execute("""
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
    """)

    return conn


class TestTrackerConnectionRepository:
    def test_create_and_get(self, conn: sqlite3.Connection) -> None:
        repo = TrackerConnectionRepository(conn)
        ts = now_iso()
        model = TrackerConnection(
            id="conn-1",
            tracker_type="jira",
            name="Test Jira",
            base_url="https://example.atlassian.net",
            workspace_key=None,
            project_key="PROJ",
            secret_ref="JIRA_TOKEN",
            is_enabled=True,
            created_at=ts,
            updated_at=ts,
        )
        repo.create(model)

        result = repo.get("conn-1")
        assert result.id == "conn-1"
        assert result.tracker_type == "jira"
        assert result.project_key == "PROJ"

    def test_get_not_found(self, conn: sqlite3.Connection) -> None:
        repo = TrackerConnectionRepository(conn)
        with pytest.raises(NotFoundError):
            repo.get("nonexistent")

    def test_duplicate_raises(self, conn: sqlite3.Connection) -> None:
        repo = TrackerConnectionRepository(conn)
        ts = now_iso()
        model = TrackerConnection(
            id="conn-1",
            tracker_type="jira",
            name="Test",
            base_url="https://example.com",
            workspace_key=None,
            project_key=None,
            secret_ref=None,
            is_enabled=True,
            created_at=ts,
            updated_at=ts,
        )
        repo.create(model)

        with pytest.raises(DuplicateError):
            repo.create(model)

    def test_list_all(self, conn: sqlite3.Connection) -> None:
        repo = TrackerConnectionRepository(conn)
        ts = now_iso()

        for i in range(3):
            model = TrackerConnection(
                id=f"conn-{i}",
                tracker_type="jira",
                name=f"Connection {i}",
                base_url="https://example.com",
                workspace_key=None,
                project_key=None,
                secret_ref=None,
                is_enabled=True,
                created_at=ts,
                updated_at=ts,
            )
            repo.create(model)

        result = repo.list_all()
        assert len(result) == 3

    def test_update_enabled(self, conn: sqlite3.Connection) -> None:
        repo = TrackerConnectionRepository(conn)
        ts = now_iso()
        model = TrackerConnection(
            id="conn-1",
            tracker_type="jira",
            name="Test",
            base_url="https://example.com",
            workspace_key=None,
            project_key=None,
            secret_ref=None,
            is_enabled=True,
            created_at=ts,
            updated_at=ts,
        )
        repo.create(model)

        repo.update_enabled("conn-1", False, now_iso())
        result = repo.get("conn-1")
        assert result.is_enabled is False


class TestIssueCacheRepository:
    @pytest.fixture
    def setup_connection(self, conn: sqlite3.Connection) -> None:
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO tracker_connection
            (id, tracker_type, name, base_url, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("conn-1", "jira", "Test", "https://example.com", 1, ts, ts),
        )

    def test_upsert_insert(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = IssueCacheRepository(conn)
        ts = now_iso()
        model = IssueCache(
            id="issue-1",
            tracker_connection_id="conn-1",
            remote_issue_id="12345",
            remote_issue_key="PROJ-123",
            title="Test Issue",
            status="Open",
            assignee=None,
            reporter=None,
            labels_json=None,
            issue_type=None,
            priority=None,
            raw_json='{"key": "PROJ-123"}',
            last_seen_at=ts,
            created_at=ts,
            updated_at=ts,
        )
        repo.upsert(model)

        result = repo.get_by_remote_key("conn-1", "PROJ-123")
        assert result.remote_issue_key == "PROJ-123"

    def test_upsert_update(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = IssueCacheRepository(conn)
        ts = now_iso()

        # First insert
        model = IssueCache(
            id="issue-1",
            tracker_connection_id="conn-1",
            remote_issue_id="12345",
            remote_issue_key="PROJ-123",
            title="Original Title",
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
        repo.upsert(model)

        # Update with same key
        ts2 = now_iso()
        model2 = IssueCache(
            id="issue-2",  # Different ID, but same key
            tracker_connection_id="conn-1",
            remote_issue_id="12345",
            remote_issue_key="PROJ-123",
            title="Updated Title",
            status="In Progress",
            assignee="user1",
            reporter=None,
            labels_json='["bug"]',
            issue_type="Bug",
            priority="High",
            raw_json='{"updated": true}',
            last_seen_at=ts2,
            created_at=ts,
            updated_at=ts2,
        )
        repo.upsert(model2)

        result = repo.get_by_remote_key("conn-1", "PROJ-123")
        assert result.title == "Updated Title"
        assert result.status == "In Progress"

    def test_list_by_connection(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = IssueCacheRepository(conn)
        ts = now_iso()

        for i in range(3):
            model = IssueCache(
                id=f"issue-{i}",
                tracker_connection_id="conn-1",
                remote_issue_id=str(i),
                remote_issue_key=f"PROJ-{i}",
                title=f"Issue {i}",
                status="Open" if i < 2 else "Closed",
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
            repo.upsert(model)

        all_issues = repo.list_by_connection("conn-1")
        assert len(all_issues) == 3

        open_issues = repo.list_by_connection("conn-1", status="Open")
        assert len(open_issues) == 2


    def test_find_by_remote_ref_with_connection_id(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = IssueCacheRepository(conn)
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO tracker_connection
            (id, tracker_type, name, base_url, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("conn-2", "jira", "Test 2", "https://second.example.com", 1, ts, ts),
        )
        repo.upsert(
            IssueCache(
                id="issue-1",
                tracker_connection_id="conn-1",
                remote_issue_id="10001",
                remote_issue_key="PROJ-123",
                title="Primary issue",
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
        repo.upsert(
            IssueCache(
                id="issue-2",
                tracker_connection_id="conn-2",
                remote_issue_id="20002",
                remote_issue_key="PROJ-123",
                title="Secondary issue",
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

        issue = repo.find_by_remote_ref(
            "tracker:issue:jira:PROJ-123",
            tracker_connection_id="conn-2",
        )
        assert issue is not None
        assert issue.title == "Secondary issue"

    def test_find_by_remote_ref_raises_on_ambiguous(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = IssueCacheRepository(conn)
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO tracker_connection
            (id, tracker_type, name, base_url, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("conn-2", "jira", "Test 2", "https://second.example.com", 1, ts, ts),
        )
        for connection_id, title in (("conn-1", "Primary issue"), ("conn-2", "Secondary issue")):
            repo.upsert(
                IssueCache(
                    id=f"issue-{connection_id}",
                    tracker_connection_id=connection_id,
                    remote_issue_id=f"remote-{connection_id}",
                    remote_issue_key="PROJ-123",
                    title=title,
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

        with pytest.raises(ValueError, match="ambiguous tracker ref"):
            repo.find_by_remote_ref("tracker:issue:jira:PROJ-123")


class TestEntityLinkRepository:
    def test_create_and_list(self, conn: sqlite3.Connection) -> None:
        repo = EntityLinkRepository(conn)
        ts = now_iso()
        model = EntityLink(
            id="link-1",
            local_ref="agent-taskstate:task:local:abc123",
            remote_ref="tracker:issue:jira:PROJ-123",
            link_role="primary",
            created_at=ts,
            updated_at=ts,
        )
        repo.create(model)

        by_local = repo.list_by_local_ref("agent-taskstate:task:local:abc123")
        assert len(by_local) == 1
        assert by_local[0].remote_ref == "tracker:issue:jira:PROJ-123"

        by_remote = repo.list_by_remote_ref("tracker:issue:jira:PROJ-123")
        assert len(by_remote) == 1
        assert by_remote[0].local_ref == "agent-taskstate:task:local:abc123"


class TestSyncEventRepository:
    @pytest.fixture
    def setup_connection(self, conn: sqlite3.Connection) -> None:
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO tracker_connection
            (id, tracker_type, name, base_url, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("conn-1", "jira", "Test", "https://example.com", 1, ts, ts),
        )

    def test_create_and_list(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = SyncEventRepository(conn)
        ts = now_iso()
        model = SyncEvent(
            id="event-1",
            tracker_connection_id="conn-1",
            direction="inbound",
            remote_ref="tracker:issue:jira:PROJ-123",
            local_ref=None,
            event_type="issue_updated",
            fingerprint="abc123",
            payload_json='{}',
            status="applied",
            error_message=None,
            occurred_at=ts,
            processed_at=ts,
            created_at=ts,
        )
        repo.create(model)

        events = repo.list()
        assert len(events) == 1

    def test_mark_applied(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = SyncEventRepository(conn)
        ts = now_iso()
        model = SyncEvent(
            id="event-1",
            tracker_connection_id="conn-1",
            direction="outbound",
            remote_ref="tracker:issue:jira:PROJ-123",
            local_ref="agent-taskstate:task:local:abc",
            event_type="status_changed",
            fingerprint=None,
            payload_json='{}',
            status="pending",
            error_message=None,
            occurred_at=ts,
            processed_at=None,
            created_at=ts,
        )
        repo.create(model)

        repo.mark_applied("event-1", now_iso())
        events = repo.list(status="applied")
        assert len(events) == 1
        assert events[0].processed_at is not None

    def test_mark_failed(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = SyncEventRepository(conn)
        ts = now_iso()
        model = SyncEvent(
            id="event-1",
            tracker_connection_id="conn-1",
            direction="outbound",
            remote_ref="tracker:issue:jira:PROJ-123",
            local_ref="agent-taskstate:task:local:abc",
            event_type="status_changed",
            fingerprint=None,
            payload_json='{}',
            status="pending",
            error_message=None,
            occurred_at=ts,
            processed_at=None,
            created_at=ts,
        )
        repo.create(model)

        repo.mark_failed("event-1", "Connection timeout", now_iso())
        events = repo.list(status="failed")
        assert len(events) == 1
        assert events[0].error_message == "Connection timeout"


    def test_get_by_fingerprint(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = SyncEventRepository(conn)
        ts = now_iso()
        model = SyncEvent(
            id="event-1",
            tracker_connection_id="conn-1",
            direction="inbound",
            remote_ref="tracker:issue:jira:PROJ-123",
            local_ref=None,
            event_type="issue_updated",
            fingerprint="fingerprint-1",
            payload_json='{}',
            status="applied",
            error_message=None,
            occurred_at=ts,
            processed_at=ts,
            created_at=ts,
        )
        repo.create(model)

        event = repo.get_by_fingerprint("conn-1", "fingerprint-1")
        assert event is not None
        assert event.id == "event-1"

    def test_get_latest_by_remote_ref(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = SyncEventRepository(conn)
        ts1 = now_iso()
        first = SyncEvent(
            id="event-1",
            tracker_connection_id="conn-1",
            direction="inbound",
            remote_ref="tracker:issue:jira:PROJ-123",
            local_ref=None,
            event_type="issue_updated",
            fingerprint="fingerprint-1",
            payload_json='{}',
            status="applied",
            error_message=None,
            occurred_at=ts1,
            processed_at=ts1,
            created_at=ts1,
        )
        repo.create(first)

        ts2 = now_iso()
        second = SyncEvent(
            id="event-2",
            tracker_connection_id="conn-1",
            direction="outbound",
            remote_ref="tracker:issue:jira:PROJ-123",
            local_ref="agent-taskstate:task:local:abc",
            event_type="comment_posted",
            fingerprint="fingerprint-2",
            payload_json='{}',
            status="applied",
            error_message=None,
            occurred_at=ts2,
            processed_at=ts2,
            created_at=ts2,
        )
        repo.create(second)

        event = repo.get_latest_by_remote_ref("tracker:issue:jira:PROJ-123")
        assert event is not None
        assert event.id == "event-2"

    def test_get_latest_by_remote_ref_filters_connection(self, conn: sqlite3.Connection, setup_connection: None) -> None:
        repo = SyncEventRepository(conn)
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO tracker_connection
            (id, tracker_type, name, base_url, is_enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("conn-2", "jira", "Test 2", "https://second.example.com", 1, ts, ts),
        )
        repo.create(
            SyncEvent(
                id="event-1",
                tracker_connection_id="conn-1",
                direction="inbound",
                remote_ref="tracker:issue:jira:PROJ-123",
                local_ref=None,
                event_type="issue_updated",
                fingerprint="fingerprint-1",
                payload_json='{}',
                status="applied",
                error_message=None,
                occurred_at=ts,
                processed_at=ts,
                created_at=ts,
            )
        )
        repo.create(
            SyncEvent(
                id="event-2",
                tracker_connection_id="conn-2",
                direction="outbound",
                remote_ref="tracker:issue:jira:PROJ-123",
                local_ref=None,
                event_type="comment_posted",
                fingerprint="fingerprint-2",
                payload_json='{}',
                status="applied",
                error_message=None,
                occurred_at=ts,
                processed_at=ts,
                created_at=ts,
            )
        )

        event = repo.get_latest_by_remote_ref(
            "tracker:issue:jira:PROJ-123",
            tracker_connection_id="conn-1",
        )
        assert event is not None
        assert event.id == "event-1"




