from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from tracker_bridge.models import TrackerConnection
from tracker_bridge.repositories.connection import TrackerConnectionRepository


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ConnectionService:
    def __init__(self, repo: TrackerConnectionRepository) -> None:
        self.repo = repo

    def create_connection(
        self,
        *,
        tracker_type: str,
        name: str,
        base_url: str,
        workspace_key: str | None = None,
        project_key: str | None = None,
        secret_ref: str | None = None,
    ) -> TrackerConnection:
        ts = now_iso()
        model = TrackerConnection(
            id=str(uuid4()),
            tracker_type=tracker_type,
            name=name,
            base_url=base_url,
            workspace_key=workspace_key,
            project_key=project_key,
            secret_ref=secret_ref,
            is_enabled=True,
            created_at=ts,
            updated_at=ts,
            metadata_json=None,
        )
        self.repo.create(model)
        return model

    def list_connections(self) -> list[TrackerConnection]:
        return list(self.repo.list_all())

    def disable_connection(self, connection_id: str) -> None:
        self.repo.update_enabled(connection_id, False, now_iso())

    def enable_connection(self, connection_id: str) -> None:
        self.repo.update_enabled(connection_id, True, now_iso())
