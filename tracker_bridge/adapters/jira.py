"""Jira adapter for issue synchronization."""
from __future__ import annotations

from typing import Any

from tracker_bridge.models import NormalizedIssue


class JiraAdapter:
    """Adapter for Atlassian Jira."""

    def __init__(self, http_client: Any | None = None) -> None:
        """Initialize adapter with optional HTTP client.

        Args:
            http_client: requests.Session or similar HTTP client
        """
        self.http_client = http_client

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        """Build request headers.

        Args:
            auth_token: Bearer token or Basic auth string

        Returns:
            Headers dict
        """
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _build_issue_url(self, base_url: str, issue_key: str) -> str:
        """Build API URL for issue.

        Args:
            base_url: Jira base URL (e.g., 'https://example.atlassian.net')
            issue_key: Issue key (e.g., 'PROJ-123')

        Returns:
            Full API URL
        """
        base = base_url.rstrip("/")
        return f"{base}/rest/api/3/issue/{issue_key}"

    def fetch_issue(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
    ) -> dict[str, Any]:
        """Fetch a single issue from Jira.

        Args:
            base_url: Jira base URL
            auth_token: API token or PAT
            remote_issue_key: Issue key (e.g., 'PROJ-123')

        Returns:
            Raw issue data from Jira API
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError(
                "HTTP client and auth_token required for live fetch. "
                "Use MockJiraAdapter for testing."
            )

        url = self._build_issue_url(base_url, remote_issue_key)
        headers = self._get_headers(auth_token)

        response = self.http_client.get(url, headers=headers)
        response.raise_for_status()

        return response.json()  # type: ignore[no-any-return]

    def normalize_issue(self, raw_issue: dict[str, Any]) -> NormalizedIssue:
        """Normalize Jira issue to common format.

        Args:
            raw_issue: Raw issue data from Jira API

        Returns:
            NormalizedIssue with standardized fields
        """
        fields = raw_issue.get("fields", {})

        # Extract assignee
        assignee_data = fields.get("assignee") or {}
        assignee = assignee_data.get("displayName") or assignee_data.get("name")

        # Extract reporter
        reporter_data = fields.get("reporter") or {}
        reporter = reporter_data.get("displayName") or reporter_data.get("name")

        # Extract labels
        labels = fields.get("labels") or []

        # Extract status
        status_data = fields.get("status") or {}
        status = status_data.get("name")

        # Extract issue type
        issue_type_data = fields.get("issuetype") or {}
        issue_type = issue_type_data.get("name")

        # Extract priority
        priority_data = fields.get("priority") or {}
        priority = priority_data.get("name")

        return NormalizedIssue(
            remote_issue_id=str(raw_issue.get("id", "")),
            remote_issue_key=str(raw_issue.get("key", "")),
            title=str(fields.get("summary", "")),
            status=status,
            assignee=assignee,
            reporter=reporter,
            labels=[str(x) for x in labels] if labels else [],
            issue_type=issue_type,
            priority=priority,
            raw=raw_issue,
        )

    def fetch_issues_by_query(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        query: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch issues matching JQL query.

        Args:
            base_url: Jira base URL
            auth_token: API token
            query: JQL query string
            max_results: Maximum results to return

        Returns:
            List of raw issue data
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError(
                "HTTP client and auth_token required for live fetch."
            )

        base = base_url.rstrip("/")
        url = f"{base}/rest/api/3/search"
        headers = self._get_headers(auth_token)

        params = {
            "jql": query,
            "maxResults": max_results,
            "fields": "summary,status,assignee,reporter,labels,issuetype,priority",
        }

        response = self.http_client.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        return data.get("issues", [])  # type: ignore[no-any-return]

    def post_comment(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        comment: str,
    ) -> dict[str, Any]:
        """Post a comment to a Jira issue.

        Args:
            base_url: Jira base URL
            auth_token: API token
            remote_issue_key: Issue key
            comment: Comment text

        Returns:
            API response data
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError("HTTP client required for live operations.")

        base = base_url.rstrip("/")
        url = f"{base}/rest/api/3/issue/{remote_issue_key}/comment"
        headers = self._get_headers(auth_token)

        body = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}}

        response = self.http_client.post(url, headers=headers, json=body)
        response.raise_for_status()

        return response.json()  # type: ignore[no-any-return]

    def update_status(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        status: str,
    ) -> dict[str, Any]:
        """Update issue status via transition.

        Args:
            base_url: Jira base URL
            auth_token: API token
            remote_issue_key: Issue key
            status: Target status name

        Returns:
            API response data
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError("HTTP client required for live operations.")

        base = base_url.rstrip("/")

        # First, get available transitions
        transitions_url = f"{base}/rest/api/3/issue/{remote_issue_key}/transitions"
        headers = self._get_headers(auth_token)

        transitions_response = self.http_client.get(transitions_url, headers=headers)
        transitions_response.raise_for_status()

        transitions = transitions_response.json().get("transitions", [])

        # Find matching transition
        transition_id = None
        for t in transitions:
            if t.get("to", {}).get("name", "").lower() == status.lower():
                transition_id = t.get("id")
                break

        if not transition_id:
            raise ValueError(f"No transition found to status: {status}")

        # Execute transition
        body = {"transition": {"id": transition_id}}

        response = self.http_client.post(transitions_url, headers=headers, json=body)
        response.raise_for_status()

        return {"status": "ok", "transition_id": transition_id}

    def create_issue(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        project_key: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> dict[str, Any]:
        """Reject issue creation until Jira support is explicitly implemented."""
        raise NotImplementedError("Jira issue creation is not supported")


class MockJiraAdapter:
    """Mock Jira adapter for testing."""

    def __init__(self, issues: dict[str, dict[str, Any]] | None = None) -> None:
        """Initialize with mock data.

        Args:
            issues: Dict mapping issue keys to issue data
        """
        self.issues = issues or {}
        self.comments: dict[str, list[str]] = {}
        self.status_updates: dict[str, list[str]] = {}

    def fetch_issue(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
    ) -> dict[str, Any]:
        """Fetch mock issue."""
        if remote_issue_key in self.issues:
            return self.issues[remote_issue_key]
        raise ValueError(f"Issue not found: {remote_issue_key}")

    def normalize_issue(self, raw_issue: dict[str, Any]) -> NormalizedIssue:
        """Normalize issue data."""
        return JiraAdapter().normalize_issue(raw_issue)

    def fetch_issues_by_query(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        query: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Return all mock issues."""
        return list(self.issues.values())[:max_results]

    def post_comment(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        comment: str,
    ) -> dict[str, Any]:
        """Store mock comment."""
        if remote_issue_key not in self.comments:
            self.comments[remote_issue_key] = []
        self.comments[remote_issue_key].append(comment)
        return {"id": "mock-comment-id", "body": comment}

    def update_status(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        status: str,
    ) -> dict[str, Any]:
        """Store mock status update."""
        if remote_issue_key not in self.status_updates:
            self.status_updates[remote_issue_key] = []
        self.status_updates[remote_issue_key].append(status)
        return {"status": "ok"}

    def create_issue(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        project_key: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> dict[str, Any]:
        """Reject issue creation to mirror the live Jira adapter."""
        raise NotImplementedError("Jira issue creation is not supported")

    def add_issue(self, key: str, data: dict[str, Any]) -> None:
        """Add a mock issue."""
        self.issues[key] = data
