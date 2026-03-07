"""Service for tracking state transitions (append-only history)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tracker_bridge.models import StateTransition
from tracker_bridge.repositories.state_transition import StateTransitionRepository


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateTransitionService:
    """Centralized state transition tracking.

    All status changes should go through this service to ensure
    append-only history is maintained.
    """

    def __init__(self, repo: StateTransitionRepository) -> None:
        self.repo = repo

    def record_transition(
        self,
        *,
        entity_type: str,
        entity_id: str,
        from_status: str | None,
        to_status: str,
        reason: str | None = None,
        actor_type: str = "system",
        actor_id: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StateTransition:
        """Record a state transition.

        Args:
            entity_type: Type of entity ('sync_event', 'issue_cache', 'entity_link')
            entity_id: ID of the entity
            from_status: Previous status (None for initial state)
            to_status: New status
            reason: Reason for transition (required for exceptional transitions)
            actor_type: Who initiated the transition ('system', 'user', 'agent')
            actor_id: ID of the actor (if applicable)
            run_id: Associated run ID (if applicable)
            metadata: Additional metadata

        Returns:
            The created StateTransition record
        """
        ts = now_iso()
        transition = StateTransition(
            id=str(uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor_type=actor_type,
            actor_id=actor_id,
            run_id=run_id,
            changed_at=ts,
            created_at=ts,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self.repo.create(transition)
        return transition

    def get_history(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[StateTransition]:
        """Get full transition history for an entity."""
        return list(self.repo.list_by_entity(entity_type, entity_id))

    def get_latest(
        self,
        entity_type: str,
        entity_id: str,
    ) -> StateTransition | None:
        """Get the most recent transition for an entity."""
        return self.repo.get_latest(entity_type, entity_id)
