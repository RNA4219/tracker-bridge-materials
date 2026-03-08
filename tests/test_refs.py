"""Tests for refs module."""
from __future__ import annotations

import pytest

from tracker_bridge.refs import (
    TypedRef,
    canonicalize,
    is_memx_ref,
    is_tracker_ref,
    is_agent_taskstate_ref,
    make_memx_artifact_ref,
    make_memx_evidence_ref,
    make_memx_knowledge_ref,
    make_ref,
    make_tracker_issue_ref,
    make_agent_taskstate_task_ref,
    validate_typed_ref,
)


class TestTypedRef:
    def test_parse_3_segment_memx(self) -> None:
        ref = TypedRef.parse("memx:evidence:01JXYZ")
        assert ref.domain == "memx"
        assert ref.entity_type == "evidence"
        assert ref.entity_id == "01JXYZ"
        assert ref.provider is None
        assert ref.is_memx is True

    def test_parse_3_segment_agent_taskstate(self) -> None:
        ref = TypedRef.parse("agent-taskstate:task:abc123")
        assert ref.domain == "agent-taskstate"
        assert ref.entity_type == "task"
        assert ref.entity_id == "abc123"
        assert ref.provider is None
        assert ref.is_agent_taskstate is True

    def test_parse_4_segment_tracker(self) -> None:
        ref = TypedRef.parse("tracker:issue:jira:PROJ-123")
        assert ref.domain == "tracker"
        assert ref.entity_type == "issue"
        assert ref.provider == "jira"
        assert ref.entity_id == "PROJ-123"
        assert ref.is_tracker is True

    def test_parse_4_segment_tracker_github(self) -> None:
        ref = TypedRef.parse("tracker:issue:github:owner/repo#45")
        assert ref.domain == "tracker"
        assert ref.provider == "github"
        assert ref.entity_id == "owner/repo#45"

    def test_parse_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid typed_ref format"):
            TypedRef.parse("invalid")

    def test_parse_empty_segment(self) -> None:
        with pytest.raises(ValueError, match="empty segment"):
            TypedRef.parse("memx::01H")

    def test_str_3_segment(self) -> None:
        ref = TypedRef(domain="memx", entity_type="evidence", entity_id="01H")
        assert str(ref) == "memx:evidence:01H"

    def test_str_4_segment(self) -> None:
        ref = TypedRef(domain="tracker", entity_type="issue", provider="jira", entity_id="PROJ-123")
        assert str(ref) == "tracker:issue:jira:PROJ-123"


class TestMakeRef:
    def test_make_memx_ref(self) -> None:
        ref = make_ref("memx", "evidence", "01JABC")
        assert ref == "memx:evidence:01JABC"

    def test_make_agent_taskstate_ref(self) -> None:
        ref = make_ref("agent-taskstate", "task", "task_123")
        assert ref == "agent-taskstate:task:task_123"

    def test_make_tracker_ref(self) -> None:
        ref = make_ref("tracker", "issue", "PROJ-123", provider="jira")
        assert ref == "tracker:issue:jira:PROJ-123"


class TestMakeTrackerIssueRef:
    def test_jira_ref(self) -> None:
        ref = make_tracker_issue_ref("jira", "PROJ-123")
        assert ref == "tracker:issue:jira:PROJ-123"

    def test_github_ref(self) -> None:
        ref = make_tracker_issue_ref("github", "owner/repo#45")
        assert ref == "tracker:issue:github:owner/repo#45"

    def test_linear_ref(self) -> None:
        ref = make_tracker_issue_ref("linear", "ENG-123")
        assert ref == "tracker:issue:linear:ENG-123"


class TestMakeAgentTaskstateTaskRef:
    def test_task_ref(self) -> None:
        ref = make_agent_taskstate_task_ref("01JABCDEF")
        assert ref == "agent-taskstate:task:01JABCDEF"


class TestMakeMemxRefs:
    def test_evidence_ref(self) -> None:
        ref = make_memx_evidence_ref("01JXYZ")
        assert ref == "memx:evidence:01JXYZ"

    def test_knowledge_ref(self) -> None:
        ref = make_memx_knowledge_ref("01HABC")
        assert ref == "memx:knowledge:01HABC"

    def test_artifact_ref(self) -> None:
        ref = make_memx_artifact_ref("01HDEF")
        assert ref == "memx:artifact:01HDEF"


class TestValidateTypedRef:
    def test_valid_3_segment_refs(self) -> None:
        assert validate_typed_ref("memx:evidence:01JXYZ") is True
        assert validate_typed_ref("memx:knowledge:01HABC") is True
        assert validate_typed_ref("agent-taskstate:task:abc123") is True

    def test_valid_4_segment_refs(self) -> None:
        assert validate_typed_ref("tracker:issue:jira:PROJ-123") is True
        assert validate_typed_ref("tracker:issue:github:owner/repo#45") is True

    def test_invalid_refs(self) -> None:
        assert validate_typed_ref("invalid") is False
        assert validate_typed_ref("memx:") is False
        assert validate_typed_ref("tracker:jira:") is False
        assert validate_typed_ref(":jira:PROJ-123") is False
        assert validate_typed_ref("") is False

    def test_unknown_domain(self) -> None:
        assert validate_typed_ref("unknown:type:provider:id") is False


class TestCanonicalize:
    def test_canonicalize_3_segment(self) -> None:
        result = canonicalize("memx:evidence:01H")
        assert result == "memx:evidence:01H"

    def test_canonicalize_4_segment(self) -> None:
        result = canonicalize("tracker:issue:jira:PROJ-123")
        assert result == "tracker:issue:jira:PROJ-123"


class TestIsDomainRef:
    def test_is_memx_ref(self) -> None:
        assert is_memx_ref("memx:evidence:01H") is True
        assert is_memx_ref("agent-taskstate:task:01H") is False
        assert is_memx_ref("tracker:issue:jira:PROJ-123") is False

    def test_is_agent_taskstate_ref(self) -> None:
        assert is_agent_taskstate_ref("agent-taskstate:task:01H") is True
        assert is_agent_taskstate_ref("memx:evidence:01H") is False
        assert is_agent_taskstate_ref("tracker:issue:jira:PROJ-123") is False

    def test_is_tracker_ref(self) -> None:
        assert is_tracker_ref("tracker:issue:jira:PROJ-123") is True
        assert is_tracker_ref("memx:evidence:01H") is False
        assert is_tracker_ref("agent-taskstate:task:01H") is False
