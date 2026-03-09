"""Integration service for tracker-bridge minimum integration."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tracker_bridge.adapters.base import TrackerAdapter
from tracker_bridge.adapters.github import MockGitHubAdapter
from tracker_bridge.adapters.jira import MockJiraAdapter
from tracker_bridge.errors import DuplicateError
from tracker_bridge.models import EntityLink, IssueCache, SyncEvent
from tracker_bridge.refs import make_agent_taskstate_task_ref, make_tracker_issue_ref
from tracker_bridge.repositories.entity_link import EntityLinkRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository
from tracker_bridge.services.issue_service import make_fingerprint, make_issue_uniqueness_source
from tracker_bridge.services.state_transition_service import StateTransitionService


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrackerIntegrationService:
    """Service for integrating external trackers with internal systems."""

    def __init__(
        self,
        *,
        issue_repo: IssueCacheRepository,
        link_repo: EntityLinkRepository,
        sync_repo: SyncEventRepository,
        transition_service: StateTransitionService | None = None,
    ) -> None:
        self.issue_repo = issue_repo
        self.link_repo = link_repo
        self.sync_repo = sync_repo
        self.transition_service = transition_service
        self._adapters: dict[str, TrackerAdapter] = {}

    def register_adapter(self, tracker_type: str, adapter: TrackerAdapter) -> None:
        self._adapters[tracker_type] = adapter

    def get_adapter(self, tracker_type: str) -> TrackerAdapter | None:
        return self._adapters.get(tracker_type)

    def import_issue(
        self,
        *,
        connection_id: str,
        tracker_type: str,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
    ) -> IssueCache:
        adapter = self.get_adapter(tracker_type)
        if not adapter:
            raise ValueError(f"No adapter registered for: {tracker_type}")

        raw_issue = adapter.fetch_issue(
            base_url=base_url,
            auth_token=auth_token,
            remote_issue_key=remote_issue_key,
        )
        normalized = adapter.normalize_issue(raw_issue)

        ts = now_iso()
        issue = IssueCache(
            id=str(uuid4()),
            tracker_connection_id=connection_id,
            remote_issue_id=normalized.remote_issue_id,
            remote_issue_key=normalized.remote_issue_key,
            title=normalized.title,
            status=normalized.status,
            assignee=normalized.assignee,
            reporter=normalized.reporter,
            labels_json=json.dumps(normalized.labels, ensure_ascii=False),
            issue_type=normalized.issue_type,
            priority=normalized.priority,
            raw_json=json.dumps(normalized.raw, ensure_ascii=False),
            last_seen_at=ts,
            created_at=ts,
            updated_at=ts,
        )
        self.issue_repo.upsert(issue)

        remote_ref = make_tracker_issue_ref(tracker_type, normalized.remote_issue_key)
        fingerprint = make_fingerprint(
            tracker_connection_id=connection_id,
            direction="inbound",
            remote_ref=remote_ref,
            event_type="issue_imported",
            uniqueness_source=make_issue_uniqueness_source(normalized),
        )
        self._record_sync_event(
            connection_id=connection_id,
            direction="inbound",
            remote_ref=remote_ref,
            event_type="issue_imported",
            payload={"issue_key": normalized.remote_issue_key, "title": normalized.title},
            fingerprint=fingerprint,
        )

        if self.transition_service:
            self.transition_service.record_transition(
                entity_type="issue_cache",
                entity_id=issue.id,
                from_status=None,
                to_status="imported",
                reason="issue_import",
            )

        resolved_issue = self.issue_repo.find_by_remote_ref(
            remote_ref,
            tracker_connection_id=connection_id,
        )
        return resolved_issue or issue

    def create_link(
        self,
        *,
        tracker_type: str,
        remote_issue_key: str,
        task_id: str,
        connection_id: str | None = None,
        link_role: str = "primary",
    ) -> EntityLink:
        remote_ref = make_tracker_issue_ref(tracker_type, remote_issue_key)
        local_ref = make_agent_taskstate_task_ref(task_id)
        if connection_id is None:
            issue = self.issue_repo.find_by_remote_ref(remote_ref)
            if issue is not None:
                connection_id = issue.tracker_connection_id

        ts = now_iso()
        link = EntityLink(
            id=str(uuid4()),
            local_ref=local_ref,
            remote_ref=remote_ref,
            link_role=link_role,
            created_at=ts,
            updated_at=ts,
            metadata_json=self._make_link_metadata_json(connection_id),
        )
        self.link_repo.create(link)
        return link

    def get_linked_issues(self, task_id: str) -> list[tuple[EntityLink, IssueCache | None]]:
        local_ref = make_agent_taskstate_task_ref(task_id)
        results: list[tuple[EntityLink, IssueCache | None]] = []

        for link in self.link_repo.list_by_local_ref(local_ref):
            try:
                issue = self.issue_repo.find_by_remote_ref(
                    link.remote_ref,
                    tracker_connection_id=self._get_link_connection_id(link),
                )
            except ValueError:
                issue = None
            results.append((link, issue))

        return results

    def suggest_status_update(
        self,
        *,
        connection_id: str,
        tracker_type: str,
        remote_issue_key: str,
        current_task_status: str,
    ) -> dict[str, Any] | None:
        _ = connection_id, remote_issue_key

        status_map = {
            "done": {"jira": "Done", "github": "closed"},
            "review": {"jira": "In Review", "github": "open"},
            "blocked": {"jira": "Blocked", "github": "open"},
        }

        if current_task_status not in status_map:
            return None

        suggested_status = status_map[current_task_status].get(tracker_type)
        if not suggested_status:
            return None

        return {
            "suggestion_type": "status_update",
            "tracker_type": tracker_type,
            "issue_key": remote_issue_key,
            "current_status": current_task_status,
            "suggested_status": suggested_status,
            "requires_confirmation": True,
        }

    def post_outbound_comment(
        self,
        *,
        connection_id: str,
        tracker_type: str,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        comment: str,
        task_id: str | None = None,
    ) -> SyncEvent:
        remote_ref = make_tracker_issue_ref(tracker_type, remote_issue_key)
        local_ref = make_agent_taskstate_task_ref(task_id) if task_id else None
        uniqueness_source = json.dumps(
            {"comment": comment, "local_ref": local_ref},
            ensure_ascii=False,
            sort_keys=True,
        )
        fingerprint = make_fingerprint(
            tracker_connection_id=connection_id,
            direction="outbound",
            remote_ref=remote_ref,
            event_type="comment_posted",
            uniqueness_source=uniqueness_source,
        )
        existing = self.sync_repo.get_by_fingerprint(connection_id, fingerprint)
        if existing is not None:
            return existing

        adapter = self.get_adapter(tracker_type)
        if not adapter:
            raise ValueError(f"No adapter registered for: {tracker_type}")

        adapter.post_comment(
            base_url=base_url,
            auth_token=auth_token,
            remote_issue_key=remote_issue_key,
            comment=comment,
        )

        return self._record_sync_event(
            connection_id=connection_id,
            direction="outbound",
            remote_ref=remote_ref,
            local_ref=local_ref,
            event_type="comment_posted",
            payload={"comment_preview": comment[:100]},
            fingerprint=fingerprint,
        )

    def export_issue_snapshot(
        self,
        *,
        tracker_type: str,
        remote_issue_key: str,
        connection_id: str | None = None,
    ) -> dict[str, Any] | None:
        remote_ref = make_tracker_issue_ref(tracker_type, remote_issue_key)
        try:
            issue = self.issue_repo.find_by_remote_ref(
                remote_ref,
                tracker_connection_id=connection_id,
            )
        except ValueError:
            return None
        if issue is None:
            return None

        latest_event = self.sync_repo.get_latest_by_remote_ref(
            remote_ref,
            tracker_connection_id=issue.tracker_connection_id,
        )
        return {
            "source": "tracker",
            "tracker_type": tracker_type,
            "tracker_connection_id": issue.tracker_connection_id,
            "issue_key": issue.remote_issue_key,
            "title": issue.title,
            "status": issue.status,
            "assignee": issue.assignee,
            "updated_at": issue.updated_at,
            "remote_ref": remote_ref,
            "last_sync_result": latest_event.status if latest_event else None,
            "last_sync_direction": latest_event.direction if latest_event else None,
            "last_synced_at": (
                (latest_event.processed_at or latest_event.occurred_at) if latest_event else None
            ),
        }

    def _record_sync_event(
        self,
        *,
        connection_id: str,
        direction: str,
        remote_ref: str,
        event_type: str,
        payload: dict[str, Any],
        local_ref: str | None = None,
        fingerprint: str | None = None,
    ) -> SyncEvent:
        ts = now_iso()
        event = SyncEvent(
            id=str(uuid4()),
            tracker_connection_id=connection_id,
            direction=direction,
            remote_ref=remote_ref,
            local_ref=local_ref,
            event_type=event_type,
            fingerprint=fingerprint,
            payload_json=json.dumps(payload, ensure_ascii=False),
            status="applied",
            error_message=None,
            occurred_at=ts,
            processed_at=ts,
            created_at=ts,
        )
        try:
            self.sync_repo.create(event)
            return event
        except DuplicateError:
            if fingerprint is None:
                raise
            existing = self.sync_repo.get_by_fingerprint(connection_id, fingerprint)
            if existing is None:
                raise
            return existing

    @staticmethod
    def _make_link_metadata_json(tracker_connection_id: str | None) -> str | None:
        if tracker_connection_id is None:
            return None
        return json.dumps(
            {"tracker_connection_id": tracker_connection_id},
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _get_link_connection_id(link: EntityLink) -> str | None:
        if not link.metadata_json:
            return None
        try:
            metadata = json.loads(link.metadata_json)
        except json.JSONDecodeError:
            return None
        connection_id = metadata.get("tracker_connection_id")
        return connection_id if isinstance(connection_id, str) else None


class MockTrackerIntegrationService(TrackerIntegrationService):
    """Mock integration service for testing."""

    def __init__(self) -> None:
        super().__init__(
            issue_repo=None,  # type: ignore[arg-type]
            link_repo=None,  # type: ignore[arg-type]
            sync_repo=None,  # type: ignore[arg-type]
        )
        self.register_adapter("jira", MockJiraAdapter())
        self.register_adapter("github", MockGitHubAdapter())
