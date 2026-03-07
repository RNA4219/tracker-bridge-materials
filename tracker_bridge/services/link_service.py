from __future__ import annotations

from datetime import datetime, UTC
from uuid import uuid4

from tracker_bridge.errors import ValidationError
from tracker_bridge.models import EntityLink
from tracker_bridge.refs import validate_typed_ref
from tracker_bridge.repositories.entity_link import EntityLinkRepository


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class LinkService:
    def __init__(self, repo: EntityLinkRepository) -> None:
        self.repo = repo

    def create_link(
        self,
        *,
        local_ref: str,
        remote_ref: str,
        link_role: str = "primary",
    ) -> EntityLink:
        if not validate_typed_ref(local_ref):
            raise ValidationError(f"invalid local_ref: {local_ref}")
        if not validate_typed_ref(remote_ref):
            raise ValidationError(f"invalid remote_ref: {remote_ref}")

        ts = now_iso()
        model = EntityLink(
            id=str(uuid4()),
            local_ref=local_ref,
            remote_ref=remote_ref,
            link_role=link_role,
            created_at=ts,
            updated_at=ts,
            metadata_json=None,
        )
        self.repo.create(model)
        return model

    def list_by_local_ref(self, local_ref: str) -> list[EntityLink]:
        return list(self.repo.list_by_local_ref(local_ref))

    def list_by_remote_ref(self, remote_ref: str) -> list[EntityLink]:
        return list(self.repo.list_by_remote_ref(remote_ref))
