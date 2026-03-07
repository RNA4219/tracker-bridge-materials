"""Service for creating context bundles with audit information."""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tracker_bridge.models import ContextBundle, ContextBundleSource
from tracker_bridge.refs import TypedRef, canonicalize
from tracker_bridge.repositories.context_bundle import ContextBundleRepository
from tracker_bridge.repositories.context_bundle_source import ContextBundleSourceRepository


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Default generator version - should be updated when bundle format changes
BUNDLE_GENERATOR_VERSION = "1.0.0"


class ContextBundleService:
    """Service for creating and managing context bundles with audit info."""

    def __init__(
        self,
        bundle_repo: ContextBundleRepository,
        source_repo: ContextBundleSourceRepository,
        generator_version: str = BUNDLE_GENERATOR_VERSION,
    ) -> None:
        self.bundle_repo = bundle_repo
        self.source_repo = source_repo
        self.generator_version = generator_version

    def create_bundle(
        self,
        *,
        purpose: str,
        summary: str,
        rebuild_level: str = "summary",
        raw_included: bool = False,
        decision_digest: str | None = None,
        open_question_digest: str | None = None,
        diagnostics: dict[str, Any] | None = None,
        source_refs: Sequence[str] | None = None,
    ) -> ContextBundle:
        """Create a context bundle with audit information.

        Args:
            purpose: Why this bundle was created ('resume', 'handoff', 'checkpoint', 'audit')
            summary: Human-readable summary of the bundle contents
            rebuild_level: How complete the bundle is ('full', 'summary', 'minimal')
            raw_included: Whether raw evidence is included
            decision_digest: Summary of decisions
            open_question_digest: Summary of open questions
            diagnostics: Diagnostic information (missing refs, warnings, etc.)
            source_refs: List of typed_ref strings for source entities

        Returns:
            The created ContextBundle
        """
        generated_at = now_iso()
        bundle_id = str(uuid4())

        bundle = ContextBundle(
            id=bundle_id,
            purpose=purpose,
            summary=summary,
            rebuild_level=rebuild_level,
            raw_included=raw_included,
            generator_version=self.generator_version,
            generated_at=generated_at,
            decision_digest=decision_digest,
            open_question_digest=open_question_digest,
            diagnostics_json=json.dumps(diagnostics) if diagnostics else None,
            created_at=generated_at,
        )
        self.bundle_repo.create(bundle)

        # Add source refs if provided
        if source_refs:
            self._add_source_refs(bundle_id, source_refs)

        return bundle

    def _add_source_refs(
        self,
        bundle_id: str,
        source_refs: Sequence[str],
    ) -> None:
        """Add source refs to a bundle."""
        sources = []
        for ref in source_refs:
            # Ensure canonical format
            canonical_ref = canonicalize(ref)
            typed_ref = TypedRef.parse(canonical_ref)

            # Determine source_kind from entity_type
            source_kind = self._get_source_kind(typed_ref.entity_type)

            source = ContextBundleSource(
                id=str(uuid4()),
                context_bundle_id=bundle_id,
                typed_ref=canonical_ref,
                source_kind=source_kind,
                selected_raw=False,
                metadata_json=None,
                created_at=now_iso(),
            )
            sources.append(source)

        self.source_repo.create_batch(sources)

    def _get_source_kind(self, entity_type: str) -> str:
        """Map entity_type to source_kind."""
        mapping = {
            "evidence": "evidence",
            "artifact": "artifact",
            "decision": "decision",
            "issue": "tracker_issue",
            "task": "task",
        }
        return mapping.get(entity_type, "task")

    def get_bundle_with_sources(
        self,
        bundle_id: str,
    ) -> tuple[ContextBundle, list[ContextBundleSource]]:
        """Get a bundle and all its source refs."""
        bundle = self.bundle_repo.get(bundle_id)
        sources = list(self.source_repo.list_by_bundle(bundle_id))
        return bundle, sources

    def list_source_refs(self, bundle_id: str) -> list[str]:
        """List all source refs for a bundle."""
        sources = self.source_repo.list_by_bundle(bundle_id)
        return [s.typed_ref for s in sources]

    def check_raw_included(self, bundle_id: str) -> bool:
        """Check if a bundle includes raw evidence."""
        bundle = self.bundle_repo.get(bundle_id)
        return bundle.raw_included

    def compare_generator_version(
        self,
        bundle_id: str,
    ) -> tuple[str, bool]:
        """Compare bundle's generator version with current.

        Returns:
            Tuple of (bundle_version, is_current)
        """
        bundle = self.bundle_repo.get(bundle_id)
        return bundle.generator_version, bundle.generator_version == self.generator_version
