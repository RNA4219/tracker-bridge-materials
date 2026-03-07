from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from tracker_bridge.errors import DuplicateError, NotFoundError
from tracker_bridge.models import TrackerConnection


class TrackerConnectionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _from_row(self, row: sqlite3.Row) -> TrackerConnection:
        return TrackerConnection(
            id=row["id"],
            tracker_type=row["tracker_type"],
            name=row["name"],
            base_url=row["base_url"],
            workspace_key=row["workspace_key"],
            project_key=row["project_key"],
            secret_ref=row["secret_ref"],
            is_enabled=bool(row["is_enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata_json=row["metadata_json"],
        )

    def create(self, model: TrackerConnection) -> None:
        try:
            self.conn.execute(
                """
                INSERT INTO tracker_connection (
                  id, tracker_type, name, base_url, workspace_key, project_key,
                  secret_ref, is_enabled, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model.id,
                    model.tracker_type,
                    model.name,
                    model.base_url,
                    model.workspace_key,
                    model.project_key,
                    model.secret_ref,
                    int(model.is_enabled),
                    model.created_at,
                    model.updated_at,
                    model.metadata_json,
                ),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateError(str(e)) from e

    def get(self, connection_id: str) -> TrackerConnection:
        row = self.conn.execute(
            "SELECT * FROM tracker_connection WHERE id = ?",
            (connection_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"tracker_connection not found: {connection_id}")
        return self._from_row(row)

    def list_all(self) -> Sequence[TrackerConnection]:
        rows = self.conn.execute(
            "SELECT * FROM tracker_connection ORDER BY created_at ASC"
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_enabled(self, connection_id: str, is_enabled: bool, updated_at: str) -> None:
        cur = self.conn.execute(
            """
            UPDATE tracker_connection
               SET is_enabled = ?, updated_at = ?
             WHERE id = ?
            """,
            (int(is_enabled), updated_at, connection_id),
        )
        if cur.rowcount == 0:
            raise NotFoundError(f"tracker_connection not found: {connection_id}")
