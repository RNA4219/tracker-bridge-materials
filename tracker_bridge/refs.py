"""typed_ref utilities for tracker-bridge.

Canonical format:
    <domain>:<entity_type>:<provider>:<entity_id>

Migration compatibility:
    - memx:<entity_type>:<entity_id>
      -> memx:<entity_type>:local:<entity_id>
    - agent-taskstate:<entity_type>:<entity_id>
      -> agent-taskstate:<entity_type>:local:<entity_id>
    - tracker:<provider>:<entity_id>
      -> tracker:issue:<provider>:<entity_id>

Examples:
    - memx:evidence:local:01JXYZ...
    - memx:knowledge:local:01HABC...
    - agent-taskstate:task:local:01JABCDEF...
    - tracker:issue:jira:PROJ-123
    - tracker:issue:github:owner/repo#45
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

KNOWN_DOMAINS: Final[set[str]] = {"tracker", "agent-taskstate", "memx"}
LOCAL_PROVIDER: Final[str] = "local"
TRACKER_DOMAIN: Final[str] = "tracker"
TRACKER_DEFAULT_ENTITY_TYPE: Final[str] = "issue"
LOCAL_DOMAINS: Final[set[str]] = {"memx", "agent-taskstate"}


@dataclass(frozen=True)
class TypedRef:
    """Typed reference with canonical 4-segment format."""

    domain: str
    entity_type: str
    entity_id: str
    provider: str | None = None

    def __post_init__(self) -> None:
        if self.domain not in KNOWN_DOMAINS:
            raise ValueError(f"Unknown typed_ref domain: {self.domain}")
        if not self.entity_type or not self.entity_id:
            raise ValueError("Invalid typed_ref: empty segment")

        provider = self.provider
        if not provider and self.domain in LOCAL_DOMAINS:
            provider = LOCAL_PROVIDER
        if not provider:
            raise ValueError("Invalid typed_ref: provider is required")

        object.__setattr__(self, "provider", provider)

    def __str__(self) -> str:
        return f"{self.domain}:{self.entity_type}:{self.provider}:{self.entity_id}"

    @classmethod
    def parse(cls, value: str) -> TypedRef:
        """Parse a typed_ref string into a canonical TypedRef object."""
        parts = value.split(":")

        if len(parts) == 3:
            domain, second, third = parts
            if not all((domain, second, third)):
                raise ValueError(f"Invalid typed_ref: empty segment in {value}")
            if domain in LOCAL_DOMAINS:
                return cls(
                    domain=domain,
                    entity_type=second,
                    entity_id=third,
                    provider=LOCAL_PROVIDER,
                )
            if domain == TRACKER_DOMAIN:
                if second == TRACKER_DEFAULT_ENTITY_TYPE:
                    raise ValueError(f"Invalid typed_ref format: {value}")
                return cls(
                    domain=domain,
                    entity_type=TRACKER_DEFAULT_ENTITY_TYPE,
                    entity_id=third,
                    provider=second,
                )
            raise ValueError(f"Unknown typed_ref domain: {domain}")

        if len(parts) == 4:
            domain, entity_type, provider, entity_id = parts
            if not all((domain, entity_type, provider, entity_id)):
                raise ValueError(f"Invalid typed_ref: empty segment in {value}")
            return cls(
                domain=domain,
                entity_type=entity_type,
                entity_id=entity_id,
                provider=provider,
            )

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
    """Create a canonical typed_ref string."""
    return str(
        TypedRef(
            domain=domain,
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider,
        )
    )


def make_tracker_issue_ref(tracker_type: str, issue_key: str) -> str:
    """Create a tracker issue reference."""
    return make_ref("tracker", "issue", issue_key, provider=tracker_type)


def make_agent_taskstate_task_ref(task_id: str) -> str:
    """Create an agent-taskstate task reference."""
    return make_ref("agent-taskstate", "task", task_id)


def make_memx_evidence_ref(evidence_id: str) -> str:
    """Create a memx evidence reference."""
    return make_ref("memx", "evidence", evidence_id)


def make_memx_knowledge_ref(knowledge_id: str) -> str:
    """Create a memx knowledge reference."""
    return make_ref("memx", "knowledge", knowledge_id)


def make_memx_artifact_ref(artifact_id: str) -> str:
    """Create a memx artifact reference."""
    return make_ref("memx", "artifact", artifact_id)


def validate_typed_ref(value: str) -> bool:
    """Validate a typed_ref string."""
    try:
        TypedRef.parse(value)
        return True
    except ValueError:
        return False


def canonicalize(value: str) -> str:
    """Canonicalize a typed_ref string."""
    return str(TypedRef.parse(value))


def is_memx_ref(value: str) -> bool:
    """Check if a typed_ref is a memx reference."""
    try:
        return TypedRef.parse(value).is_memx
    except ValueError:
        return False


def is_agent_taskstate_ref(value: str) -> bool:
    """Check if a typed_ref is an agent-taskstate reference."""
    try:
        return TypedRef.parse(value).is_agent_taskstate
    except ValueError:
        return False


def is_tracker_ref(value: str) -> bool:
    """Check if a typed_ref is a tracker reference."""
    try:
        return TypedRef.parse(value).is_tracker
    except ValueError:
        return False
