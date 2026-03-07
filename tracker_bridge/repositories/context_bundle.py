"""Repository for context_bundle table (audit-enabled bundles)."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from tracker_bridge.errors import NotFoundError
from tracker_bridge.models import ContextBundle


class ContextBundleRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _from_row(self, row: sqlite3.Row) -> ContextBundle:
        return ContextBundle(
            id=row["id"],
            purpose=row["purpose"],
            summary=row["summary"],
            rebuild_level=row["rebuild_level"],
            raw_included=bool(row["raw_included"]),
            generator_version=row["generator_version"],
            generated_at=row["generated_at"],
            decision_digest=row["decision_digest"],
            open_question_digest=row["open_question_digest"],
            diagnostics_json=row["diagnostics_json"],
            created_at=row["created_at"],
        )

    def create(self, model: ContextBundle) -> None:
        self.conn.execute(
            """
            INSERT INTO context_bundle (
                id, purpose, summary, rebuild_level, raw_included,
                generator_version, generated_at, decision_digest,
                open_question_digest, diagnostics_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model.id,
                model.purpose,
                model.summary,
                model.rebuild_level,
                1 if model.raw_included else 0,
                model.generator_version,
                model.generated_at,
                model.decision_digest,
                model.open_question_digest,
                model.diagnostics_json,
                model.created_at,
            ),
        )

    def get(self, bundle_id: str) -> ContextBundle:
        row = self.conn.execute(
            "SELECT * FROM context_bundle WHERE id = ?",
            (bundle_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"context_bundle not found: {bundle_id}")
        return self._from_row(row)

    def list_latest(self, limit: int = 10) -> Sequence[ContextBundle]:
        rows = self.conn.execute(
            """
            SELECT * FROM context_bundle
            ORDER BY generated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_purpose(self, purpose: str) -> Sequence[ContextBundle]:
        rows = self.conn.execute(
            """
            SELECT * FROM context_bundle
            WHERE purpose = ?
            ORDER BY generated_at DESC
            """,
            (purpose,),
        ).fetchall()
        return [self._from_row(row) for row in rows]
