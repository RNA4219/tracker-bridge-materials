"""Tests for state_transition module."""
from __future__ import annotations

import sqlite3

import pytest

from tracker_bridge.models import StateTransition
from tracker_bridge.repositories.state_transition import StateTransitionRepository
from tracker_bridge.services.state_transition_service import StateTransitionService


@pytest.fixture
def conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("""
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
            metadata_json TEXT,
            created_at TEXT NOT NULL
        )
    """)
    return conn


class TestStateTransitionRepository:
    def test_create_and_list(self, conn: sqlite3.Connection) -> None:
        repo = StateTransitionRepository(conn)
        transition = StateTransition(
            id="trans-1",
            entity_type="sync_event",
            entity_id="event-1",
            from_status=None,
            to_status="pending",
            reason="event_created",
            actor_type="system",
            actor_id=None,
            run_id=None,
            changed_at="2025-01-01T00:00:00Z",
            created_at="2025-01-01T00:00:00Z",
            metadata_json=None,
        )
        repo.create(transition)

        history = repo.list_by_entity("sync_event", "event-1")
        assert len(history) == 1
        assert history[0].to_status == "pending"

    def test_list_by_entity_ordered(self, conn: sqlite3.Connection) -> None:
        repo = StateTransitionRepository(conn)

        for i, (from_s, to_s) in enumerate([(None, "pending"), ("pending", "applied")]):
            transition = StateTransition(
                id=f"trans-{i}",
                entity_type="sync_event",
                entity_id="event-1",
                from_status=from_s,
                to_status=to_s,
                reason=None,
                actor_type="system",
                actor_id=None,
                run_id=None,
                changed_at=f"2025-01-01T00:0{i}:00Z",
                created_at=f"2025-01-01T00:0{i}:00Z",
                metadata_json=None,
            )
            repo.create(transition)

        history = repo.list_by_entity("sync_event", "event-1")
        assert len(history) == 2
        # Most recent first
        assert history[0].to_status == "applied"
        assert history[1].to_status == "pending"

    def test_get_latest(self, conn: sqlite3.Connection) -> None:
        repo = StateTransitionRepository(conn)

        transition = StateTransition(
            id="trans-1",
            entity_type="sync_event",
            entity_id="event-1",
            from_status=None,
            to_status="pending",
            reason=None,
            actor_type="system",
            actor_id=None,
            run_id=None,
            changed_at="2025-01-01T00:00:00Z",
            created_at="2025-01-01T00:00:00Z",
            metadata_json=None,
        )
        repo.create(transition)

        latest = repo.get_latest("sync_event", "event-1")
        assert latest is not None
        assert latest.to_status == "pending"

        # Non-existent entity
        assert repo.get_latest("sync_event", "nonexistent") is None


class TestStateTransitionService:
    def test_record_transition(self, conn: sqlite3.Connection) -> None:
        repo = StateTransitionRepository(conn)
        service = StateTransitionService(repo)

        transition = service.record_transition(
            entity_type="sync_event",
            entity_id="event-1",
            from_status=None,
            to_status="pending",
            reason="event_created",
        )

        assert transition.id is not None
        assert transition.entity_type == "sync_event"
        assert transition.to_status == "pending"

    def test_get_history(self, conn: sqlite3.Connection) -> None:
        repo = StateTransitionRepository(conn)
        service = StateTransitionService(repo)

        service.record_transition(
            entity_type="sync_event",
            entity_id="event-1",
            from_status=None,
            to_status="pending",
        )
        service.record_transition(
            entity_type="sync_event",
            entity_id="event-1",
            from_status="pending",
            to_status="applied",
        )

        history = service.get_history("sync_event", "event-1")
        assert len(history) == 2
