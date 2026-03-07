from __future__ import annotations

from typing import Any, Protocol

from tracker_bridge.models import NormalizedIssue


class TrackerAdapter(Protocol):
    def fetch_issue(self, *, base_url: str, secret_ref: str | None, remote_issue_key: str) -> dict[str, Any]:
        ...

    def normalize_issue(self, raw_issue: dict[str, Any]) -> NormalizedIssue:
        ...
