from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from tracker_bridge.errors import DuplicateError, NotFoundError
from tracker_bridge.models import SyncEvent


class SyncEventRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _from_row(self, row: sqlite3.Row) -> SyncEvent:
        return SyncEvent(
            id=row["id"],
            tracker_connection_id=row["tracker_connection_id"],
            direction=row["direction"],
            remote_ref=row["remote_ref"],
            local_ref=row["local_ref"],
            event_type=row["event_type"],
            fingerprint=row["fingerprint"],
            payload_json=row["payload_json"],
            status=row["status"],
            error_message=row["error_message"],
            occurred_at=row["occurred_at"],
            processed_at=row["processed_at"],
            created_at=row["created_at"],
        )

    def create(self, model: SyncEvent) -> None:
        try:
            self.conn.execute(
                """
                INSERT INTO sync_event (
                  id, tracker_connection_id, direction, remote_ref, local_ref,
                  event_type, fingerprint, payload_json, status,
                  error_message, occurred_at, processed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model.id,
                    model.tracker_connection_id,
                    model.direction,
                    model.remote_ref,
                    model.local_ref,
                    model.event_type,
                    model.fingerprint,
                    model.payload_json,
                    model.status,
                    model.error_message,
                    model.occurred_at,
                    model.processed_at,
                    model.created_at,
                ),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateError(str(e)) from e

    def list(
        self,
        *,
        status: str | None = None,
        direction: str | None = None,
    ) -> Sequence[SyncEvent]:
        sql = "SELECT * FROM sync_event WHERE 1=1"
        params: list[str] = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if direction:
            sql += " AND direction = ?"
            params.append(direction)

        sql += " ORDER BY occurred_at DESC"

        rows = self.conn.execute(sql, params).fetchall()
        return [self._from_row(row) for row in rows]

    def mark_applied(self, event_id: str, processed_at: str) -> None:
        cur = self.conn.execute(
            """
            UPDATE sync_event
               SET status = 'applied',
                   processed_at = ?,
                   error_message = NULL
             WHERE id = ?
            """,
            (processed_at, event_id),
        )
        if cur.rowcount == 0:
            raise NotFoundError(f"sync_event not found: {event_id}")

    def mark_failed(self, event_id: str, error_message: str, processed_at: str) -> None:
        cur = self.conn.execute(
            """
            UPDATE sync_event
               SET status = 'failed',
                   error_message = ?,
                   processed_at = ?
             WHERE id = ?
            """,
            (error_message, processed_at, event_id),
        )
        if cur.rowcount == 0:
            raise NotFoundError(f"sync_event not found: {event_id}")
