from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from tracker_bridge.models import SyncEvent
from tracker_bridge.repositories.sync_event import SyncEventRepository

if TYPE_CHECKING:
    from tracker_bridge.models import StateTransition
    from tracker_bridge.services.state_transition_service import StateTransitionService


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_fingerprint(
    *,
    tracker_connection_id: str,
    direction: str,
    remote_ref: str,
    event_type: str,
    uniqueness_source: str,
) -> str:
    raw = "|".join(
        [
            tracker_connection_id,
            direction,
            remote_ref,
            event_type,
            uniqueness_source,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SyncService:
    """Service for managing sync events with state transition tracking."""

    def __init__(
        self,
        repo: SyncEventRepository,
        transition_service: StateTransitionService | None = None,
    ) -> None:
        self.repo = repo
        self.transition_service = transition_service

    def emit_outbound_event(
        self,
        *,
        tracker_connection_id: str,
        remote_ref: str,
        local_ref: str | None,
        event_type: str,
        payload: dict[str, object],
        uniqueness_source: str,
    ) -> SyncEvent:
        ts = now_iso()
        event_id = str(uuid4())
        model = SyncEvent(
            id=event_id,
            tracker_connection_id=tracker_connection_id,
            direction="outbound",
            remote_ref=remote_ref,
            local_ref=local_ref,
            event_type=event_type,
            fingerprint=make_fingerprint(
                tracker_connection_id=tracker_connection_id,
                direction="outbound",
                remote_ref=remote_ref,
                event_type=event_type,
                uniqueness_source=uniqueness_source,
            ),
            payload_json=json.dumps(payload, ensure_ascii=False),
            status="pending",
            error_message=None,
            occurred_at=ts,
            processed_at=None,
            created_at=ts,
        )
        self.repo.create(model)

        # Record initial state transition
        if self.transition_service:
            self.transition_service.record_transition(
                entity_type="sync_event",
                entity_id=event_id,
                from_status=None,
                to_status="pending",
                reason="event_created",
                actor_type="system",
            )

        return model

    def mark_applied(self, event_id: str) -> None:
        # Get current status for transition
        from_status = None
        if self.transition_service:
            latest = self.transition_service.get_latest("sync_event", event_id)
            if latest:
                from_status = latest.to_status

        self.repo.mark_applied(event_id, now_iso())

        # Record transition
        if self.transition_service:
            self.transition_service.record_transition(
                entity_type="sync_event",
                entity_id=event_id,
                from_status=from_status,
                to_status="applied",
                reason="event_processed",
                actor_type="system",
            )

    def mark_failed(
        self,
        event_id: str,
        error_message: str,
        reason: str | None = None,
    ) -> None:
        # Get current status for transition
        from_status = None
        if self.transition_service:
            latest = self.transition_service.get_latest("sync_event", event_id)
            if latest:
                from_status = latest.to_status

        self.repo.mark_failed(event_id, error_message, now_iso())

        # Record transition with reason
        if self.transition_service:
            self.transition_service.record_transition(
                entity_type="sync_event",
                entity_id=event_id,
                from_status=from_status,
                to_status="failed",
                reason=reason or error_message,
                actor_type="system",
                metadata={"error_message": error_message},
            )

    def mark_skipped(
        self,
        event_id: str,
        reason: str,
    ) -> None:
        """Mark an event as skipped with a reason."""
        from_status = None
        if self.transition_service:
            latest = self.transition_service.get_latest("sync_event", event_id)
            if latest:
                from_status = latest.to_status

        # Update status to skipped
        self.repo.mark_skipped(event_id, now_iso())

        if self.transition_service:
            self.transition_service.record_transition(
                entity_type="sync_event",
                entity_id=event_id,
                from_status=from_status,
                to_status="skipped",
                reason=reason,
                actor_type="system",
            )

    def list_failed(self) -> list[SyncEvent]:
        return list(self.repo.list(status="failed"))

    def list_pending(self) -> list[SyncEvent]:
        return list(self.repo.list(status="pending"))

    def get_transition_history(self, event_id: str) -> list[StateTransition]:
        """Get the full transition history for a sync event."""
        if not self.transition_service:
            return []
        return self.transition_service.get_history("sync_event", event_id)
