"""typed_ref utilities for tracker-bridge.

Format (domain-dependent):
    - memx:   3-segment: <domain>:<entity_type>:<entity_id>
    - agent-taskstate:  3-segment: <domain>:<entity_type>:<entity_id>
    - tracker: 4-segment: <domain>:<entity_type>:<provider>:<entity_id>

Examples:
    - memx:evidence:01JXYZ...
    - memx:knowledge:01HABC...
    - agent-taskstate:task:01JABCDEF...
    - tracker:issue:jira:PROJ-123
    - tracker:issue:github:owner/repo#45
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Known domains (namespace)
KNOWN_DOMAINS: Final[set[str]] = {"tracker", "agent-taskstate", "memx"}

# Domains that use 3-segment format (no provider)
THREE_SEGMENT_DOMAINS: Final[set[str]] = {"memx", "agent-taskstate"}

# Domains that use 4-segment format (with provider)
FOUR_SEGMENT_DOMAINS: Final[set[str]] = {"tracker"}


@dataclass(frozen=True)
class TypedRef:
    """Typed reference with domain-dependent format."""

    domain: str
    entity_type: str
    entity_id: str
    provider: str | None = None  # Only for tracker domain

    def __str__(self) -> str:
        if self.domain in THREE_SEGMENT_DOMAINS:
            return f"{self.domain}:{self.entity_type}:{self.entity_id}"
        else:
            return f"{self.domain}:{self.entity_type}:{self.provider}:{self.entity_id}"

    @classmethod
    def parse(cls, value: str) -> TypedRef:
        """Parse a typed_ref string into TypedRef object.

        Accepts both 3-segment and 4-segment formats based on domain.
        """
        parts = value.split(":")

        if len(parts) == 3:
            # 3-segment format (memx, agent-taskstate)
            domain, entity_type, entity_id = parts
            if not all([domain, entity_type, entity_id]):
                raise ValueError(f"Invalid typed_ref: empty segment in {value}")
            return cls(
                domain=domain,
                entity_type=entity_type,
                entity_id=entity_id,
                provider=None,
            )

        elif len(parts) == 4:
            # 4-segment format (tracker)
            domain, entity_type, provider, entity_id = parts
            if not all([domain, entity_type, provider, entity_id]):
                raise ValueError(f"Invalid typed_ref: empty segment in {value}")
            return cls(
                domain=domain,
                entity_type=entity_type,
                provider=provider,
                entity_id=entity_id,
            )

        else:
            raise ValueError(f"Invalid typed_ref format: {value}")

    @property
    def is_memx(self) -> bool:
        """Check if this is a memx reference."""
        return self.domain == "memx"

    @property
    def is_agent_taskstate(self) -> bool:
        """Check if this is an agent-taskstate reference."""
        return self.domain == "agent-taskstate"

    @property
    def is_tracker(self) -> bool:
        """Check if this is a tracker reference."""
        return self.domain == "tracker"


def make_ref(
    domain: str,
    entity_type: str,
    entity_id: str,
    provider: str | None = None,
) -> str:
    """Create a typed_ref string.

    Args:
        domain: Domain (memx, agent-taskstate, tracker)
        entity_type: Entity type (evidence, task, issue, etc.)
        entity_id: Entity identifier
        provider: Provider (only required for tracker domain)

    Returns:
        typed_ref string
    """
    ref = TypedRef(
        domain=domain,
        entity_type=entity_type,
        entity_id=entity_id,
        provider=provider,
    )
    return str(ref)


def make_tracker_issue_ref(tracker_type: str, issue_key: str) -> str:
    """Create a tracker issue reference.

    Args:
        tracker_type: e.g., 'jira', 'github'
        issue_key: e.g., 'PROJ-123', 'owner/repo#45'

    Returns:
        Ref: 'tracker:issue:<tracker_type>:<issue_key>'
    """
    return make_ref("tracker", "issue", issue_key, provider=tracker_type)


def make_agent_taskstate_task_ref(task_id: str) -> str:
    """Create an agent-taskstate task reference.

    Args:
        task_id: Task identifier

    Returns:
        Ref: 'agent-taskstate:task:<task_id>'
    """
    return make_ref("agent-taskstate", "task", task_id)


def make_memx_evidence_ref(evidence_id: str) -> str:
    """Create a memx evidence reference.

    Args:
        evidence_id: Evidence identifier

    Returns:
        Ref: 'memx:evidence:<evidence_id>'
    """
    return make_ref("memx", "evidence", evidence_id)


def make_memx_knowledge_ref(knowledge_id: str) -> str:
    """Create a memx knowledge reference.

    Args:
        knowledge_id: Knowledge identifier

    Returns:
        Ref: 'memx:knowledge:<knowledge_id>'
    """
    return make_ref("memx", "knowledge", knowledge_id)


def make_memx_artifact_ref(artifact_id: str) -> str:
    """Create a memx artifact reference.

    Args:
        artifact_id: Artifact identifier

    Returns:
        Ref: 'memx:artifact:<artifact_id>'
    """
    return make_ref("memx", "artifact", artifact_id)


def validate_typed_ref(value: str) -> bool:
    """Validate a typed_ref string.

    Returns True if valid, False otherwise.
    """
    try:
        ref = TypedRef.parse(value)
        return ref.domain in KNOWN_DOMAINS
    except ValueError:
        return False


def canonicalize(value: str) -> str:
    """Canonicalize a typed_ref string.

    Args:
        value: A typed_ref string

    Returns:
        Canonical typed_ref string
    """
    ref = TypedRef.parse(value)
    return str(ref)


def is_memx_ref(value: str) -> bool:
    """Check if a typed_ref is a memx reference."""
    try:
        ref = TypedRef.parse(value)
        return ref.is_memx
    except ValueError:
        return False


def is_agent_taskstate_ref(value: str) -> bool:
    """Check if a typed_ref is an agent-taskstate reference."""
    try:
        ref = TypedRef.parse(value)
        return ref.is_agent_taskstate
    except ValueError:
        return False


def is_tracker_ref(value: str) -> bool:
    """Check if a typed_ref is a tracker reference."""
    try:
        ref = TypedRef.parse(value)
        return ref.is_tracker
    except ValueError:
        return False
