from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from tracker_bridge.errors import NotFoundError
from tracker_bridge.models import IssueCache
from tracker_bridge.refs import TypedRef


class IssueCacheRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _from_row(self, row: sqlite3.Row) -> IssueCache:
        return IssueCache(
            id=row["id"],
            tracker_connection_id=row["tracker_connection_id"],
            remote_issue_id=row["remote_issue_id"],
            remote_issue_key=row["remote_issue_key"],
            title=row["title"],
            status=row["status"],
            assignee=row["assignee"],
            reporter=row["reporter"],
            labels_json=row["labels_json"],
            issue_type=row["issue_type"],
            priority=row["priority"],
            raw_json=row["raw_json"],
            last_seen_at=row["last_seen_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def upsert(self, model: IssueCache) -> None:
        self.conn.execute(
            """
            INSERT INTO issue_cache (
              id, tracker_connection_id, remote_issue_id, remote_issue_key,
              title, status, assignee, reporter, labels_json,
              issue_type, priority, raw_json, last_seen_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tracker_connection_id, remote_issue_key)
            DO UPDATE SET
              remote_issue_id = excluded.remote_issue_id,
              title = excluded.title,
              status = excluded.status,
              assignee = excluded.assignee,
              reporter = excluded.reporter,
              labels_json = excluded.labels_json,
              issue_type = excluded.issue_type,
              priority = excluded.priority,
              raw_json = excluded.raw_json,
              last_seen_at = excluded.last_seen_at,
              updated_at = excluded.updated_at
            """,
            (
                model.id,
                model.tracker_connection_id,
                model.remote_issue_id,
                model.remote_issue_key,
                model.title,
                model.status,
                model.assignee,
                model.reporter,
                model.labels_json,
                model.issue_type,
                model.priority,
                model.raw_json,
                model.last_seen_at,
                model.created_at,
                model.updated_at,
            ),
        )

    def get_by_remote_key(self, tracker_connection_id: str, remote_issue_key: str) -> IssueCache:
        row = self.conn.execute(
            """
            SELECT * FROM issue_cache
             WHERE tracker_connection_id = ? AND remote_issue_key = ?
            """,
            (tracker_connection_id, remote_issue_key),
        ).fetchone()
        if row is None:
            raise NotFoundError(
                f"issue not found: connection={tracker_connection_id}, key={remote_issue_key}"
            )
        return self._from_row(row)

    def _list_rows_by_remote_ref(
        self,
        remote_ref: str,
        *,
        tracker_connection_id: str | None = None,
    ) -> list[sqlite3.Row]:
        ref = TypedRef.parse(remote_ref)
        if not ref.is_tracker or ref.provider is None:
            raise ValueError(f"remote_ref must be a tracker ref: {remote_ref}")

        sql = """
            SELECT ic.*
              FROM issue_cache ic
              JOIN tracker_connection tc
                ON tc.id = ic.tracker_connection_id
             WHERE tc.tracker_type = ? AND ic.remote_issue_key = ?
        """
        params: list[str] = [ref.provider, ref.entity_id]
        if tracker_connection_id is not None:
            sql += " AND ic.tracker_connection_id = ?"
            params.append(tracker_connection_id)
        sql += " ORDER BY ic.updated_at DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return list(rows)

    def find_by_remote_ref(
        self,
        remote_ref: str,
        *,
        tracker_connection_id: str | None = None,
    ) -> IssueCache | None:
        rows = self._list_rows_by_remote_ref(
            remote_ref,
            tracker_connection_id=tracker_connection_id,
        )
        if not rows:
            return None
        if tracker_connection_id is None and len(rows) > 1:
            raise ValueError(f"ambiguous tracker ref across connections: {remote_ref}")
        return self._from_row(rows[0])

    def list_by_remote_ref(self, remote_ref: str) -> Sequence[IssueCache]:
        rows = self._list_rows_by_remote_ref(remote_ref)
        return [self._from_row(row) for row in rows]

    def list_by_connection(
        self,
        tracker_connection_id: str,
        *,
        status: str | None = None,
    ) -> Sequence[IssueCache]:
        if status:
            rows = self.conn.execute(
                """
                SELECT * FROM issue_cache
                 WHERE tracker_connection_id = ? AND status = ?
                 ORDER BY updated_at DESC
                """,
                (tracker_connection_id, status),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM issue_cache
                 WHERE tracker_connection_id = ?
                 ORDER BY updated_at DESC
                """,
                (tracker_connection_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_tracker_type(self, tracker_type: str) -> Sequence[IssueCache]:
        rows = self.conn.execute(
            """
            SELECT ic.*
              FROM issue_cache ic
              JOIN tracker_connection tc
                ON tc.id = ic.tracker_connection_id
             WHERE tc.tracker_type = ?
             ORDER BY ic.updated_at DESC
            """,
            (tracker_type,),
        ).fetchall()
        return [self._from_row(row) for row in rows]
