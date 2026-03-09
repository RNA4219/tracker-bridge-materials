"""Tests for adapter methods that use HTTP clients."""
from __future__ import annotations

from typing import Any

import pytest

from tracker_bridge.adapters import GitHubAdapter, JiraAdapter


class FakeResponse:
    def __init__(self, payload: Any, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    def json(self) -> Any:
        return self.payload


class FakeHttpClient:
    def __init__(self, responses: dict[tuple[str, str], FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return self.responses[("GET", url)]

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return self.responses[("POST", url)]

    def patch(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("PATCH", url, kwargs))
        return self.responses[("PATCH", url)]


class TestJiraAdapterHttpClient:
    def test_fetch_issue_uses_http_client(self) -> None:
        url = "https://example.atlassian.net/rest/api/3/issue/PROJ-123"
        client = FakeHttpClient({("GET", url): FakeResponse({"key": "PROJ-123"})})
        adapter = JiraAdapter(http_client=client)

        result = adapter.fetch_issue(
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
        )

        assert result["key"] == "PROJ-123"
        assert client.calls[0][0] == "GET"

    def test_fetch_issue_requires_auth(self) -> None:
        adapter = JiraAdapter()
        with pytest.raises(NotImplementedError):
            adapter.fetch_issue(
                base_url="https://example.atlassian.net",
                auth_token=None,
                remote_issue_key="PROJ-123",
            )

    def test_fetch_issues_by_query(self) -> None:
        url = "https://example.atlassian.net/rest/api/3/search"
        client = FakeHttpClient({("GET", url): FakeResponse({"issues": [{"key": "PROJ-123"}]})})
        adapter = JiraAdapter(http_client=client)

        result = adapter.fetch_issues_by_query(
            base_url="https://example.atlassian.net",
            auth_token="token",
            query="project = PROJ",
            max_results=10,
        )

        assert result == [{"key": "PROJ-123"}]
        assert client.calls[0][2]["params"]["jql"] == "project = PROJ"

    def test_post_comment(self) -> None:
        url = "https://example.atlassian.net/rest/api/3/issue/PROJ-123/comment"
        client = FakeHttpClient({("POST", url): FakeResponse({"id": "comment-1"})})
        adapter = JiraAdapter(http_client=client)

        result = adapter.post_comment(
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
            comment="hello",
        )

        assert result["id"] == "comment-1"
        assert client.calls[0][2]["json"]["body"]["type"] == "doc"

    def test_update_status(self) -> None:
        url = "https://example.atlassian.net/rest/api/3/issue/PROJ-123/transitions"
        client = FakeHttpClient(
            {
                ("GET", url): FakeResponse({"transitions": [{"id": "31", "to": {"name": "Done"}}]}),
                ("POST", url): FakeResponse({}),
            }
        )
        adapter = JiraAdapter(http_client=client)

        result = adapter.update_status(
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
            status="Done",
        )

        assert result == {"status": "ok", "transition_id": "31"}

    def test_update_status_raises_when_transition_missing(self) -> None:
        url = "https://example.atlassian.net/rest/api/3/issue/PROJ-123/transitions"
        client = FakeHttpClient({("GET", url): FakeResponse({"transitions": []})})
        adapter = JiraAdapter(http_client=client)

        with pytest.raises(ValueError, match="No transition found"):
            adapter.update_status(
                base_url="https://example.atlassian.net",
                auth_token="token",
                remote_issue_key="PROJ-123",
                status="Done",
            )


class TestGitHubAdapterHttpClient:
    def test_fetch_issue_uses_http_client(self) -> None:
        url = "https://api.github.com/repos/owner/repo/issues/123"
        client = FakeHttpClient({("GET", url): FakeResponse({"number": 123})})
        adapter = GitHubAdapter(http_client=client)

        result = adapter.fetch_issue(
            base_url="https://api.github.com",
            auth_token="token",
            remote_issue_key="owner/repo#123",
        )

        assert result["number"] == 123

    def test_fetch_issue_requires_auth(self) -> None:
        adapter = GitHubAdapter()
        with pytest.raises(NotImplementedError):
            adapter.fetch_issue(
                base_url="https://api.github.com",
                auth_token=None,
                remote_issue_key="owner/repo#123",
            )

    def test_fetch_issues_by_query(self) -> None:
        url = "https://api.github.com/search/issues"
        client = FakeHttpClient({("GET", url): FakeResponse({"items": [{"id": 1}]})})
        adapter = GitHubAdapter(http_client=client)

        result = adapter.fetch_issues_by_query(
            base_url="https://api.github.com",
            auth_token="token",
            query="repo:owner/repo is:issue",
            max_results=5,
        )

        assert result == [{"id": 1}]
        assert client.calls[0][2]["params"]["per_page"] == 5

    def test_post_comment(self) -> None:
        url = "https://api.github.com/repos/owner/repo/issues/123/comments"
        client = FakeHttpClient({("POST", url): FakeResponse({"id": 1})})
        adapter = GitHubAdapter(http_client=client)

        result = adapter.post_comment(
            base_url="https://api.github.com",
            auth_token="token",
            remote_issue_key="owner/repo#123",
            comment="hello",
        )

        assert result["id"] == 1
        assert client.calls[0][2]["json"] == {"body": "hello"}

    def test_update_status(self) -> None:
        url = "https://api.github.com/repos/owner/repo/issues/123"
        client = FakeHttpClient({("PATCH", url): FakeResponse({"state": "closed"})})
        adapter = GitHubAdapter(http_client=client)

        result = adapter.update_status(
            base_url="https://api.github.com",
            auth_token="token",
            remote_issue_key="owner/repo#123",
            status="closed",
        )

        assert result["state"] == "closed"

    def test_update_status_rejects_invalid_status(self) -> None:
        adapter = GitHubAdapter(http_client=FakeHttpClient({}))
        with pytest.raises(ValueError, match="GitHub status must be 'open' or 'closed'"):
            adapter.update_status(
                base_url="https://api.github.com",
                auth_token="token",
                remote_issue_key="owner/repo#123",
                status="done",
            )
