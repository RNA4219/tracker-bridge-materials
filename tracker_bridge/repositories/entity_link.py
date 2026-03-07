from __future__ import annotations

import sqlite3
from typing import Sequence

from tracker_bridge.errors import DuplicateError
from tracker_bridge.models import EntityLink


class EntityLinkRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _from_row(self, row: sqlite3.Row) -> EntityLink:
        return EntityLink(
            id=row["id"],
            local_ref=row["local_ref"],
            remote_ref=row["remote_ref"],
            link_role=row["link_role"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata_json=row["metadata_json"],
        )

    def create(self, model: EntityLink) -> None:
        try:
            self.conn.execute(
                """
                INSERT INTO entity_link (
                  id, local_ref, remote_ref, link_role, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model.id,
                    model.local_ref,
                    model.remote_ref,
                    model.link_role,
                    model.created_at,
                    model.updated_at,
                    model.metadata_json,
                ),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateError(str(e)) from e

    def list_by_local_ref(self, local_ref: str) -> Sequence[EntityLink]:
        rows = self.conn.execute(
            "SELECT * FROM entity_link WHERE local_ref = ? ORDER BY created_at ASC",
            (local_ref,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_remote_ref(self, remote_ref: str) -> Sequence[EntityLink]:
        rows = self.conn.execute(
            "SELECT * FROM entity_link WHERE remote_ref = ? ORDER BY created_at ASC",
            (remote_ref,),
        ).fetchall()
        return [self._from_row(row) for row in rows]
