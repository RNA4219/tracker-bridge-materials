"""Tests for refs module."""
from __future__ import annotations

import pytest

from tracker_bridge.refs import (
    TypedRef,
    canonicalize,
    is_canonical,
    make_memx_evidence_ref,
    make_ref,
    make_tracker_issue_ref,
    make_workx_task_ref,
    validate_typed_ref,
)


class TestTypedRef:
    def test_parse_canonical_format(self) -> None:
        ref = TypedRef.parse("tracker:issue:jira:PROJ-123")
        assert ref.domain == "tracker"
        assert ref.entity_type == "issue"
        assert ref.provider == "jira"
        assert ref.entity_id == "PROJ-123"

    def test_parse_legacy_3_segment(self) -> None:
        ref = TypedRef.parse("workx:task:abc123")
        assert ref.domain == "workx"
        assert ref.entity_type == "task"
        assert ref.provider == "local"  # Default provider
        assert ref.entity_id == "abc123"

    def test_parse_memx_legacy(self) -> None:
        ref = TypedRef.parse("memx:evidence:xyz789")
        assert ref.domain == "memx"
        assert ref.entity_type == "evidence"
        assert ref.provider == "local"
        assert ref.entity_id == "xyz789"

    def test_parse_invalid_format(self) -> None:
        with pytest.raises(ValueError, match="Invalid typed_ref format"):
            TypedRef.parse("invalid")

    def test_parse_empty_segment(self) -> None:
        with pytest.raises(ValueError, match="empty segment"):
            TypedRef.parse("tracker::jira:PROJ-123")

    def test_str_representation(self) -> None:
        ref = TypedRef(domain="tracker", entity_type="issue", provider="jira", entity_id="PROJ-123")
        assert str(ref) == "tracker:issue:jira:PROJ-123"


class TestMakeRef:
    def test_make_ref(self) -> None:
        ref = make_ref("tracker", "issue", "jira", "PROJ-123")
        assert ref == "tracker:issue:jira:PROJ-123"

    def test_make_ref_workx(self) -> None:
        ref = make_ref("workx", "task", "local", "01JABCDEF")
        assert ref == "workx:task:local:01JABCDEF"


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


class TestMakeWorkxTaskRef:
    def test_default_provider(self) -> None:
        ref = make_workx_task_ref("01JABCDEF")
        assert ref == "workx:task:local:01JABCDEF"

    def test_custom_provider(self) -> None:
        ref = make_workx_task_ref("01JABCDEF", provider="external")
        assert ref == "workx:task:external:01JABCDEF"


class TestMakeMemxEvidenceRef:
    def test_default_provider(self) -> None:
        ref = make_memx_evidence_ref("01JXYZ")
        assert ref == "memx:evidence:local:01JXYZ"


class TestValidateTypedRef:
    def test_valid_canonical_refs(self) -> None:
        assert validate_typed_ref("tracker:issue:jira:PROJ-123") is True
        assert validate_typed_ref("workx:task:local:abc123") is True
        assert validate_typed_ref("memx:evidence:local:xyz789") is True
        assert validate_typed_ref("tracker:issue:github:owner/repo#45") is True

    def test_valid_legacy_refs(self) -> None:
        # Legacy 3-segment format is accepted during migration
        assert validate_typed_ref("tracker:jira:PROJ-123") is True
        assert validate_typed_ref("workx:task:abc123") is True
        assert validate_typed_ref("memx:evidence:xyz789") is True

    def test_invalid_refs(self) -> None:
        assert validate_typed_ref("invalid") is False
        assert validate_typed_ref("tracker:") is False
        assert validate_typed_ref("tracker:jira:") is False
        assert validate_typed_ref(":jira:PROJ-123") is False
        assert validate_typed_ref("") is False

    def test_unknown_domain(self) -> None:
        # Unknown domain should fail validation
        assert validate_typed_ref("unknown:type:provider:id") is False


class TestCanonicalize:
    def test_canonicalize_4_segment(self) -> None:
        # Already canonical - no change
        result = canonicalize("tracker:issue:jira:PROJ-123")
        assert result == "tracker:issue:jira:PROJ-123"

    def test_canonicalize_3_segment(self) -> None:
        # Legacy format - add 'local' provider
        result = canonicalize("workx:task:abc123")
        assert result == "workx:task:local:abc123"

    def test_canonicalize_memx(self) -> None:
        result = canonicalize("memx:evidence:xyz789")
        assert result == "memx:evidence:local:xyz789"


class TestIsCanonical:
    def test_is_canonical_true(self) -> None:
        assert is_canonical("tracker:issue:jira:PROJ-123") is True
        assert is_canonical("workx:task:local:abc123") is True

    def test_is_canonical_false(self) -> None:
        # 3-segment is not canonical
        assert is_canonical("workx:task:abc123") is False
        assert is_canonical("tracker:jira:PROJ-123") is False
