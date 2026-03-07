"""GitHub Issues adapter for issue synchronization."""
from __future__ import annotations

from typing import Any

from tracker_bridge.models import NormalizedIssue


class GitHubAdapter:
    """Adapter for GitHub Issues."""

    def __init__(self, http_client: Any | None = None) -> None:
        """Initialize adapter with optional HTTP client.

        Args:
            http_client: requests.Session or similar HTTP client
        """
        self.http_client = http_client

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        """Build request headers."""
        return {
            "Authorization": f"token {auth_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

    def _parse_issue_key(self, remote_issue_key: str) -> tuple[str, str, int]:
        """Parse GitHub issue key.

        Args:
            remote_issue_key: Issue key in format 'owner/repo#123'

        Returns:
            Tuple of (owner, repo, issue_number)
        """
        if "#" not in remote_issue_key:
            raise ValueError(f"Invalid GitHub issue key: {remote_issue_key}")

        repo_part, number_part = remote_issue_key.rsplit("#", 1)
        if "/" not in repo_part:
            raise ValueError(f"Invalid GitHub issue key: {remote_issue_key}")

        owner, repo = repo_part.split("/", 1)
        return owner, repo, int(number_part)

    def fetch_issue(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
    ) -> dict[str, Any]:
        """Fetch a single issue from GitHub.

        Args:
            base_url: GitHub API base URL (default: 'https://api.github.com')
            auth_token: GitHub PAT
            remote_issue_key: Issue key (e.g., 'owner/repo#123')

        Returns:
            Raw issue data from GitHub API
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError(
                "HTTP client and auth_token required for live fetch. "
                "Use MockGitHubAdapter for testing."
            )

        owner, repo, issue_number = self._parse_issue_key(remote_issue_key)
        api_base = base_url.rstrip("/") or "https://api.github.com"
        url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}"
        headers = self._get_headers(auth_token)

        response = self.http_client.get(url, headers=headers)
        response.raise_for_status()

        return response.json()  # type: ignore[no-any-return]

    def normalize_issue(self, raw_issue: dict[str, Any]) -> NormalizedIssue:
        """Normalize GitHub issue to common format.

        Args:
            raw_issue: Raw issue data from GitHub API

        Returns:
            NormalizedIssue with standardized fields
        """
        # Extract labels
        labels_data = raw_issue.get("labels") or []
        labels = [label.get("name", "") for label in labels_data if isinstance(label, dict)]

        # Extract assignee (GitHub uses single assignee in basic API)
        assignee_data = raw_issue.get("assignee") or {}
        assignee = assignee_data.get("login") if assignee_data else None

        # Extract user (reporter)
        user_data = raw_issue.get("user") or {}
        reporter = user_data.get("login")

        # GitHub issue state
        state = raw_issue.get("state")

        # Build remote_issue_key
        html_url = raw_issue.get("html_url", "")
        # Extract owner/repo#number from URL or construct from data
        if "issues" in html_url:
            parts = html_url.split("/")
            if len(parts) >= 5:
                owner_repo = f"{parts[3]}/{parts[4]}"
                issue_number = raw_issue.get("number", "")
                remote_key = f"{owner_repo}#{issue_number}"
            else:
                remote_key = str(raw_issue.get("id", ""))
        else:
            remote_key = str(raw_issue.get("id", ""))

        return NormalizedIssue(
            remote_issue_id=str(raw_issue.get("id", "")),
            remote_issue_key=remote_key,
            title=str(raw_issue.get("title", "")),
            status=state,
            assignee=assignee,
            reporter=reporter,
            labels=labels,
            issue_type="Issue",  # GitHub doesn't have issue types by default
            priority=None,  # GitHub doesn't have priority by default
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
        """Fetch issues matching search query.

        Args:
            base_url: GitHub API base URL
            auth_token: GitHub PAT
            query: Search query
            max_results: Maximum results

        Returns:
            List of raw issue data
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError("HTTP client required for live fetch.")

        api_base = base_url.rstrip("/") or "https://api.github.com"
        url = f"{api_base}/search/issues"
        headers = self._get_headers(auth_token)

        params = {"q": query, "per_page": max_results}

        response = self.http_client.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        return data.get("items", [])  # type: ignore[no-any-return]

    def post_comment(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        comment: str,
    ) -> dict[str, Any]:
        """Post a comment to a GitHub issue.

        Args:
            base_url: GitHub API base URL
            auth_token: GitHub PAT
            remote_issue_key: Issue key
            comment: Comment text

        Returns:
            API response data
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError("HTTP client required for live operations.")

        owner, repo, issue_number = self._parse_issue_key(remote_issue_key)
        api_base = base_url.rstrip("/") or "https://api.github.com"
        url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        headers = self._get_headers(auth_token)

        body = {"body": comment}

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
        """Update issue state (open/closed).

        Args:
            base_url: GitHub API base URL
            auth_token: GitHub PAT
            remote_issue_key: Issue key
            status: 'open' or 'closed'

        Returns:
            API response data
        """
        if not self.http_client or not auth_token:
            raise NotImplementedError("HTTP client required for live operations.")

        if status.lower() not in ("open", "closed"):
            raise ValueError(f"GitHub status must be 'open' or 'closed', got: {status}")

        owner, repo, issue_number = self._parse_issue_key(remote_issue_key)
        api_base = base_url.rstrip("/") or "https://api.github.com"
        url = f"{api_base}/repos/{owner}/{repo}/issues/{issue_number}"
        headers = self._get_headers(auth_token)

        body = {"state": status.lower()}

        response = self.http_client.patch(url, headers=headers, json=body)
        response.raise_for_status()

        return response.json()  # type: ignore[no-any-return]


class MockGitHubAdapter:
    """Mock GitHub adapter for testing."""

    def __init__(self, issues: dict[str, dict[str, Any]] | None = None) -> None:
        """Initialize with mock data."""
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
        return GitHubAdapter().normalize_issue(raw_issue)

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
        return {"id": 1, "body": comment}

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
        return {"state": status}

    def add_issue(self, key: str, data: dict[str, Any]) -> None:
        """Add a mock issue."""
        self.issues[key] = data
