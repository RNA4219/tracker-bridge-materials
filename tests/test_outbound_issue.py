from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from tracker_bridge.adapters.github import GitHubAdapter, MockGitHubAdapter
from tracker_bridge.db import connect
from tracker_bridge.models import TrackerConnection
from tracker_bridge.repositories.connection import TrackerConnectionRepository
from tracker_bridge.repositories.entity_link import EntityLinkRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository
from tracker_bridge.services.tracker_integration_service import TrackerIntegrationService, now_iso


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    schema_path = Path(__file__).resolve().parents[1] / "docs" / "0001_init_tracker_bridge.sql"
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def make_service(
    conn: sqlite3.Connection,
    adapter: MockGitHubAdapter,
    *,
    secret_ref: str = "TEST_GITHUB_TOKEN",
) -> TrackerIntegrationService:
    ts = now_iso()
    connection_repo = TrackerConnectionRepository(conn)
    connection_repo.create(
        TrackerConnection(
            id="github-main",
            tracker_type="github",
            name="GitHub",
            base_url="https://api.github.com",
            workspace_key=None,
            project_key="owner/repo",
            secret_ref=secret_ref,
            is_enabled=True,
            created_at=ts,
            updated_at=ts,
        )
    )
    conn.commit()
    service = TrackerIntegrationService(
        connection_repo=connection_repo,
        issue_repo=IssueCacheRepository(conn),
        link_repo=EntityLinkRepository(conn),
        sync_repo=SyncEventRepository(conn),
    )
    service.register_adapter("github", adapter)
    return service


def create_issue(service: TrackerIntegrationService):  # type: ignore[no-untyped-def]
    return service.create_outbound_issue(
        connection_id="github-main",
        task_id="task-123",
        handoff_id="rand:downstream-run-1",
        handoff_item_id="rand:handoff-item:local:req-1",
        title="Requirement 1",
        body="Implement requirement 1",
        labels=["rand", "requirements"],
    )


def test_create_outbound_issue_is_idempotent_and_audited(
    conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "secret-token")
    adapter = MockGitHubAdapter()
    service = make_service(conn, adapter)

    first = create_issue(service)
    second = create_issue(service)

    assert first.id == second.id
    assert first.status == "applied"
    assert second.status == "skipped"
    assert first.remote_ref == "tracker:issue:github:owner/repo#1"
    assert first.local_ref == "agent-taskstate:task:local:task-123"
    assert len(adapter.created_issues) == 1
    assert "<!-- rand-handoff:" in adapter.created_issues[0]["body"]
    assert len(IssueCacheRepository(conn).list_by_connection("github-main")) == 1
    links = EntityLinkRepository(conn).list_by_local_ref(first.local_ref or "")
    assert len(links) == 1
    assert links[0].remote_ref == first.remote_ref


def test_missing_secret_fails_before_reservation(
    conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_GITHUB_TOKEN", raising=False)
    service = make_service(conn, MockGitHubAdapter())

    with pytest.raises(ValueError, match="credential environment variable is missing"):
        create_issue(service)

    assert SyncEventRepository(conn).list() == []


class TimeoutGitHubAdapter(MockGitHubAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.create_calls = 0

    def create_issue(self, **kwargs: Any) -> dict[str, Any]:
        self.create_calls += 1
        raise TimeoutError("response lost")


def test_unknown_outcome_is_not_automatically_created_again(
    conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "secret-token")
    adapter = TimeoutGitHubAdapter()
    service = make_service(conn, adapter)

    first = create_issue(service)
    second = create_issue(service)

    assert first.status == "failed"
    assert second.id == first.id
    assert adapter.create_calls == 1
    assert json.loads(first.payload_json)["outcome_unknown"] is True
    assert "secret-token" not in (first.error_message or "")


def test_pending_marker_is_reconciled_without_duplicate_create(
    conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "secret-token")
    adapter = TimeoutGitHubAdapter()
    service = make_service(conn, adapter)
    failed = create_issue(service)
    marker = json.loads(failed.payload_json)["idempotency_marker"]
    adapter.issues["owner/repo#77"] = {
        "id": 77,
        "number": 77,
        "title": "Requirement 1",
        "body": marker,
        "labels": [{"name": "rand"}],
        "state": "open",
        "html_url": "https://github.com/owner/repo/issues/77",
    }

    reconciled = create_issue(service)

    assert reconciled.status == "applied"
    assert reconciled.remote_ref == "tracker:issue:github:owner/repo#77"
    assert adapter.create_calls == 1


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        return FakeResponse({"id": 1, "number": 1})


class SlowGitHubAdapter(MockGitHubAdapter):
    def __init__(self) -> None:
        super().__init__()
        self._create_lock = threading.Lock()
        self.create_calls = 0

    def create_issue(self, **kwargs: Any) -> dict[str, Any]:
        with self._create_lock:
            self.create_calls += 1
        time.sleep(0.05)
        return super().create_issue(**kwargs)


def test_concurrent_same_fingerprint_creates_only_one_issue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "secret-token")
    db_path = tmp_path / "tracker.db"
    setup = connect(db_path)
    schema_path = Path(__file__).resolve().parents[1] / "docs" / "0001_init_tracker_bridge.sql"
    setup.executescript(schema_path.read_text(encoding="utf-8"))
    ts = now_iso()
    TrackerConnectionRepository(setup).create(
        TrackerConnection(
            id="github-main",
            tracker_type="github",
            name="GitHub",
            base_url="https://api.github.com",
            workspace_key=None,
            project_key="owner/repo",
            secret_ref="TEST_GITHUB_TOKEN",
            is_enabled=True,
            created_at=ts,
            updated_at=ts,
        )
    )
    setup.commit()
    setup.close()

    adapter = SlowGitHubAdapter()
    start = threading.Barrier(2)

    def worker() -> str:
        connection = connect(db_path)
        try:
            service = TrackerIntegrationService(
                connection_repo=TrackerConnectionRepository(connection),
                issue_repo=IssueCacheRepository(connection),
                link_repo=EntityLinkRepository(connection),
                sync_repo=SyncEventRepository(connection),
            )
            service.register_adapter("github", adapter)
            start.wait(timeout=5)
            return str(create_issue(service).status)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _index: worker(), range(2)))

    verify = connect(db_path)
    try:
        service = TrackerIntegrationService(
            connection_repo=TrackerConnectionRepository(verify),
            issue_repo=IssueCacheRepository(verify),
            link_repo=EntityLinkRepository(verify),
            sync_repo=SyncEventRepository(verify),
        )
        service.register_adapter("github", adapter)
        replay = create_issue(service)
        assert adapter.create_calls == 1
        assert len(adapter.created_issues) == 1
        assert len(SyncEventRepository(verify).list()) == 1
        assert len(IssueCacheRepository(verify).list_by_connection("github-main")) == 1
        assert "applied" in statuses
        assert replay.status == "skipped"
    finally:
        verify.close()


def test_secret_is_never_persisted(
    conn: sqlite3.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_GITHUB_TOKEN", "secret-token")
    service = make_service(conn, MockGitHubAdapter())
    create_issue(service)
    dump = " ".join(conn.iterdump())
    assert "secret-token" not in dump

def test_github_create_issue_posts_expected_payload() -> None:
    client = FakeClient()
    adapter = GitHubAdapter(http_client=client)

    result = adapter.create_issue(
        base_url="https://api.github.com",
        auth_token="token",
        project_key="owner/repo",
        title="Title",
        body="Body",
        labels=["rand"],
    )

    assert result["number"] == 1
    assert client.calls == [
        (
            "https://api.github.com/repos/owner/repo/issues",
            {
                "headers": adapter._get_headers("token"),
                "json": {"title": "Title", "body": "Body", "labels": ["rand"]},
            },
        )
    ]
