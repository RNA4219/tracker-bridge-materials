"""Integration service for tracker-bridge minimum integration."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tracker_bridge.adapters.base import TrackerAdapter
from tracker_bridge.adapters.github import MockGitHubAdapter
from tracker_bridge.adapters.jira import MockJiraAdapter
from tracker_bridge.models import EntityLink, IssueCache, SyncEvent
from tracker_bridge.refs import TypedRef, make_tracker_issue_ref, make_workx_task_ref
from tracker_bridge.repositories.entity_link import EntityLinkRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository
from tracker_bridge.services.state_transition_service import StateTransitionService


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrackerIntegrationService:
    """Service for integrating external trackers with internal systems.

    This service handles:
    - Issue import and caching
    - Entity linking between tracker issues and workx tasks
    - Sync event tracking
    - Status suggestion (not automatic updates)
    """

    def __init__(
        self,
        *,
        issue_repo: IssueCacheRepository,
        link_repo: EntityLinkRepository,
        sync_repo: SyncEventRepository,
        transition_service: StateTransitionService | None = None,
    ) -> None:
        """Initialize the integration service.

        Args:
            issue_repo: Repository for issue cache
            link_repo: Repository for entity links
            sync_repo: Repository for sync events
            transition_service: Optional service for state transitions
        """
        self.issue_repo = issue_repo
        self.link_repo = link_repo
        self.sync_repo = sync_repo
        self.transition_service = transition_service

        # Adapter registry
        self._adapters: dict[str, TrackerAdapter] = {}

    def register_adapter(self, tracker_type: str, adapter: TrackerAdapter) -> None:
        """Register an adapter for a tracker type.

        Args:
            tracker_type: Tracker type identifier (e.g., 'jira', 'github')
            adapter: Adapter instance
        """
        self._adapters[tracker_type] = adapter

    def get_adapter(self, tracker_type: str) -> TrackerAdapter | None:
        """Get adapter for a tracker type.

        Args:
            tracker_type: Tracker type identifier

        Returns:
            Adapter instance or None
        """
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
        """Import an issue from an external tracker.

        Args:
            connection_id: Tracker connection ID
            tracker_type: Type of tracker (jira, github, etc.)
            base_url: Tracker base URL
            auth_token: Authentication token
            remote_issue_key: Issue key to import

        Returns:
            Cached issue data
        """
        adapter = self.get_adapter(tracker_type)
        if not adapter:
            raise ValueError(f"No adapter registered for: {tracker_type}")

        # Fetch and normalize
        raw_issue = adapter.fetch_issue(
            base_url=base_url,
            auth_token=auth_token,
            remote_issue_key=remote_issue_key,
        )
        normalized = adapter.normalize_issue(raw_issue)

        # Cache the issue
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

        # Record sync event
        remote_ref = make_tracker_issue_ref(tracker_type, normalized.remote_issue_key)
        self._record_sync_event(
            connection_id=connection_id,
            direction="inbound",
            remote_ref=remote_ref,
            event_type="issue_imported",
            payload={"issue_key": normalized.remote_issue_key, "title": normalized.title},
        )

        # Record state transition
        if self.transition_service:
            self.transition_service.record_transition(
                entity_type="issue_cache",
                entity_id=issue.id,
                from_status=None,
                to_status="imported",
                reason="issue_import",
            )

        return issue

    def create_link(
        self,
        *,
        tracker_type: str,
        remote_issue_key: str,
        task_id: str,
        link_role: str = "primary",
    ) -> EntityLink:
        """Create a link between a tracker issue and a workx task.

        Args:
            tracker_type: Type of tracker
            remote_issue_key: Issue key
            task_id: workx task ID
            link_role: Link role (primary, related, duplicate, blocks)

        Returns:
            Created entity link
        """
        remote_ref = make_tracker_issue_ref(tracker_type, remote_issue_key)
        local_ref = make_workx_task_ref(task_id)

        ts = now_iso()
        link = EntityLink(
            id=str(uuid4()),
            local_ref=local_ref,
            remote_ref=remote_ref,
            link_role=link_role,
            created_at=ts,
            updated_at=ts,
        )
        self.link_repo.create(link)

        return link

    def get_linked_issues(self, task_id: str) -> list[tuple[EntityLink, IssueCache | None]]:
        """Get all issues linked to a task.

        Args:
            task_id: workx task ID

        Returns:
            List of (link, issue) tuples
        """
        local_ref = make_workx_task_ref(task_id)
        links = self.link_repo.list_by_local_ref(local_ref)

        results = []
        for link in links:
            # Parse remote_ref to get issue key
            try:
                typed_ref = TypedRef.parse(link.remote_ref)
                issue_key = typed_ref.entity_id
                # Try to find in cache
                issues = self.issue_repo.list_by_connection(
                    link.remote_ref.split(":")[2] if ":" in link.remote_ref else ""
                )
                issue = None
                for i in issues:
                    if i.remote_issue_key == issue_key:
                        issue = i
                        break
                results.append((link, issue))
            except Exception:
                results.append((link, None))

        return results

    def suggest_status_update(
        self,
        *,
        connection_id: str,
        tracker_type: str,
        remote_issue_key: str,
        current_task_status: str,
    ) -> dict[str, Any] | None:
        """Suggest a status update based on task status.

        This does NOT automatically update the tracker.
        It returns a suggestion for operator review.

        Args:
            connection_id: Tracker connection ID
            tracker_type: Type of tracker
            remote_issue_key: Issue key
            current_task_status: Current task status

        Returns:
            Suggestion dict or None
        """
        # Mapping of task status to suggested tracker status
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
        """Post a comment to an external tracker.

        Args:
            connection_id: Tracker connection ID
            tracker_type: Type of tracker
            base_url: Tracker base URL
            auth_token: Authentication token
            remote_issue_key: Issue key
            comment: Comment text
            task_id: Optional related task ID

        Returns:
            Sync event record
        """
        adapter = self.get_adapter(tracker_type)
        if not adapter:
            raise ValueError(f"No adapter registered for: {tracker_type}")

        # Post comment
        adapter.post_comment(
            base_url=base_url,
            auth_token=auth_token,
            remote_issue_key=remote_issue_key,
            comment=comment,
        )

        # Record sync event
        remote_ref = make_tracker_issue_ref(tracker_type, remote_issue_key)
        local_ref = make_workx_task_ref(task_id) if task_id else None

        return self._record_sync_event(
            connection_id=connection_id,
            direction="outbound",
            remote_ref=remote_ref,
            local_ref=local_ref,
            event_type="comment_posted",
            payload={"comment_preview": comment[:100]},
        )

    def export_issue_snapshot(
        self,
        *,
        tracker_type: str,
        remote_issue_key: str,
    ) -> dict[str, Any] | None:
        """Export a minimal issue snapshot for context build.

        Args:
            tracker_type: Type of tracker
            remote_issue_key: Issue key

        Returns:
            Snapshot dict or None if not found
        """
        # Find cached issue
        issues = self.issue_repo.list_by_connection("")  # TODO: proper lookup

        for issue in issues:
            if issue.remote_issue_key == remote_issue_key:
                return {
                    "source": "tracker",
                    "tracker_type": tracker_type,
                    "issue_key": issue.remote_issue_key,
                    "title": issue.title,
                    "status": issue.status,
                    "assignee": issue.assignee,
                    "updated_at": issue.updated_at,
                    "remote_ref": make_tracker_issue_ref(tracker_type, remote_issue_key),
                }

        return None

    def _record_sync_event(
        self,
        *,
        connection_id: str,
        direction: str,
        remote_ref: str,
        event_type: str,
        payload: dict[str, Any],
        local_ref: str | None = None,
    ) -> SyncEvent:
        """Record a sync event."""
        ts = now_iso()
        event = SyncEvent(
            id=str(uuid4()),
            tracker_connection_id=connection_id,
            direction=direction,
            remote_ref=remote_ref,
            local_ref=local_ref,
            event_type=event_type,
            fingerprint=None,
            payload_json=json.dumps(payload, ensure_ascii=False),
            status="applied",
            error_message=None,
            occurred_at=ts,
            processed_at=ts,
            created_at=ts,
        )
        self.sync_repo.create(event)
        return event


class MockTrackerIntegrationService(TrackerIntegrationService):
    """Mock integration service for testing."""

    def __init__(self) -> None:
        """Initialize with mock adapters."""
        # These will be set up with in-memory DB in tests
        super().__init__(
            issue_repo=None,  # type: ignore
            link_repo=None,  # type: ignore
            sync_repo=None,  # type: ignore
        )

        # Register mock adapters
        self.register_adapter("jira", MockJiraAdapter())
        self.register_adapter("github", MockGitHubAdapter())
