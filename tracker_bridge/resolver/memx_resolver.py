"""memx-core resolver for resolving memx:* typed_refs."""
from __future__ import annotations

from typing import Any

from tracker_bridge.refs import TypedRef
from tracker_bridge.resolver.interface import (
    RefResolver,
    ResolvedRef,
    ResolveReport,
    ResolveStatus,
    SourceKind,
)


class MemxResolver(RefResolver):
    """Resolver for memx:* typed_refs."""

    def __init__(self, memx_client: Any | None = None) -> None:
        self.memx_client = memx_client

    def can_resolve(self, typed_ref: str) -> bool:
        try:
            ref = TypedRef.parse(typed_ref)
            return ref.is_memx
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
                error_message="Not a memx ref",
            )

        try:
            ref = TypedRef.parse(typed_ref)
            canonical_ref = str(ref)
            entity_type = ref.entity_type
            entity_id = ref.entity_id

            if entity_type == "evidence":
                return self._resolve_evidence(canonical_ref, entity_id, include_raw)
            if entity_type == "knowledge":
                return self._resolve_knowledge(canonical_ref, entity_id, include_raw)
            if entity_type == "artifact":
                return self._resolve_artifact(canonical_ref, entity_id)
            if entity_type == "lineage":
                return self._resolve_lineage(canonical_ref, entity_id)
            return ResolvedRef(
                typed_ref=canonical_ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message=f"Unsupported memx entity type: {entity_type}",
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_evidence(self, typed_ref: str, evidence_id: str, include_raw: bool) -> ResolvedRef:  # noqa: ARG002
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.EVIDENCE,
                summary=f"Evidence {evidence_id}",
                metadata={"evidence_id": evidence_id},
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_knowledge(self, typed_ref: str, knowledge_id: str, include_raw: bool) -> ResolvedRef:  # noqa: ARG002
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.KNOWLEDGE,
                summary=f"Knowledge {knowledge_id}",
                metadata={"knowledge_id": knowledge_id},
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_artifact(self, typed_ref: str, artifact_id: str) -> ResolvedRef:
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.ARTIFACT,
                summary=f"Artifact {artifact_id}",
                metadata={"artifact_id": artifact_id},
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_lineage(self, typed_ref: str, lineage_id: str) -> ResolvedRef:
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.EVIDENCE,
                summary=f"Lineage {lineage_id}",
                metadata={"lineage_id": lineage_id},
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


class MockMemxResolver(RefResolver):
    """Mock memx resolver for testing."""

    def __init__(self, data: dict[str, dict[str, Any]] | None = None) -> None:
        self.data = data or {}

    def can_resolve(self, typed_ref: str) -> bool:
        try:
            ref = TypedRef.parse(typed_ref)
            return ref.is_memx
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
        if canonical_ref in self.data:
            data = self.data[canonical_ref]
            ref = TypedRef.parse(canonical_ref)
            source_kind = self._get_source_kind(ref.entity_type)
            return ResolvedRef(
                typed_ref=canonical_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=source_kind,
                summary=data.get("summary"),
                raw=data if include_raw else None,
                metadata=data.get("metadata"),
            )

        return ResolvedRef(
            typed_ref=canonical_ref,
            status=ResolveStatus.UNRESOLVED,
            error_message="Not found in mock data",
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

    def _get_source_kind(self, entity_type: str) -> SourceKind:
        mapping = {
            "evidence": SourceKind.EVIDENCE,
            "knowledge": SourceKind.KNOWLEDGE,
            "artifact": SourceKind.ARTIFACT,
            "lineage": SourceKind.EVIDENCE,
        }
        return mapping.get(entity_type, SourceKind.EVIDENCE)

