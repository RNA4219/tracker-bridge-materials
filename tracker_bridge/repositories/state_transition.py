"""Repository for state_transition table (append-only history)."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from tracker_bridge.models import StateTransition


class StateTransitionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _from_row(self, row: sqlite3.Row) -> StateTransition:
        return StateTransition(
            id=row["id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            from_status=row["from_status"],
            to_status=row["to_status"],
            reason=row["reason"],
            actor_type=row["actor_type"],
            actor_id=row["actor_id"],
            run_id=row["run_id"],
            changed_at=row["changed_at"],
            created_at=row["created_at"],
            metadata_json=row["metadata_json"],
        )

    def create(self, model: StateTransition) -> None:
        self.conn.execute(
            """
            INSERT INTO state_transition (
                id, entity_type, entity_id, from_status, to_status,
                reason, actor_type, actor_id, run_id, changed_at, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model.id,
                model.entity_type,
                model.entity_id,
                model.from_status,
                model.to_status,
                model.reason,
                model.actor_type,
                model.actor_id,
                model.run_id,
                model.changed_at,
                model.created_at,
                model.metadata_json,
            ),
        )

    def list_by_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> Sequence[StateTransition]:
        rows = self.conn.execute(
            """
            SELECT * FROM state_transition
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY changed_at DESC
            """,
            (entity_type, entity_id),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def get_latest(self, entity_type: str, entity_id: str) -> StateTransition | None:
        row = self.conn.execute(
            """
            SELECT * FROM state_transition
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY changed_at DESC
            LIMIT 1
            """,
            (entity_type, entity_id),
        ).fetchone()
        return self._from_row(row) if row else None

    def list_by_time_range(
        self,
        start: str,
        end: str,
    ) -> Sequence[StateTransition]:
        rows = self.conn.execute(
            """
            SELECT * FROM state_transition
            WHERE changed_at >= ? AND changed_at <= ?
            ORDER BY changed_at DESC
            """,
            (start, end),
        ).fetchall()
        return [self._from_row(row) for row in rows]
