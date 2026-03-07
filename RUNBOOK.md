---
intent_id: INT-TB-001
owner: tracker-bridge-team
status: active
last_reviewed_at: 2025-03-08
next_review_due: 2025-04-08
---

# Runbook - tracker-bridge

## Environments

| Environment | DB Path | Secrets |
|-------------|---------|---------|
| Local | `./data/tracker.db` | `.env` file |
| CI | `:memory:` | GitHub Secrets |
| Prod | `$TRACKER_BRIDGE_DB` | Secret Manager |

## Execute

### Setup

```bash
# 1. 仮想環境作成
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 2. 開発依存関係インストール
pip install -e ".[dev]"

# 3. DB初期化
python -c "
from pathlib import Path
from tracker_bridge.db import connect
conn = connect(Path('data/tracker.db'))
with open('docs/0001_init_tracker_bridge.sql') as f:
    conn.executescript(f.read())
conn.close()
"
```

### Run Tests

```bash
# 全テスト実行
pytest

# カバレッジ付き
pytest --cov=tracker_bridge --cov-report=term-missing

# 型チェック
mypy tracker_bridge

# リント
ruff check .
```

### Manual Issue Import

```python
from tracker_bridge.db import connect
from tracker_bridge.repositories.connection import TrackerConnectionRepository
from tracker_bridge.repositories.issue_cache import IssueCacheRepository
from tracker_bridge.repositories.sync_event import SyncEventRepository
from tracker_bridge.services.issue_service import IssueService
from tracker_bridge.models import NormalizedIssue

conn = connect("data/tracker.db")
svc = IssueService(
    connection_repo=TrackerConnectionRepository(conn),
    issue_repo=IssueCacheRepository(conn),
    sync_repo=SyncEventRepository(conn),
)

# 事前に connection を作成しておく
normalized = NormalizedIssue(
    remote_issue_id="12345",
    remote_issue_key="PROJ-123",
    title="Sample Issue",
    status="Open",
    assignee="user1",
    reporter="user2",
    labels=["bug"],
    issue_type="Bug",
    priority="High",
    raw={"id": "12345", "key": "PROJ-123"},
)

issue = svc.import_normalized_issue(
    tracker_connection_id="<connection-id>",
    normalized_issue=normalized,
)
print(issue)
```

## Observability

### ログ確認

```bash
# 同期失敗イベント
sqlite3 data/tracker.db "
SELECT remote_ref, event_type, error_message, occurred_at
FROM sync_event
WHERE status = 'failed'
ORDER BY occurred_at DESC
LIMIT 10;
"

# 未処理イベント
sqlite3 data/tracker.db "
SELECT id, remote_ref, event_type, occurred_at
FROM sync_event
WHERE status = 'pending'
ORDER BY occurred_at ASC;
"
```

### 失敗兆候と対応

| 兆候 | 原因 | 対応 |
|------|------|------|
| sync_event.status = 'failed' | 外部API接続失敗 | ネットワーク/認証確認、再試行 |
| issue_cache が更新されない | Adapter未実装 | fetch_issue を実装 |
| entity_link 重複エラー | 既存リンク | スキップまたは link_role 変更 |

## Confirm

```bash
# 1. テスト成功
pytest && echo "Tests passed"

# 2. 型チェック成功
mypy tracker_bridge && echo "Type check passed"

# 3. リント成功
ruff check . && echo "Lint passed"

# 4. DBスキーマ確認
sqlite3 data/tracker.db ".schema" | grep -c "CREATE TABLE"
# 期待値: 4 (tracker_connection, issue_cache, entity_link, sync_event)
```

## Rollback / Retry

### DBロールバック

```bash
# バックアップから復元
cp data/tracker.db.bak data/tracker.db
```

### 失敗イベント再試行

```python
from tracker_bridge.db import connect
from tracker_bridge.repositories.sync_event import SyncEventRepository

conn = connect("data/tracker.db")
repo = SyncEventRepository(conn)

# 失敗イベント一覧
failed = repo.list(status="failed")
for event in failed:
    print(f"{event.id}: {event.remote_ref} - {event.error_message}")
    # 再試行処理を実装して呼び出し
```

### インシデント記録

失敗が継続する場合は `docs/IN-YYYYMMDD-XXX.md` を作成し、原因・対応を記録する。