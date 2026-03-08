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
    """Resolver for memx:* typed_refs.

    This resolver interfaces with memx-core to resolve:
    - memx:evidence:* -> Evidence records
    - memx:knowledge:* -> KnowledgeCard records
    - memx:artifact:* -> Artifact records
    - memx:lineage:* -> LineageEdge records

    memx-core API is typically accessed via HTTP or direct Go/Python binding.
    """

    def __init__(self, memx_client: Any | None = None) -> None:
        """Initialize resolver with memx-core client.

        Args:
            memx_client: HTTP client or binding for memx-core API
        """
        self.memx_client = memx_client

    def can_resolve(self, typed_ref: str) -> bool:
        """Check if this resolver can handle the given typed_ref.

        Args:
            typed_ref: The typed_ref string

        Returns:
            True if this is a memx:* ref
        """
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
        """Resolve a memx typed_ref.

        Args:
            typed_ref: The typed_ref string
            include_raw: Whether to include raw content

        Returns:
            ResolvedRef with the resolved content
        """
        if not self.can_resolve(typed_ref):
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNSUPPORTED,
                error_message="Not a memx ref",
            )

        try:
            ref = TypedRef.parse(typed_ref)
            entity_type = ref.entity_type
            entity_id = ref.entity_id

            # Resolve based on entity type
            if entity_type == "evidence":
                return self._resolve_evidence(entity_id, include_raw)
            elif entity_type == "knowledge":
                return self._resolve_knowledge(entity_id, include_raw)
            elif entity_type == "artifact":
                return self._resolve_artifact(entity_id)
            elif entity_type == "lineage":
                return self._resolve_lineage(entity_id)
            else:
                return ResolvedRef(
                    typed_ref=typed_ref,
                    status=ResolveStatus.UNSUPPORTED,
                    error_message=f"Unsupported memx entity type: {entity_type}",
                )

        except Exception as e:
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_evidence(self, evidence_id: str, include_raw: bool) -> ResolvedRef:  # noqa: ARG002
        """Resolve an evidence record."""
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=f"memx:evidence:{evidence_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            # Call memx-core evidence.get API
            # client.get_evidence(evidence_id)
            # For now, return placeholder
            return ResolvedRef(
                typed_ref=f"memx:evidence:{evidence_id}",
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.EVIDENCE,
                summary=f"Evidence {evidence_id}",
                metadata={"evidence_id": evidence_id},
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=f"memx:evidence:{evidence_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_knowledge(self, knowledge_id: str, include_raw: bool) -> ResolvedRef:  # noqa: ARG002
        """Resolve a knowledge record."""
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=f"memx:knowledge:{knowledge_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            # Call memx-core knowledge.get API
            return ResolvedRef(
                typed_ref=f"memx:knowledge:{knowledge_id}",
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.KNOWLEDGE,
                summary=f"Knowledge {knowledge_id}",
                metadata={"knowledge_id": knowledge_id},
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=f"memx:knowledge:{knowledge_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_artifact(self, artifact_id: str) -> ResolvedRef:
        """Resolve an artifact record."""
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=f"memx:artifact:{artifact_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            return ResolvedRef(
                typed_ref=f"memx:artifact:{artifact_id}",
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.ARTIFACT,
                summary=f"Artifact {artifact_id}",
                metadata={"artifact_id": artifact_id},
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=f"memx:artifact:{artifact_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message=str(e),
            )

    def _resolve_lineage(self, lineage_id: str) -> ResolvedRef:
        """Resolve a lineage record."""
        if not self.memx_client:
            return ResolvedRef(
                typed_ref=f"memx:lineage:{lineage_id}",
                status=ResolveStatus.UNRESOLVED,
                error_message="memx_client not configured",
            )

        try:
            return ResolvedRef(
                typed_ref=f"memx:lineage:{lineage_id}",
                status=ResolveStatus.RESOLVED,
                source_kind=SourceKind.EVIDENCE,  # Lineage is evidence-related
                summary=f"Lineage {lineage_id}",
                metadata={"lineage_id": lineage_id},
            )
        except Exception as e:
            return ResolvedRef(
                typed_ref=f"memx:lineage:{lineage_id}",
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
            typed_refs: List of typed_ref strings
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

    def _get_source_kind(self, entity_type: str) -> SourceKind:
        """Map memx entity_type to SourceKind."""
        mapping = {
            "evidence": SourceKind.EVIDENCE,
            "knowledge": SourceKind.KNOWLEDGE,
            "artifact": SourceKind.ARTIFACT,
            "lineage": SourceKind.EVIDENCE,
        }
        return mapping.get(entity_type, SourceKind.EVIDENCE)


class MockMemxResolver(RefResolver):
    """Mock memx resolver for testing."""

    def __init__(self, data: dict[str, dict[str, Any]] | None = None) -> None:
        """Initialize with mock data.

        Args:
            data: Dict mapping typed_ref to resolved data
        """
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

        if typed_ref in self.data:
            data = self.data[typed_ref]
            ref = TypedRef.parse(typed_ref)
            source_kind = self._get_source_kind(ref.entity_type)
            return ResolvedRef(
                typed_ref=typed_ref,
                status=ResolveStatus.RESOLVED,
                source_kind=source_kind,
                summary=data.get("summary"),
                raw=data if include_raw else None,
                metadata=data.get("metadata"),
            )

        return ResolvedRef(
            typed_ref=typed_ref,
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
        }
        return mapping.get(entity_type, SourceKind.EVIDENCE)
