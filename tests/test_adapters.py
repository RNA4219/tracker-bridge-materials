"""Tests for tracker adapters."""
from __future__ import annotations

import pytest

from tracker_bridge.adapters import (
    GitHubAdapter,
    JiraAdapter,
    MockGitHubAdapter,
    MockJiraAdapter,
)


class TestJiraAdapter:
    def test_normalize_issue(self) -> None:
        adapter = JiraAdapter()
        raw = {
            "id": "12345",
            "key": "PROJ-123",
            "fields": {
                "summary": "Test Issue",
                "status": {"name": "In Progress"},
                "assignee": {"displayName": "John Doe"},
                "reporter": {"displayName": "Jane Smith"},
                "labels": ["bug", "frontend"],
                "issuetype": {"name": "Bug"},
                "priority": {"name": "High"},
            },
        }

        result = adapter.normalize_issue(raw)

        assert result.remote_issue_id == "12345"
        assert result.remote_issue_key == "PROJ-123"
        assert result.title == "Test Issue"
        assert result.status == "In Progress"
        assert result.assignee == "John Doe"
        assert result.reporter == "Jane Smith"
        assert result.labels == ["bug", "frontend"]
        assert result.issue_type == "Bug"
        assert result.priority == "High"

    def test_normalize_issue_with_missing_fields(self) -> None:
        adapter = JiraAdapter()
        raw = {"id": "123", "key": "PROJ-456", "fields": {}}

        result = adapter.normalize_issue(raw)

        assert result.remote_issue_id == "123"
        assert result.remote_issue_key == "PROJ-456"
        assert result.title == ""
        assert result.status is None
        assert result.assignee is None


class TestMockJiraAdapter:
    def test_fetch_issue(self) -> None:
        adapter = MockJiraAdapter({
            "PROJ-123": {
                "id": "12345",
                "key": "PROJ-123",
                "fields": {"summary": "Test"},
            }
        })

        result = adapter.fetch_issue(
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
        )

        assert result["key"] == "PROJ-123"

    def test_fetch_issue_not_found(self) -> None:
        adapter = MockJiraAdapter()

        with pytest.raises(ValueError, match="Issue not found"):
            adapter.fetch_issue(
                base_url="https://example.atlassian.net",
                auth_token="token",
                remote_issue_key="MISSING",
            )

    def test_post_comment(self) -> None:
        adapter = MockJiraAdapter({"PROJ-123": {"id": "1", "key": "PROJ-123"}})

        adapter.post_comment(
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
            comment="Test comment",
        )

        assert "PROJ-123" in adapter.comments
        assert adapter.comments["PROJ-123"] == ["Test comment"]

    def test_update_status(self) -> None:
        adapter = MockJiraAdapter({"PROJ-123": {"id": "1", "key": "PROJ-123"}})

        adapter.update_status(
            base_url="https://example.atlassian.net",
            auth_token="token",
            remote_issue_key="PROJ-123",
            status="Done",
        )

        assert adapter.status_updates["PROJ-123"] == ["Done"]


class TestGitHubAdapter:
    def test_normalize_issue(self) -> None:
        adapter = GitHubAdapter()
        raw = {
            "id": 12345,
            "number": 42,
            "title": "Test Issue",
            "state": "open",
            "user": {"login": "reporter"},
            "assignee": {"login": "assignee"},
            "labels": [{"name": "bug"}, {"name": "enhancement"}],
            "html_url": "https://github.com/owner/repo/issues/42",
        }

        result = adapter.normalize_issue(raw)

        assert result.remote_issue_id == "12345"
        assert result.remote_issue_key == "owner/repo#42"
        assert result.title == "Test Issue"
        assert result.status == "open"
        assert result.assignee == "assignee"
        assert result.reporter == "reporter"
        assert "bug" in result.labels
        assert result.issue_type == "Issue"

    def test_parse_issue_key(self) -> None:
        adapter = GitHubAdapter()

        owner, repo, number = adapter._parse_issue_key("owner/repo#123")
        assert owner == "owner"
        assert repo == "repo"
        assert number == 123

    def test_parse_issue_key_invalid(self) -> None:
        adapter = GitHubAdapter()

        with pytest.raises(ValueError):
            adapter._parse_issue_key("invalid")


class TestMockGitHubAdapter:
    def test_fetch_issue(self) -> None:
        adapter = MockGitHubAdapter({
            "owner/repo#123": {
                "id": 12345,
                "number": 123,
                "title": "Test",
                "state": "open",
            }
        })

        result = adapter.fetch_issue(
            base_url="https://api.github.com",
            auth_token="token",
            remote_issue_key="owner/repo#123",
        )

        assert result["number"] == 123

    def test_update_status(self) -> None:
        adapter = MockGitHubAdapter({"owner/repo#123": {"id": 1}})

        adapter.update_status(
            base_url="https://api.github.com",
            auth_token="token",
            remote_issue_key="owner/repo#123",
            status="closed",
        )

        assert adapter.status_updates["owner/repo#123"] == ["closed"]
