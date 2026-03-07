from __future__ import annotations

import json
import hashlib
from datetime import datetime, UTC
from uuid import uuid4

from tracker_bridge.models import IssueCache, SyncEvent
from tracker_bridge.refs import make_remote_ref
from tracker_bridge.repositories.connection import TrackerConnectionRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
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


class IssueService:
    def __init__(
        self,
        *,
        connection_repo: TrackerConnectionRepository,
        issue_repo: IssueCacheRepository,
        sync_repo: SyncEventRepository,
    ) -> None:
        self.connection_repo = connection_repo
        self.issue_repo = issue_repo
        self.sync_repo = sync_repo

    def import_normalized_issue(
        self,
        *,
        tracker_connection_id: str,
        normalized_issue,
    ) -> IssueCache:
        connection = self.connection_repo.get(tracker_connection_id)
        ts = now_iso()

        issue = IssueCache(
            id=str(uuid4()),
            tracker_connection_id=tracker_connection_id,
            remote_issue_id=normalized_issue.remote_issue_id,
            remote_issue_key=normalized_issue.remote_issue_key,
            title=normalized_issue.title,
            status=normalized_issue.status,
            assignee=normalized_issue.assignee,
            reporter=normalized_issue.reporter,
            labels_json=json.dumps(normalized_issue.labels, ensure_ascii=False),
            issue_type=normalized_issue.issue_type,
            priority=normalized_issue.priority,
            raw_json=json.dumps(normalized_issue.raw, ensure_ascii=False),
            last_seen_at=ts,
            created_at=ts,
            updated_at=ts,
        )
        self.issue_repo.upsert(issue)

        remote_ref = make_remote_ref(connection.tracker_type, normalized_issue.remote_issue_key)
        fingerprint = make_fingerprint(
            tracker_connection_id=tracker_connection_id,
            direction="inbound",
            remote_ref=remote_ref,
            event_type="issue_updated",
            uniqueness_source=ts,
        )

        event = SyncEvent(
            id=str(uuid4()),
            tracker_connection_id=tracker_connection_id,
            direction="inbound",
            remote_ref=remote_ref,
            local_ref=None,
            event_type="issue_updated",
            fingerprint=fingerprint,
            payload_json=json.dumps(normalized_issue.raw, ensure_ascii=False),
            status="applied",
            error_message=None,
            occurred_at=ts,
            processed_at=ts,
            created_at=ts,
        )
        self.sync_repo.create(event)

        return self.issue_repo.get_by_remote_key(
            tracker_connection_id, normalized_issue.remote_issue_key
        )
