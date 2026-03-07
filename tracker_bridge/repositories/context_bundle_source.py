"""Repository for context_bundle_source table (source refs tracking)."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from tracker_bridge.models import ContextBundleSource


class ContextBundleSourceRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _from_row(self, row: sqlite3.Row) -> ContextBundleSource:
        return ContextBundleSource(
            id=row["id"],
            context_bundle_id=row["context_bundle_id"],
            typed_ref=row["typed_ref"],
            source_kind=row["source_kind"],
            selected_raw=bool(row["selected_raw"]),
            metadata_json=row["metadata_json"],
            created_at=row["created_at"],
        )

    def create(self, model: ContextBundleSource) -> None:
        self.conn.execute(
            """
            INSERT INTO context_bundle_source (
                id, context_bundle_id, typed_ref, source_kind,
                selected_raw, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model.id,
                model.context_bundle_id,
                model.typed_ref,
                model.source_kind,
                1 if model.selected_raw else 0,
                model.metadata_json,
                model.created_at,
            ),
        )

    def create_batch(self, sources: Sequence[ContextBundleSource]) -> None:
        for source in sources:
            self.create(source)

    def list_by_bundle(self, bundle_id: str) -> Sequence[ContextBundleSource]:
        rows = self.conn.execute(
            """
            SELECT * FROM context_bundle_source
            WHERE context_bundle_id = ?
            ORDER BY created_at
            """,
            (bundle_id,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_typed_ref(self, typed_ref: str) -> Sequence[ContextBundleSource]:
        rows = self.conn.execute(
            """
            SELECT * FROM context_bundle_source
            WHERE typed_ref = ?
            ORDER BY created_at DESC
            """,
            (typed_ref,),
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def count_by_bundle(self, bundle_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM context_bundle_source WHERE context_bundle_id = ?",
            (bundle_id,),
        ).fetchone()
        return row["cnt"] if row else 0
