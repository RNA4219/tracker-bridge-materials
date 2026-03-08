---
intent_id: INT-TB-001
owner: tracker-bridge-team
status: active
last_reviewed_at: 2025-03-08
next_review_due: 2025-04-08
---

# Evaluation - tracker-bridge

## Acceptance Criteria

### MVP成功条件

- [ ] 外部 issue 1件を取得できる
- [ ] issue_cache に保存できる
- [ ] agent-taskstate.task 1件とリンクできる
- [ ] inbound sync_event を履歴として残せる
- [ ] 内部完了イベントを外部へ 1 回反映できる
- [ ] 失敗時に failed 履歴と原因を確認できる

### 品質基準

- [ ] 全テストがパスする (`pytest`)
- [ ] 型チェックがパスする (`mypy --strict`)
- [ ] リントがパスする (`ruff check .`)
- [ ] カバレッジ 80% 以上 (`pytest --cov`)

## KPIs

| 指標 | 目的 | 収集方法 | 目標値 |
|------|------|----------|--------|
| `sync_success_rate` | 同期成功率を可視化 | sync_event.status 集計 | 95%以上 |
| `sync_latency_seconds` | 同期処理時間を監視 | occurred_at ~ processed_at | 30秒以下 |
| `failed_event_age_minutes` | 失敗イベントの未解決期間 | occurred_at からの経過時間 | 1440分以下 |

## Test Outline

### 単体テスト

- `test_models.py`: データモデルの生成・アクセス
- `test_db.py`: DB接続・トランザクション
- `test_refs.py`: typed_ref 生成・検証
- `test_repositories.py`: 各リポジトリの CRUD 操作

### 結合テスト

- `test_services.py`: サービス層のワークフロー
  - IssueService.import_normalized_issue
  - LinkService.create_link
  - SyncService.emit_outbound_event

### MVP検証シナリオ

1. **Issue取り込み**: JiraAdapter.normalize_issue → IssueService.import_normalized_issue
2. **リンク作成**: LinkService.create_link で agent-taskstate:task:* と tracker:jira:* を紐付け
3. **同期履歴**: sync_event テーブルに inbound/outbound イベントが記録される

## Verification Checklist

- [ ] 主要フローが動作する（手動確認）
  ```bash
  pytest tests/test_repositories.py -v
  ```
- [ ] エラー時挙動が明示されている
  - NotFoundError: レコード不明
  - DuplicateError: 重複レコード
  - ValidationError: 不正な typed_ref
- [ ] 依存関係が再現できる環境である
  - `pip install -e ".[dev]"` で環境構築可能