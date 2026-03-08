"""Tests for resolver module."""
from __future__ import annotations

from tracker_bridge.resolver import (
    MockTrackerIssueResolver,
    ResolvedRef,
    ResolverDiagnostics,
    ResolveReport,
    ResolveStatus,
    SourceKind,
)


class TestResolveStatus:
    def test_status_values(self) -> None:
        assert ResolveStatus.RESOLVED == "resolved"
        assert ResolveStatus.UNRESOLVED == "unresolved"
        assert ResolveStatus.UNSUPPORTED == "unsupported"


class TestResolvedRef:
    def test_resolved_ref_creation(self) -> None:
        ref = ResolvedRef(
            typed_ref="tracker:issue:jira:PROJ-123",
            status=ResolveStatus.RESOLVED,
            source_kind=SourceKind.TRACKER_ISSUE,
            summary="Test Issue",
        )
        assert ref.typed_ref == "tracker:issue:jira:PROJ-123"
        assert ref.status == ResolveStatus.RESOLVED
        assert ref.source_kind == SourceKind.TRACKER_ISSUE

    def test_unresolved_ref(self) -> None:
        ref = ResolvedRef(
            typed_ref="tracker:issue:jira:MISSING",
            status=ResolveStatus.UNRESOLVED,
            error_message="Issue not found",
        )
        assert ref.status == ResolveStatus.UNRESOLVED
        assert ref.error_message == "Issue not found"


class TestResolveReport:
    def test_empty_report(self) -> None:
        report = ResolveReport()
        assert report.total_count == 0
        assert report.success_rate == 0.0

    def test_report_with_results(self) -> None:
        report = ResolveReport()
        report.resolved.append(ResolvedRef(
            typed_ref="ref1",
            status=ResolveStatus.RESOLVED,
        ))
        report.unresolved.append(ResolvedRef(
            typed_ref="ref2",
            status=ResolveStatus.UNRESOLVED,
        ))

        assert report.total_count == 2
        assert report.success_rate == 0.5


class TestResolverDiagnostics:
    def test_empty_diagnostics(self) -> None:
        diag = ResolverDiagnostics()
        assert diag.missing_refs == []
        assert diag.unsupported_refs == []
        assert diag.partial_bundle is False

    def test_to_dict(self) -> None:
        diag = ResolverDiagnostics(
            missing_refs=["ref1"],
            unsupported_refs=["ref2"],
            resolver_warnings=["Warning"],
            partial_bundle=True,
        )
        result = diag.to_dict()
        assert result["missing_refs"] == ["ref1"]
        assert result["unsupported_refs"] == ["ref2"]
        assert result["partial_bundle"] is True


class TestMockTrackerIssueResolver:
    def test_can_resolve_tracker_issue(self) -> None:
        resolver = MockTrackerIssueResolver()
        assert resolver.can_resolve("tracker:issue:jira:PROJ-123") is True
        assert resolver.can_resolve("agent-taskstate:task:local:123") is False
        assert resolver.can_resolve("invalid") is False

    def test_resolve_existing_issue(self) -> None:
        resolver = MockTrackerIssueResolver({
            "tracker:issue:jira:PROJ-123": {
                "summary": "Test Issue Summary",
                "metadata": {"status": "Open"},
            }
        })

        result = resolver.resolve("tracker:issue:jira:PROJ-123")
        assert result.status == ResolveStatus.RESOLVED
        assert result.summary == "Test Issue Summary"

    def test_resolve_missing_issue(self) -> None:
        resolver = MockTrackerIssueResolver()

        result = resolver.resolve("tracker:issue:jira:MISSING")
        assert result.status == ResolveStatus.UNRESOLVED

    def test_resolve_unsupported_ref(self) -> None:
        resolver = MockTrackerIssueResolver()

        result = resolver.resolve("agent-taskstate:task:local:123")
        assert result.status == ResolveStatus.UNSUPPORTED

    def test_resolve_many(self) -> None:
        resolver = MockTrackerIssueResolver({
            "tracker:issue:jira:PROJ-123": {"summary": "Issue 1"},
            "tracker:issue:jira:PROJ-456": {"summary": "Issue 2"},
        })

        report = resolver.resolve_many([
            "tracker:issue:jira:PROJ-123",
            "tracker:issue:jira:PROJ-456",
            "tracker:issue:jira:MISSING",
        ])

        assert len(report.resolved) == 2
        assert len(report.unresolved) == 1
        assert report.total_count == 3

    def test_resolve_with_raw(self) -> None:
        resolver = MockTrackerIssueResolver({
            "tracker:issue:jira:PROJ-123": {
                "summary": "Test",
                "raw_field": "raw_value",
            }
        })

        result = resolver.resolve("tracker:issue:jira:PROJ-123", include_raw=True)
        assert result.status == ResolveStatus.RESOLVED
        assert result.raw is not None
        assert result.raw["raw_field"] == "raw_value"

        result_no_raw = resolver.resolve("tracker:issue:jira:PROJ-123", include_raw=False)
        assert result_no_raw.raw is None
