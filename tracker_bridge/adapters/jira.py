from __future__ import annotations

from typing import Any

from tracker_bridge.models import NormalizedIssue


class JiraAdapter:
    def fetch_issue(
        self,
        *,
        base_url: str,
        secret_ref: str | None,
        remote_issue_key: str,
    ) -> dict[str, Any]:
        # TODO: requests/httpx で実装
        raise NotImplementedError

    def normalize_issue(self, raw_issue: dict[str, Any]) -> NormalizedIssue:
        fields = raw_issue.get("fields", {})
        assignee = fields.get("assignee") or {}
        reporter = fields.get("reporter") or {}
        labels = fields.get("labels") or []
        status = fields.get("status") or {}
        issue_type = fields.get("issuetype") or {}
        priority = fields.get("priority") or {}

        return NormalizedIssue(
            remote_issue_id=str(raw_issue.get("id", "")),
            remote_issue_key=str(raw_issue.get("key", "")),
            title=str(fields.get("summary", "")),
            status=status.get("name"),
            assignee=assignee.get("displayName"),
            reporter=reporter.get("displayName"),
            labels=[str(x) for x in labels],
            issue_type=issue_type.get("name"),
            priority=priority.get("name"),
            raw=raw_issue,
        )
