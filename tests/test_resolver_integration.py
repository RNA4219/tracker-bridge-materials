"""Tests for concrete resolver implementations."""
from __future__ import annotations

from tracker_bridge.models import IssueCache
from tracker_bridge.resolver import MemxResolver, ResolveStatus, TrackerIssueResolver


class IssueCacheRepoStub:
    def __init__(self, issue: IssueCache | None = None, *, error: Exception | None = None) -> None:
        self.issue = issue
        self.error = error
        self.seen_refs: list[str] = []

    def find_by_remote_ref(
        self,
        remote_ref: str,
        *,
        tracker_connection_id: str | None = None,
    ) -> IssueCache | None:
        _ = tracker_connection_id
        self.seen_refs.append(remote_ref)
        if self.error is not None:
            raise self.error
        return self.issue


class TestMemxResolver:
    def test_resolve_known_memx_entities(self) -> None:
        resolver = MemxResolver(memx_client=object())

        evidence = resolver.resolve("memx:evidence:123", include_raw=True)
        knowledge = resolver.resolve("memx:knowledge:local:456")
        artifact = resolver.resolve("memx:artifact:local:789")
        lineage = resolver.resolve("memx:lineage:local:999")

        assert evidence.status == ResolveStatus.RESOLVED
        assert evidence.typed_ref == "memx:evidence:local:123"
        assert knowledge.status == ResolveStatus.RESOLVED
        assert artifact.status == ResolveStatus.RESOLVED
        assert lineage.status == ResolveStatus.RESOLVED

    def test_resolve_without_client_returns_unresolved(self) -> None:
        resolver = MemxResolver()
        result = resolver.resolve("memx:evidence:local:123")
        assert result.status == ResolveStatus.UNRESOLVED
        assert result.error_message == "memx_client not configured"

    def test_resolve_unsupported_memx_entity_type(self) -> None:
        resolver = MemxResolver(memx_client=object())
        result = resolver.resolve("memx:unknown:local:123")
        assert result.status == ResolveStatus.UNSUPPORTED

    def test_resolve_many_collects_results(self) -> None:
        resolver = MemxResolver(memx_client=object())
        report = resolver.resolve_many(
            [
                "memx:evidence:local:123",
                "memx:unknown:local:456",
            ]
        )
        assert len(report.resolved) == 1
        assert len(report.unsupported) == 1


class TestTrackerIssueResolver:
    def test_resolve_issue_from_cache(self) -> None:
        issue = IssueCache(
            id="issue-1",
            tracker_connection_id="conn-1",
            remote_issue_id="10001",
            remote_issue_key="PROJ-123",
            title="Investigate sync drift",
            status="In Progress",
            assignee="alice",
            reporter="bob",
            labels_json='["bug"]',
            issue_type="Bug",
            priority="High",
            raw_json='{"key": "PROJ-123"}',
            last_seen_at="2026-03-09T00:00:00Z",
            created_at="2026-03-09T00:00:00Z",
            updated_at="2026-03-09T00:00:00Z",
        )
        repo = IssueCacheRepoStub(issue)
        resolver = TrackerIssueResolver(issue_cache_repo=repo, entity_link_repo=object())

        result = resolver.resolve("tracker:issue:jira:PROJ-123", include_raw=True)

        assert result.status == ResolveStatus.RESOLVED
        assert result.metadata is not None
        assert result.metadata["provider"] == "jira"
        assert result.metadata["tracker_connection_id"] == "conn-1"
        assert repo.seen_refs == ["tracker:issue:jira:PROJ-123"]
        assert result.raw == {"key": "PROJ-123"}

    def test_resolve_missing_issue(self) -> None:
        resolver = TrackerIssueResolver(issue_cache_repo=IssueCacheRepoStub(), entity_link_repo=object())
        result = resolver.resolve("tracker:issue:jira:MISSING")
        assert result.status == ResolveStatus.UNRESOLVED

    def test_resolve_ambiguous_issue(self) -> None:
        resolver = TrackerIssueResolver(
            issue_cache_repo=IssueCacheRepoStub(error=ValueError("ambiguous tracker ref across connections: tracker:issue:jira:PROJ-123")),
            entity_link_repo=object(),
        )
        result = resolver.resolve("tracker:issue:jira:PROJ-123")
        assert result.status == ResolveStatus.UNRESOLVED
        assert result.error_message == "ambiguous tracker ref across connections: tracker:issue:jira:PROJ-123"

    def test_resolve_unsupported_ref(self) -> None:
        resolver = TrackerIssueResolver(issue_cache_repo=IssueCacheRepoStub(), entity_link_repo=object())
        result = resolver.resolve("memx:evidence:local:123")
        assert result.status == ResolveStatus.UNSUPPORTED
