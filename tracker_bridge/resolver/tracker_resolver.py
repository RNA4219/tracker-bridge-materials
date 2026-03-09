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
    """Resolver for tracker:issue:* typed_refs."""

    def __init__(self, issue_cache_repo: Any, entity_link_repo: Any) -> None:
        self.issue_cache_repo = issue_cache_repo
        self.entity_link_repo = entity_link_repo

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
                error_message="Not a tracker:issue ref",
            )

        try:
            ref = TypedRef.parse(typed_ref)
            provider = ref.provider
            if provider is None:
                return ResolvedRef(
                    typed_ref=typed_ref,
                    status=ResolveStatus.UNSUPPORTED,
                    error_message="Tracker ref must have provider",
                )

            issue = self.issue_cache_repo.find_by_remote_ref(str(ref))
            if issue is None:
                return ResolvedRef(
                    typed_ref=typed_ref,
                    status=ResolveStatus.UNRESOLVED,
                    error_message=f"Issue not found in cache: {provider}:{ref.entity_id}",
                )
        except ValueError as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

        summary = self._build_summary(issue)
        raw = json.loads(issue.raw_json) if include_raw and issue.raw_json else None
        return ResolvedRef(
            typed_ref=str(ref),
            status=ResolveStatus.RESOLVED,
            source_kind=SourceKind.TRACKER_ISSUE,
            summary=summary,
            raw=raw,
            metadata={
                "provider": provider,
                "issue_key": ref.entity_id,
                "status": issue.status,
                "title": issue.title,
                "tracker_connection_id": issue.tracker_connection_id,
            },
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

    def _build_summary(self, issue: Any) -> str:
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

        canonical_ref = str(TypedRef.parse(typed_ref))
        if canonical_ref in self.issues:
            data = self.issues[canonical_ref]
            return ResolvedRef(
                typed_ref=canonical_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.TRACKER_ISSUE,
                summary=data.get("summary"),
                raw=data if include_raw else None,
                metadata=data.get("metadata"),
            )

        return ResolvedRef(
            typed_ref=canonical_ref,
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
