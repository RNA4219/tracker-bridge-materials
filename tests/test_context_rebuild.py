"""Tests for context rebuild service."""
from __future__ import annotations

import sqlite3

import pytest

from tracker_bridge.repositories.context_bundle import ContextBundleRepository
from tracker_bridge.repositories.context_bundle_source import ContextBundleSourceRepository
from tracker_bridge.resolver import MockTrackerIssueResolver
from tracker_bridge.services.context_bundle_service import ContextBundleService
from tracker_bridge.services.context_rebuild_service import ContextRebuildService


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
            created_at TEXT NOT NULL,
            decision_digest TEXT,
            open_question_digest TEXT,
            diagnostics_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE context_bundle_source (
            id TEXT PRIMARY KEY,
            context_bundle_id TEXT NOT NULL,
            typed_ref TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            selected_raw INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT,
            FOREIGN KEY (context_bundle_id) REFERENCES context_bundle(id) ON DELETE CASCADE
        )
    """)
    return conn


class TestContextRebuildService:
    def test_rebuild_context_with_resolved_refs(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        bundle_service = ContextBundleService(bundle_repo, source_repo)

        resolver = MockTrackerIssueResolver({
            "tracker:issue:jira:PROJ-123": {"summary": "Issue 1"},
            "tracker:issue:jira:PROJ-456": {"summary": "Issue 2"},
        })

        rebuild_service = ContextRebuildService(
            resolvers=[resolver],
            bundle_service=bundle_service,
        )

        bundle_id, report, diagnostics = rebuild_service.rebuild_context(
            purpose="resume",
            source_refs=[
                "tracker:issue:jira:PROJ-123",
                "tracker:issue:jira:PROJ-456",
            ],
        )

        assert bundle_id is not None
        assert len(report.resolved) == 2
        assert report.success_rate == 1.0
        assert diagnostics.partial_bundle is False

    def test_rebuild_context_with_unresolved_refs(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        bundle_service = ContextBundleService(bundle_repo, source_repo)

        resolver = MockTrackerIssueResolver({})

        rebuild_service = ContextRebuildService(
            resolvers=[resolver],
            bundle_service=bundle_service,
        )

        bundle_id, report, diagnostics = rebuild_service.rebuild_context(
            purpose="resume",
            source_refs=["tracker:issue:jira:MISSING"],
        )

        assert bundle_id is not None
        assert len(report.unresolved) == 1
        assert diagnostics.partial_bundle is True
        assert "tracker:issue:jira:MISSING" in diagnostics.missing_refs

    def test_rebuild_context_with_unsupported_refs(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        bundle_service = ContextBundleService(bundle_repo, source_repo)

        resolver = MockTrackerIssueResolver({})

        rebuild_service = ContextRebuildService(
            resolvers=[resolver],
            bundle_service=bundle_service,
        )

        bundle_id, report, diagnostics = rebuild_service.rebuild_context(
            purpose="resume",
            source_refs=["agent-taskstate:task:123"],
        )

        assert bundle_id is not None
        assert len(report.unsupported) == 1
        assert "agent-taskstate:task:123" in diagnostics.unsupported_refs

    def test_should_include_raw(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        bundle_service = ContextBundleService(bundle_repo, source_repo)
        resolver = MockTrackerIssueResolver({})

        rebuild_service = ContextRebuildService(
            resolvers=[resolver],
            bundle_service=bundle_service,
        )

        # Review context triggers raw
        assert rebuild_service.should_include_raw("review") is True

        # Investigation triggers raw
        assert rebuild_service.should_include_raw("investigation") is True

        # Low confidence triggers raw
        assert rebuild_service.should_include_raw("normal", confidence=0.5) is True

        # High confidence doesn't trigger raw
        assert rebuild_service.should_include_raw("normal", confidence=0.9) is False

        # Open questions trigger raw
        assert rebuild_service.should_include_raw("normal", has_open_questions=True) is True

        # Conflicts trigger raw
        assert rebuild_service.should_include_raw("normal", has_conflicts=True) is True

    def test_determine_rebuild_level(self, conn: sqlite3.Connection) -> None:
        bundle_repo = ContextBundleRepository(conn)
        source_repo = ContextBundleSourceRepository(conn)
        bundle_service = ContextBundleService(bundle_repo, source_repo)
        resolver = MockTrackerIssueResolver({})

        rebuild_service = ContextRebuildService(
            resolvers=[resolver],
            bundle_service=bundle_service,
        )

        # Create reports with different success rates
        full_report = type('Report', (), {
            'total_count': 10,
            'success_rate': 0.95,
        })()
        assert rebuild_service._determine_rebuild_level(full_report, include_raw=True) == "full"

        summary_report = type('Report', (), {
            'total_count': 10,
            'success_rate': 0.8,
        })()
        assert rebuild_service._determine_rebuild_level(summary_report, include_raw=False) == "summary"

        minimal_report = type('Report', (), {
            'total_count': 10,
            'success_rate': 0.5,
        })()
        assert rebuild_service._determine_rebuild_level(minimal_report, include_raw=False) == "minimal"

        empty_report = type('Report', (), {
            'total_count': 0,
            'success_rate': 0.0,
        })()
        assert rebuild_service._determine_rebuild_level(empty_report, include_raw=False) == "minimal"
