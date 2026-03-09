"""Context rebuild service for reconstructing context from typed_refs."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tracker_bridge.refs import canonicalize
from tracker_bridge.resolver.interface import (
    RefResolver,
    ResolvedRef,
    ResolverDiagnostics,
    ResolveReport,
    ResolveStatus,
    SourceKind,
)
from tracker_bridge.services.context_bundle_service import ContextBundleService

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
    """Service for rebuilding context from typed_refs."""

    def __init__(
        self,
        resolvers: list[RefResolver],
        bundle_service: ContextBundleService,
        generator_version: str = "1.0.0",
    ) -> None:
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
        diagnostics = ResolverDiagnostics()
        canonical_refs: list[str] = []

        for ref in source_refs:
            try:
                canonical_refs.append(canonicalize(ref))
            except ValueError:
                diagnostics.unsupported_refs.append(ref)
                diagnostics.resolver_warnings.append(f"Invalid ref format: {ref}")

        report = self._resolve_all(canonical_refs, include_raw=include_raw)

        for unresolved in report.unresolved:
            diagnostics.missing_refs.append(unresolved.typed_ref)
        for unsupported in report.unsupported:
            diagnostics.unsupported_refs.append(unsupported.typed_ref)

        diagnostics.partial_bundle = bool(report.unresolved or report.unsupported)
        resolved_refs = [resolved for resolved in report.resolved if resolved.status == ResolveStatus.RESOLVED]

        bundle = self.bundle_service.create_bundle(
            purpose=purpose,
            summary=self._build_bundle_summary(resolved_refs, report),
            rebuild_level=self._determine_rebuild_level(report, include_raw),
            raw_included=include_raw,
            decision_digest=decision_digest,
            open_question_digest=open_question_digest,
            diagnostics=diagnostics.to_dict(),
            source_refs=[resolved.typed_ref for resolved in resolved_refs],
        )
        return bundle.id, report, diagnostics

    def _resolve_all(
        self,
        typed_refs: list[str],
        *,
        include_raw: bool = False,
    ) -> ResolveReport:
        combined = ResolveReport()
        remaining_refs = list(typed_refs)

        for resolver in self.resolvers:
            if not remaining_refs:
                break

            resolvable = [ref for ref in remaining_refs if resolver.can_resolve(ref)]
            if not resolvable:
                continue

            report = resolver.resolve_many(resolvable, include_raw=include_raw)
            combined.resolved.extend(report.resolved)
            combined.unresolved.extend(report.unresolved)
            combined.unsupported.extend(report.unsupported)

            handled_refs = {
                resolved.typed_ref for resolved in report.resolved + report.unresolved + report.unsupported
            }
            remaining_refs = [ref for ref in remaining_refs if ref not in handled_refs]

        for ref in remaining_refs:
            combined.unsupported.append(
                ResolvedRef(
                    typed_ref=ref,
                    status=ResolveStatus.UNSUPPORTED,
                    error_message="No resolver available",
                )
            )

        return combined

    def _build_bundle_summary(
        self,
        resolved_refs: list[Any],
        report: ResolveReport,
    ) -> str:
        parts = []
        kind_counts: dict[SourceKind, int] = {}
        for ref in resolved_refs:
            if ref.source_kind:
                kind_counts[ref.source_kind] = kind_counts.get(ref.source_kind, 0) + 1

        if kind_counts:
            kind_strs = [f"{kind.value}: {count}" for kind, count in kind_counts.items()]
            parts.append(f"Sources: {', '.join(kind_strs)}")

        parts.append(f"Resolved: {len(report.resolved)}/{report.total_count}")
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
        if report.total_count == 0:
            return "minimal"
        if include_raw and report.success_rate >= 0.9:
            return "full"
        if report.success_rate >= 0.7:
            return "summary"
        return "minimal"

    def should_include_raw(
        self,
        context: str,
        confidence: float | None = None,
        has_open_questions: bool = False,
        has_conflicts: bool = False,
    ) -> bool:
        if context in RAW_INCLUSION_TRIGGERS:
            return True
        if confidence is not None and confidence < 0.7:
            return True
        if has_open_questions:
            return True
        return bool(has_conflicts)
