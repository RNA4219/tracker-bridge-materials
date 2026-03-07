"""Tests for context_bundle module."""
from __future__ import annotations

import sqlite3

import pytest

from tracker_bridge.models import ContextBundle, ContextBundleSource
from tracker_bridge.repositories.context_bundle import ContextBundleRepository
from tracker_bridge.repositories.context_bundle_source import ContextBundleSourceRepository
from tracker_bridge.services.context_bundle_service import ContextBundleService


@pytest.fixture
def conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("""
        CREATE TABLE context_bundle (
            id TEXT PRIMARY KEY,
            purpose TEXT NOT NULL,
            summary TEXT NOT NULL,
            rebuild_level TEXT NOT NULL,
            raw_included INTEGER NOT NULL,
            generator_version TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            decision_digest TEXT,
            open_question_digest TEXT,
            diagnostics_json TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE context_bundle_source (
            id TEXT PRIMARY KEY,
            context_bundle_id TEXT NOT NULL,
            typed_ref TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            selected_raw INTEGER NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (context_bundle_id) REFERENCES context_bundle(id) ON DELETE CASCADE
        )
    """)
    return conn


class TestContextBundleRepository:
    def test_create_and_get(self, conn: sqlite3.Connection) -> None:
        repo = ContextBundleRepository(conn)
        bundle = ContextBundle(
            id="bundle-1",
            purpose="resume",
            summary="Test bundle",
            rebuild_level="summary",
            raw_included=False,
            generator_version="1.0.0",
            generated_at="2025-01-01T00:00:00Z",
            decision_digest=None,
            open_question_digest=None,
            diagnostics_json=None,
            created_at="2025-01-01T00:00:00Z",
        )
        repo.create(bundle)

        result = repo.get("bundle-1")
        assert result.purpose == "resume"
        assert result.summary == "Test bundle"
        assert result.raw_included is False

    def test_list_latest(self, conn: sqlite3.Connection) -> None:
        repo = ContextBundleRepository(conn)

        for i in range(3):
            bundle = ContextBundle(
                id=f"bundle-{i}",
                purpose="resume",
                summary=f"Bundle {i}",
                rebuild_level="summary",
                raw_included=False,
                generator_version="1.0.0",
                generated_at=f"2025-01-0{i}T00:00:00Z",
                decision_digest=None,
                open_question_digest=None,
                diagnostics_json=None,
                created_at=f"2025-01-0{i}T00:00:00Z",
            )
            repo.create(bundle)

        results = repo.list_latest(limit=2)
        assert len(results) == 2


class TestContextBundleSourceRepository:
    def test_create_and_list(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)

        # Create bundle first
        bundle = ContextBundle(
            id="bundle-1",
            purpose="resume",
            summary="Test",
            rebuild_level="summary",
            raw_included=False,
            generator_version="1.0.0",
            generated_at="2025-01-01T00:00:00Z",
            decision_digest=None,
            open_question_digest=None,
            diagnostics_json=None,
            created_at="2025-01-01T00:00:00Z",
        )
        bundle_repo.create(bundle)

        # Add sources
        source = ContextBundleSource(
            id="source-1",
            context_bundle_id="bundle-1",
            typed_ref="workx:task:local:task-123",
            source_kind="task",
            selected_raw=False,
            metadata_json=None,
            created_at="2025-01-01T00:00:00Z",
        )
        source_repo.create(source)

        sources = source_repo.list_by_bundle("bundle-1")
        assert len(sources) == 1
        assert sources[0].typed_ref == "workx:task:local:task-123"

    def test_count_by_bundle(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)

        bundle = ContextBundle(
            id="bundle-1",
            purpose="resume",
            summary="Test",
            rebuild_level="summary",
            raw_included=False,
            generator_version="1.0.0",
            generated_at="2025-01-01T00:00:00Z",
            decision_digest=None,
            open_question_digest=None,
            diagnostics_json=None,
            created_at="2025-01-01T00:00:00Z",
        )
        bundle_repo.create(bundle)

        for i in range(3):
            source = ContextBundleSource(
                id=f"source-{i}",
                context_bundle_id="bundle-1",
                typed_ref=f"workx:task:local:task-{i}",
                source_kind="task",
                selected_raw=False,
                metadata_json=None,
                created_at="2025-01-01T00:00:00Z",
            )
            source_repo.create(source)

        assert source_repo.count_by_bundle("bundle-1") == 3


class TestContextBundleService:
    def test_create_bundle_with_sources(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        service = ContextBundleService(bundle_repo, source_repo)

        bundle = service.create_bundle(
            purpose="resume",
            summary="Test bundle for resumption",
            rebuild_level="summary",
            raw_included=False,
            source_refs=[
                "workx:task:local:task-123",
                "tracker:issue:jira:PROJ-456",
            ],
        )

        assert bundle.id is not None
        assert bundle.purpose == "resume"
        assert bundle.generator_version == "1.0.0"

        # Check sources were added
        sources = source_repo.list_by_bundle(bundle.id)
        assert len(sources) == 2

    def test_get_bundle_with_sources(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        service = ContextBundleService(bundle_repo, source_repo)

        bundle = service.create_bundle(
            purpose="checkpoint",
            summary="Checkpoint bundle",
            source_refs=["workx:task:local:task-123"],
        )

        retrieved, sources = service.get_bundle_with_sources(bundle.id)
        assert retrieved.id == bundle.id
        assert len(sources) == 1

    def test_check_raw_included(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        service = ContextBundleService(bundle_repo, source_repo)

        bundle = service.create_bundle(
            purpose="resume",
            summary="With raw",
            raw_included=True,
        )

        assert service.check_raw_included(bundle.id) is True

    def test_compare_generator_version(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        service = ContextBundleService(bundle_repo, source_repo, generator_version="1.0.0")

        bundle = service.create_bundle(
            purpose="resume",
            summary="Test",
        )

        version, is_current = service.compare_generator_version(bundle.id)
        assert version == "1.0.0"
        assert is_current is True
