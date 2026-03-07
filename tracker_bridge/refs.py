"""typed_ref utilities for tracker-bridge.

Canonical format (4-segment):
    <domain>:<entity_type>:<provider>:<entity_id>

Examples:
    - tracker:issue:jira:PROJ-123
    - tracker:issue:github:owner/repo#45
    - workx:task:local:01JABCDEF...
    - memx:evidence:local:01JXYZ...
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Known domains (namespace)
KNOWN_DOMAINS: Final[set[str]] = {"tracker", "workx", "memx"}


@dataclass(frozen=True, slots=True)
class TypedRef:
    """Canonical typed reference with 4 segments."""

    domain: str
    entity_type: str
    provider: str
    entity_id: str

    def __str__(self) -> str:
        return f"{self.domain}:{self.entity_type}:{self.provider}:{self.entity_id}"

    @classmethod
    def parse(cls, value: str) -> TypedRef:
        """Parse a typed_ref string into TypedRef object.

        Accepts both canonical (4-segment) and legacy (3-segment) formats.
        Legacy format is normalized with 'local' as default provider.
        """
        parts = value.split(":")
        if len(parts) == 4:
            # Canonical format
            domain, entity_type, provider, entity_id = parts
        elif len(parts) == 3:
            # Legacy format: normalize with 'local' provider
            domain, entity_type, entity_id = parts
            provider = "local"
        else:
            raise ValueError(f"Invalid typed_ref format: {value}")

        if not all([domain, entity_type, provider, entity_id]):
            raise ValueError(f"Invalid typed_ref: empty segment in {value}")

        return cls(
            domain=domain,
            entity_type=entity_type,
            provider=provider,
            entity_id=entity_id,
        )


def make_ref(
    domain: str,
    entity_type: str,
    provider: str,
    entity_id: str,
) -> str:
    """Create a canonical typed_ref string (4-segment)."""
    ref = TypedRef(
        domain=domain,
        entity_type=entity_type,
        provider=provider,
        entity_id=entity_id,
    )
    return str(ref)


def make_tracker_issue_ref(tracker_type: str, issue_key: str) -> str:
    """Create a tracker issue reference.

    Args:
        tracker_type: e.g., 'jira', 'github'
        issue_key: e.g., 'PROJ-123', 'owner/repo#45'

    Returns:
        Canonical ref: 'tracker:issue:<tracker_type>:<issue_key>'
    """
    return make_ref("tracker", "issue", tracker_type, issue_key)


def make_workx_task_ref(task_id: str, provider: str = "local") -> str:
    """Create a workx task reference.

    Args:
        task_id: Task identifier
        provider: Provider name (default: 'local')

    Returns:
        Canonical ref: 'workx:task:<provider>:<task_id>'
    """
    return make_ref("workx", "task", provider, task_id)


def make_memx_evidence_ref(evidence_id: str, provider: str = "local") -> str:
    """Create a memx evidence reference.

    Args:
        evidence_id: Evidence identifier
        provider: Provider name (default: 'local')

    Returns:
        Canonical ref: 'memx:evidence:<provider>:<evidence_id>'
    """
    return make_ref("memx", "evidence", provider, evidence_id)


def validate_typed_ref(value: str) -> bool:
    """Validate a typed_ref string.

    Accepts both canonical (4-segment) and legacy (3-segment) formats.
    Returns True if valid, False otherwise.
    """
    try:
        ref = TypedRef.parse(value)
        return ref.domain in KNOWN_DOMAINS
    except ValueError:
        return False


def canonicalize(value: str) -> str:
    """Canonicalize a typed_ref string to 4-segment format.

    Args:
        value: A typed_ref string (3 or 4 segments)

    Returns:
        Canonical 4-segment typed_ref string
    """
    ref = TypedRef.parse(value)
    return str(ref)


def is_canonical(value: str) -> bool:
    """Check if a typed_ref is in canonical (4-segment) format."""
    return value.count(":") == 3
