"""Audited and idempotent outbound issue creation."""
from __future__ import annotations

import json
import os
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tracker_bridge.adapters.base import TrackerAdapter
from tracker_bridge.db import transaction
from tracker_bridge.errors import DuplicateError
from tracker_bridge.models import EntityLink, IssueCache, SyncEvent
from tracker_bridge.refs import make_agent_taskstate_task_ref, make_ref, make_tracker_issue_ref
from tracker_bridge.repositories.connection import TrackerConnectionRepository
from tracker_bridge.repositories.entity_link import EntityLinkRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository
from tracker_bridge.services.issue_service import make_fingerprint


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OutboundIssueCreator:
    """Create GitHub issues while retaining tracker-bridge as sync history authority."""

    def __init__(
        self,
        *,
        connection_repo: TrackerConnectionRepository,
        issue_repo: IssueCacheRepository,
        link_repo: EntityLinkRepository,
        sync_repo: SyncEventRepository,
        adapters: dict[str, TrackerAdapter],
    ) -> None:
        self.connection_repo = connection_repo
        self.issue_repo = issue_repo
        self.link_repo = link_repo
        self.sync_repo = sync_repo
        self.adapters = adapters

    def create(
        self,
        *,
        connection_id: str,
        task_id: str,
        handoff_id: str,
        handoff_item_id: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> SyncEvent:
        connection = self.connection_repo.get(connection_id)
        if not connection.is_enabled:
            raise ValueError(f"tracker connection is disabled: {connection_id}")
        if connection.tracker_type != "github":
            raise ValueError("outbound issue creation currently supports github only")
        if not connection.project_key:
            raise ValueError(f"tracker connection project_key is required: {connection_id}")
        if not connection.secret_ref:
            raise ValueError(f"tracker connection secret_ref is required: {connection_id}")
        auth_token = os.environ.get(connection.secret_ref)
        if not auth_token:
            raise ValueError(f"tracker credential environment variable is missing: {connection.secret_ref}")
        adapter = self.adapters.get(connection.tracker_type)
        if adapter is None:
            raise ValueError(f"No adapter registered for: {connection.tracker_type}")

        marker = self._marker(handoff_id, handoff_item_id)
        marked_body = body if marker in body else f"{body.rstrip()}\n\n{marker}".strip()
        local_ref = make_agent_taskstate_task_ref(task_id)
        target_ref = make_ref("tracker", "repository", connection.project_key, provider="github")
        fingerprint = make_fingerprint(
            tracker_connection_id=connection_id,
            direction="outbound",
            remote_ref=target_ref,
            event_type="issue_created",
            uniqueness_source=json.dumps(
                {"handoff_id": handoff_id, "handoff_item_id": handoff_item_id},
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        existing = self.sync_repo.get_by_fingerprint(connection_id, fingerprint)
        if existing is not None and existing.status in {"applied", "skipped"}:
            return replace(existing, status="skipped", processed_at=now_iso())
        if existing is not None and existing.status == "pending":
            reconciled = self._reconcile(
                existing,
                adapter,
                connection.base_url,
                auth_token,
                connection.project_key,
                marker,
                local_ref,
            )
            return reconciled or existing
        if existing is not None and self._outcome_unknown(existing):
            reconciled = self._reconcile(
                existing,
                adapter,
                connection.base_url,
                auth_token,
                connection.project_key,
                marker,
                local_ref,
            )
            return reconciled or existing

        if existing is None:
            event, reservation_owner = self._reserve(
                connection_id=connection_id,
                remote_ref=target_ref,
                local_ref=local_ref,
                fingerprint=fingerprint,
                handoff_id=handoff_id,
                handoff_item_id=handoff_item_id,
                marker=marker,
            )
            if not reservation_owner:
                reconciled = self._reconcile(
                    event,
                    adapter,
                    connection.base_url,
                    auth_token,
                    connection.project_key,
                    marker,
                    local_ref,
                )
                return reconciled or event
        else:
            event = existing
        if existing is not None:
            with transaction(self.sync_repo.conn):
                self.sync_repo.update_result(
                    event.id,
                    status="pending",
                    processed_at=None,
                    error_message=None,
                )

        try:
            found = self._find_by_marker(
                adapter,
                connection.base_url,
                auth_token,
                connection.project_key,
                marker,
            )
        except Exception as exc:
            return self._fail(event, exc, outcome_unknown=False)
        if found is not None:
            return self._apply(event, found, adapter, connection_id, local_ref)

        try:
            raw_issue = adapter.create_issue(
                base_url=connection.base_url,
                auth_token=auth_token,
                project_key=connection.project_key,
                title=title,
                body=marked_body,
                labels=labels,
            )
        except Exception as exc:
            return self._fail(event, exc, outcome_unknown=not self._is_definitive_failure(exc))
        return self._apply(event, raw_issue, adapter, connection_id, local_ref)

    def _reserve(
        self,
        *,
        connection_id: str,
        remote_ref: str,
        local_ref: str,
        fingerprint: str,
        handoff_id: str,
        handoff_item_id: str,
        marker: str,
    ) -> tuple[SyncEvent, bool]:
        ts = now_iso()
        event = SyncEvent(
            id=str(uuid4()),
            tracker_connection_id=connection_id,
            direction="outbound",
            remote_ref=remote_ref,
            local_ref=local_ref,
            event_type="issue_created",
            fingerprint=fingerprint,
            payload_json=json.dumps(
                {
                    "handoff_id": handoff_id,
                    "handoff_item_id": handoff_item_id,
                    "idempotency_marker": marker,
                    "outcome_unknown": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            status="pending",
            error_message=None,
            occurred_at=ts,
            processed_at=None,
            created_at=ts,
        )
        try:
            with transaction(self.sync_repo.conn):
                self.sync_repo.create(event)
            return event, True
        except DuplicateError:
            existing = self.sync_repo.get_by_fingerprint(connection_id, fingerprint)
            if existing is None:
                raise
            return existing, False

    def _reconcile(
        self,
        event: SyncEvent,
        adapter: TrackerAdapter,
        base_url: str,
        auth_token: str,
        project_key: str,
        marker: str,
        local_ref: str,
    ) -> SyncEvent | None:
        try:
            found = self._find_by_marker(adapter, base_url, auth_token, project_key, marker)
        except Exception:
            return None
        if found is None:
            return None
        return self._apply(event, found, adapter, event.tracker_connection_id, local_ref)

    @staticmethod
    def _find_by_marker(
        adapter: TrackerAdapter,
        base_url: str,
        auth_token: str,
        project_key: str,
        marker: str,
    ) -> dict[str, Any] | None:
        issues = adapter.fetch_issues_by_query(
            base_url=base_url,
            auth_token=auth_token,
            query=f'repo:{project_key} is:issue in:body "{marker}"',
            max_results=10,
        )
        return next((issue for issue in issues if marker in str(issue.get("body", ""))), None)

    def _apply(
        self,
        event: SyncEvent,
        raw_issue: dict[str, Any],
        adapter: TrackerAdapter,
        connection_id: str,
        local_ref: str,
    ) -> SyncEvent:
        normalized = adapter.normalize_issue(raw_issue)
        remote_ref = make_tracker_issue_ref("github", normalized.remote_issue_key)
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
        payload = json.loads(event.payload_json)
        payload.update(
            {
                "outcome_unknown": False,
                "remote_issue_key": normalized.remote_issue_key,
                "remote_ref": remote_ref,
            }
        )
        with transaction(self.sync_repo.conn):
            self.issue_repo.upsert(issue)
            with suppress(DuplicateError):
                self.link_repo.create(
                    EntityLink(
                        id=str(uuid4()),
                        local_ref=local_ref,
                        remote_ref=remote_ref,
                        link_role="primary",
                        created_at=ts,
                        updated_at=ts,
                        metadata_json=json.dumps(
                            {"tracker_connection_id": connection_id},
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    )
                )
            self.sync_repo.update_result(
                event.id,
                status="applied",
                processed_at=ts,
                remote_ref=remote_ref,
                payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                error_message=None,
            )
        result = self.sync_repo.get_by_fingerprint(connection_id, event.fingerprint or "")
        if result is None:
            raise RuntimeError("applied sync event could not be reloaded")
        return result

    def _fail(self, event: SyncEvent, exc: Exception, *, outcome_unknown: bool) -> SyncEvent:
        payload = json.loads(event.payload_json)
        payload["outcome_unknown"] = outcome_unknown
        error = self._safe_error(exc)
        with transaction(self.sync_repo.conn):
            self.sync_repo.update_result(
                event.id,
                status="failed",
                processed_at=now_iso(),
                payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                error_message=error,
            )
        result = self.sync_repo.get_by_fingerprint(event.tracker_connection_id, event.fingerprint or "")
        if result is None:
            raise RuntimeError("failed sync event could not be reloaded")
        return result

    @staticmethod
    def _outcome_unknown(event: SyncEvent) -> bool:
        try:
            return bool(json.loads(event.payload_json).get("outcome_unknown"))
        except json.JSONDecodeError:
            return True

    @staticmethod
    def _is_definitive_failure(exc: Exception) -> bool:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return isinstance(status_code, int) and 400 <= status_code < 500 and status_code not in {408, 409, 429}

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        suffix = f" (HTTP {status_code})" if isinstance(status_code, int) else ""
        return f"{type(exc).__name__}: external tracker operation failed{suffix}"

    @staticmethod
    def _marker(handoff_id: str, handoff_item_id: str) -> str:
        safe_handoff = handoff_id.replace("--", "-")
        safe_item = handoff_item_id.replace("--", "-")
        return f"<!-- rand-handoff:{safe_handoff}:{safe_item} -->"
