"""Tests for refs module."""
from __future__ import annotations

import pytest

from tracker_bridge.refs import (
    make_remote_ref,
    make_local_task_ref,
    validate_typed_ref,
)


class TestMakeRemoteRef:
    def test_jira_ref(self) -> None:
        ref = make_remote_ref("jira", "PROJ-123")
        assert ref == "tracker:jira:PROJ-123"

    def test_github_ref(self) -> None:
        ref = make_remote_ref("github", "repo#45")
        assert ref == "tracker:github:repo#45"


class TestMakeLocalTaskRef:
    def test_task_ref(self) -> None:
        ref = make_local_task_ref("abc123")
        assert ref == "workx:task:abc123"


class TestValidateTypedRef:
    def test_valid_refs(self) -> None:
        assert validate_typed_ref("tracker:jira:PROJ-123") is True
        assert validate_typed_ref("workx:task:abc123") is True
        assert validate_typed_ref("memx:evidence:xyz789") is True
        assert validate_typed_ref("tracker:github:owner/repo#45") is True

    def test_invalid_refs(self) -> None:
        assert validate_typed_ref("invalid") is False
        assert validate_typed_ref("tracker:") is False
        assert validate_typed_ref("tracker:jira:") is False
        assert validate_typed_ref(":jira:PROJ-123") is False
        assert validate_typed_ref("") is False