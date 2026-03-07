"""Base adapter interface for external trackers."""
from __future__ import annotations

from typing import Any, Protocol

from tracker_bridge.models import NormalizedIssue


class TrackerAdapter(Protocol):
    """Protocol for tracker adapters.

    Adapters handle communication with external tracker systems
    and normalization of issue data.
    """

    def fetch_issue(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
    ) -> dict[str, Any]:
        """Fetch a single issue from the tracker.

        Args:
            base_url: Base URL for the tracker API
            auth_token: Authentication token/credentials
            remote_issue_key: Issue key to fetch (e.g., 'PROJ-123')

        Returns:
            Raw issue data from the tracker API
        """
        ...

    def normalize_issue(self, raw_issue: dict[str, Any]) -> NormalizedIssue:
        """Normalize raw issue data to common format.

        Args:
            raw_issue: Raw issue data from the tracker API

        Returns:
            NormalizedIssue with standardized fields
        """
        ...

    def fetch_issues_by_query(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        query: str,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch multiple issues matching a query.

        Args:
            base_url: Base URL for the tracker API
            auth_token: Authentication token/credentials
            query: Query string (JQL for Jira, search query for GitHub)
            max_results: Maximum number of results

        Returns:
            List of raw issue data
        """
        ...

    def post_comment(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        comment: str,
    ) -> dict[str, Any]:
        """Post a comment to an issue.

        Args:
            base_url: Base URL for the tracker API
            auth_token: Authentication token/credentials
            remote_issue_key: Issue key
            comment: Comment text

        Returns:
            Response data from the API
        """
        ...

    def update_status(
        self,
        *,
        base_url: str,
        auth_token: str | None,
        remote_issue_key: str,
        status: str,
    ) -> dict[str, Any]:
        """Update issue status.

        Args:
            base_url: Base URL for the tracker API
            auth_token: Authentication token/credentials
            remote_issue_key: Issue key
            status: New status value

        Returns:
            Response data from the API
        """
        ...
