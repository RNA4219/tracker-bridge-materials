"""Resolver interface for typed_ref resolution.

This module defines the abstract interface for resolving typed_refs
in the context rebuild process.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ResolveStatus(str, Enum):
    """Status of a resolved reference."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    UNSUPPORTED = "unsupported"


class SourceKind(str, Enum):
    """Kind of source for resolved content."""

    EVIDENCE = "evidence"
    ARTIFACT = "artifact"
    KNOWLEDGE = "knowledge"
    TRACKER_ISSUE = "tracker_issue"
    TASK = "task"
    DECISION = "decision"


@dataclass
class ResolvedRef:
    """Result of resolving a single typed_ref."""

    typed_ref: str
    status: ResolveStatus
    source_kind: SourceKind | None = None
    summary: str | None = None
    raw: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    error_message: str | None = None


@dataclass
class ResolveReport:
    """Report of resolving multiple typed_refs."""

    resolved: list[ResolvedRef] = field(default_factory=list)
    unresolved: list[ResolvedRef] = field(default_factory=list)
    unsupported: list[ResolvedRef] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.resolved) + len(self.unresolved) + len(self.unsupported)

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return len(self.resolved) / self.total_count


@dataclass
class ResolverDiagnostics:
    """Diagnostics from the resolver process."""

    missing_refs: list[str] = field(default_factory=list)
    unsupported_refs: list[str] = field(default_factory=list)
    resolver_warnings: list[str] = field(default_factory=list)
    partial_bundle: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "missing_refs": self.missing_refs,
            "unsupported_refs": self.unsupported_refs,
            "resolver_warnings": self.resolver_warnings,
            "partial_bundle": self.partial_bundle,
        }


class RefResolver(Protocol):
    """Protocol for resolving typed_refs.

    Implementations should handle specific domains (memx, tracker, workx).
    """

    def can_resolve(self, typed_ref: str) -> bool:
        """Check if this resolver can handle the given typed_ref."""
        ...

    def resolve(
        self,
        typed_ref: str,
        *,
        include_raw: bool = False,
    ) -> ResolvedRef:
        """Resolve a typed_ref to its content.

        Args:
            typed_ref: The canonical typed_ref string
            include_raw: Whether to include raw content

        Returns:
            ResolvedRef with the resolution result
        """
        ...

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
        ...


class SummaryFirstResolver(Protocol):
    """Protocol for summary-first retrieval.

    Prefers summaries over raw content for efficiency.
    """

    def load_summary(self, typed_ref: str) -> dict[str, Any] | None:
        """Load summary for a typed_ref.

        Args:
            typed_ref: The canonical typed_ref string

        Returns:
            Summary dict or None if not available
        """
        ...

    def load_selected_raw(
        self,
        typed_ref: str,
        selector: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Load selected raw content for a typed_ref.

        Args:
            typed_ref: The canonical typed_ref string
            selector: Optional selector to filter content

        Returns:
            Raw content dict or None if not available
        """
        ...
