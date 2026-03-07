"""Tracker issue resolver for resolving tracker:* typed_refs."""
from __future__ import annotations

import json
from typing import Any

from tracker_bridge.refs import TypedRef
from tracker_bridge.resolver.interface import (
    RefResolver,
    ResolvedRef,
    ResolveReport,
    ResolveStatus,
    SourceKind,
)


class TrackerIssueResolver(RefResolver):
    """Resolver for tracker:issue:* typed_refs.

    Resolves external tracker issue references to their cached content.
    """

    def __init__(self, issue_cache_repo: Any, entity_link_repo: Any) -> None:
        """Initialize resolver with repositories.

        Args:
            issue_cache_repo: Repository for issue cache access
            entity_link_repo: Repository for entity link lookup
        """
        self.issue_cache_repo = issue_cache_repo
        self.entity_link_repo = entity_link_repo

    def can_resolve(self, typed_ref: str) -> bool:
        """Check if this resolver can handle the given typed_ref.

        Args:
            typed_ref: The canonical typed_ref string

        Returns:
            True if this is a tracker:issue:* ref
        """
        try:
            ref = TypedRef.parse(typed_ref)
            return ref.domain == "tracker" and ref.entity_type == "issue"
        except ValueError:
            return False

    def resolve(
        self,
        typed_ref: str,
        *,
        include_raw: bool = False,
    ) -> ResolvedRef:
        """Resolve a tracker issue typed_ref.

        Args:
            typed_ref: The canonical typed_ref string
            include_raw: Whether to include raw issue data

        Returns:
            ResolvedRef with the issue content
        """
        if not self.can_resolve(typed_ref):
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message="Not a tracker:issue ref",
            )

        try:
            ref = TypedRef.parse(typed_ref)
            provider = ref.provider  # e.g., 'jira', 'github'
            issue_key = ref.entity_id  # e.g., 'PROJ-123'

            # Look up issue in cache by remote_issue_key
            # Note: This requires a connection_id mapping which we'll handle
            # For now, we search by remote_issue_key across connections
            issue = self._find_issue_by_key(provider, issue_key)

            if issue is None:
                return ResolvedRef(
                    typed_ref=typed_ref,
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Issue not found in cache: {provider}:{issue_key}",
                )

            summary = self._build_summary(issue)
            raw = None
            if include_raw:
                raw = json.loads(issue.raw_json) if issue.raw_json else None

            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.TRACKER_ISSUE,
                summary=summary,
                raw=raw,
                metadata={
                    "provider": provider,
                    "issue_key": issue_key,
                    "status": issue.status,
                    "title": issue.title,
                },
            )

        except Exception as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def resolve_many(
        self,
        typed_refs: list[str],
        *,
        include_raw: bool = False,
    ) -> ResolveReport:
        """Resolve multiple typed_refs.

        Args:
            typed_refs: List of canonical typed_ref strings
            include_raw: Whether to include raw content

        Returns:
            ResolveReport with all resolution results
        """
        report = ResolveReport()

        for typed_ref in typed_refs:
            result = self.resolve(typed_ref, include_raw=include_raw)

            if result.status == ResolveStatus.RESOLVED:
                report.resolved.append(result)
            elif result.status == ResolveStatus.UNRESOLVED:
                report.unresolved.append(result)
            else:
                report.unsupported.append(result)

        return report

    def _find_issue_by_key(self, provider: str, issue_key: str) -> Any:
        """Find an issue in cache by provider and key.

        Args:
            provider: Tracker type (jira, github, etc.)
            issue_key: Issue key (PROJ-123, owner/repo#45, etc.)

        Returns:
            IssueCache or None
        """
        # This is a simplified implementation
        # In practice, we'd need to query by tracker_connection_id + remote_issue_key
        # For now, we iterate through available issues
        try:
            issues = self.issue_cache_repo.list_by_provider(provider)
            for issue in issues:
                if issue.remote_issue_key == issue_key:
                    return issue
        except Exception:
            pass
        return None

    def _build_summary(self, issue: Any) -> str:
        """Build a summary string for an issue.

        Args:
            issue: IssueCache object

        Returns:
            Human-readable summary
        """
        parts = []
        if issue.title:
            parts.append(f"**{issue.title}**")
        if issue.status:
            parts.append(f"Status: {issue.status}")
        if issue.issue_type:
            parts.append(f"Type: {issue.issue_type}")
        if issue.priority:
            parts.append(f"Priority: {issue.priority}")
        if issue.assignee:
            parts.append(f"Assignee: {issue.assignee}")

        return " | ".join(parts) if parts else f"Issue {issue.remote_issue_key}"


class MockTrackerIssueResolver(RefResolver):
    """Mock resolver for testing without database."""

    def __init__(self, issues: dict[str, dict[str, Any]] | None = None) -> None:
        """Initialize with mock data.

        Args:
            issues: Dict mapping typed_ref to issue data
        """
        self.issues = issues or {}

    def can_resolve(self, typed_ref: str) -> bool:
        try:
            ref = TypedRef.parse(typed_ref)
            return ref.domain == "tracker" and ref.entity_type == "issue"
        except ValueError:
            return False

    def resolve(
        self,
        typed_ref: str,
        *,
        include_raw: bool = False,
    ) -> ResolvedRef:
        if not self.can_resolve(typed_ref):
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNSUPPORTED,
            )

        if typed_ref in self.issues:
            data = self.issues[typed_ref]
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.TRACKER_ISSUE,
                summary=data.get("summary"),
                raw=data if include_raw else None,
                metadata=data.get("metadata"),
            )

        return ResolvedRef(
            typed_ref=typed_ref,
            status=ResolveStatus.UNRESOLVED,
            error_message="Issue not found in mock data",
        )

    def resolve_many(
        self,
        typed_refs: list[str],
        *,
        include_raw: bool = False,
    ) -> ResolveReport:
        report = ResolveReport()
        for typed_ref in typed_refs:
            result = self.resolve(typed_ref, include_raw=include_raw)
            if result.status == ResolveStatus.RESOLVED:
                report.resolved.append(result)
            elif result.status == ResolveStatus.UNRESOLVED:
                report.unresolved.append(result)
            else:
                report.unsupported.append(result)
        return report
