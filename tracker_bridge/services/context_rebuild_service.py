"""Context rebuild service for reconstructing context from typed_refs."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tracker_bridge.refs import canonicalize
from tracker_bridge.resolver.interface import (
    RefResolver,
    ResolverDiagnostics,
    ResolveReport,
    ResolveStatus,
    SourceKind,
)
from tracker_bridge.services.context_bundle_service import ContextBundleService


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# Conditions that trigger raw inclusion
RAW_INCLUSION_TRIGGERS = [
    "review",
    "conflict_resolution",
    "investigation",
    "verification",
    "low_confidence",
    "high_priority_question",
    "explicit_request",
]


class ContextRebuildService:
    """Service for rebuilding context from typed_refs.

    This is the central service for context reconstruction, coordinating
    multiple resolvers to gather context from various sources.
    """

    def __init__(
        self,
        resolvers: list[RefResolver],
        bundle_service: ContextBundleService,
        generator_version: str = "1.0.0",
    ) -> None:
        """Initialize the context rebuild service.

        Args:
            resolvers: List of resolvers to use for typed_ref resolution
            bundle_service: Service for creating context bundles
            generator_version: Version of the bundle generator
        """
        self.resolvers = resolvers
        self.bundle_service = bundle_service
        self.generator_version = generator_version

    def rebuild_context(
        self,
        *,
        purpose: str,
        source_refs: Sequence[str],
        include_raw: bool = False,
        raw_triggers: list[str] | None = None,  # noqa: ARG002 - reserved for future use
        decision_digest: str | None = None,
        open_question_digest: str | None = None,
    ) -> tuple[str, ResolveReport, ResolverDiagnostics]:
        """Rebuild context from source refs.

        Args:
            purpose: Why this context is being rebuilt
            source_refs: List of typed_ref strings to resolve
            include_raw: Whether to include raw content by default
            raw_triggers: Conditions that trigger raw inclusion
            decision_digest: Summary of decisions
            open_question_digest: Summary of open questions

        Returns:
            Tuple of (bundle_id, resolve_report, diagnostics)
        """
        diagnostics = ResolverDiagnostics()
        canonical_refs = []

        # Normalize and validate refs
        for ref in source_refs:
            try:
                canonical = canonicalize(ref)
                canonical_refs.append(canonical)
            except ValueError:
                diagnostics.unsupported_refs.append(ref)
                diagnostics.resolver_warnings.append(f"Invalid ref format: {ref}")

        # Resolve all refs
        report = self._resolve_all(canonical_refs, include_raw=include_raw)

        # Update diagnostics
        for unresolved in report.unresolved:
            diagnostics.missing_refs.append(unresolved.typed_ref)

        for unsupported in report.unsupported:
            diagnostics.unsupported_refs.append(unsupported.typed_ref)

        diagnostics.partial_bundle = len(report.unresolved) > 0 or len(report.unsupported) > 0

        # Determine which refs need raw content
        resolved_refs = [r for r in report.resolved if r.status == ResolveStatus.RESOLVED]

        # Build bundle
        bundle_summary = self._build_bundle_summary(resolved_refs, report)
        rebuild_level = self._determine_rebuild_level(report, include_raw)

        # Collect source refs for bundle
        bundle_source_refs = [r.typed_ref for r in resolved_refs]

        bundle = self.bundle_service.create_bundle(
            purpose=purpose,
            summary=bundle_summary,
            rebuild_level=rebuild_level,
            raw_included=include_raw,
            decision_digest=decision_digest,
            open_question_digest=open_question_digest,
            diagnostics=diagnostics.to_dict(),
            source_refs=bundle_source_refs,
        )

        return bundle.id, report, diagnostics

    def _resolve_all(
        self,
        typed_refs: list[str],
        *,
        include_raw: bool = False,
    ) -> ResolveReport:
        """Resolve all typed_refs using available resolvers.

        Args:
            typed_refs: List of canonical typed_ref strings
            include_raw: Whether to include raw content

        Returns:
            Combined ResolveReport from all resolvers
        """
        combined = ResolveReport()
        remaining_refs = list(typed_refs)

        for resolver in self.resolvers:
            if not remaining_refs:
                break

            # Find refs this resolver can handle
            resolvable = [ref for ref in remaining_refs if resolver.can_resolve(ref)]

            if resolvable:
                report = resolver.resolve_many(resolvable, include_raw=include_raw)
                combined.resolved.extend(report.resolved)
                combined.unresolved.extend(report.unresolved)
                combined.unsupported.extend(report.unsupported)

                # Remove resolved refs from remaining
                resolved_set = {r.typed_ref for r in report.resolved}
                remaining_refs = [ref for ref in remaining_refs if ref not in resolved_set]

        # Mark remaining as unsupported
        for ref in remaining_refs:
            combined.unsupported.append(
                type('ResolvedRef', (), {
                    'typed_ref': ref,
                    'status': ResolveStatus.UNSUPPORTED,
                    'source_kind': None,
                    'summary': None,
                    'raw': None,
                    'metadata': None,
                    'error_message': 'No resolver available',
                })()
            )

        return combined

    def _build_bundle_summary(
        self,
        resolved_refs: list[Any],
        report: ResolveReport,
    ) -> str:
        """Build a summary string for the bundle.

        Args:
            resolved_refs: List of successfully resolved refs
            report: Full resolve report

        Returns:
            Human-readable summary
        """
        parts = []

        # Count by source kind
        kind_counts: dict[SourceKind, int] = {}
        for ref in resolved_refs:
            if ref.source_kind:
                kind_counts[ref.source_kind] = kind_counts.get(ref.source_kind, 0) + 1

        if kind_counts:
            kind_strs = [f"{kind.value}: {count}" for kind, count in kind_counts.items()]
            parts.append(f"Sources: {', '.join(kind_strs)}")

        # Add resolution stats
        parts.append(f"Resolved: {len(report.resolved)}/{report.total_count}")

        # Add warnings
        if report.unresolved:
            parts.append(f"Unresolved: {len(report.unresolved)}")
        if report.unsupported:
            parts.append(f"Unsupported: {len(report.unsupported)}")

        return " | ".join(parts)

    def _determine_rebuild_level(
        self,
        report: ResolveReport,
        include_raw: bool,
    ) -> str:
        """Determine the rebuild level based on resolution results.

        Args:
            report: Resolve report
            include_raw: Whether raw content was requested

        Returns:
            Rebuild level string: 'full', 'summary', or 'minimal'
        """
        if report.total_count == 0:
            return "minimal"

        success_rate = report.success_rate

        if include_raw and success_rate >= 0.9:
            return "full"
        elif success_rate >= 0.7:
            return "summary"
        else:
            return "minimal"

    def should_include_raw(
        self,
        context: str,
        confidence: float | None = None,
        has_open_questions: bool = False,
        has_conflicts: bool = False,
    ) -> bool:
        """Determine if raw content should be included.

        Args:
            context: Current context/phase
            confidence: Confidence level (0.0-1.0)
            has_open_questions: Whether there are high-priority open questions
            has_conflicts: Whether there are conflicting summaries

        Returns:
            True if raw content should be included
        """
        # Explicit triggers
        if context in RAW_INCLUSION_TRIGGERS:
            return True

        # Low confidence decisions
        if confidence is not None and confidence < 0.7:
            return True

        # High priority open questions
        if has_open_questions:
            return True

        # Conflicting summaries
        return bool(has_conflicts)
