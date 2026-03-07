from __future__ import annotations

import json
import hashlib
from datetime import datetime, UTC
from uuid import uuid4

from tracker_bridge.models import SyncEvent
from tracker_bridge.repositories.sync_event import SyncEventRepository


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
    def __init__(self, repo: SyncEventRepository) -> None:
        self.repo = repo

    def emit_outbound_event(
        self,
        *,
        tracker_connection_id: str,
        remote_ref: str,
        local_ref: str | None,
        event_type: str,
        payload: dict,
        uniqueness_source: str,
    ) -> SyncEvent:
        ts = now_iso()
        model = SyncEvent(
            id=str(uuid4()),
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
        return model

    def mark_applied(self, event_id: str) -> None:
        self.repo.mark_applied(event_id, now_iso())

    def mark_failed(self, event_id: str, error_message: str) -> None:
        self.repo.mark_failed(event_id, error_message, now_iso())

    def list_failed(self) -> list[SyncEvent]:
        return list(self.repo.list(status="failed"))

    def list_pending(self) -> list[SyncEvent]:
        return list(self.repo.list(status="pending"))
