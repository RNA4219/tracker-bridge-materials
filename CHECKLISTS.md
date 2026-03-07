---
intent_id: INT-TB-001
owner: tracker-bridge-team
status: active
last_reviewed_at: 2025-03-08
next_review_due: 2025-04-08
---

# Checklists - tracker-bridge

## リリース前チェック

### コード品質

- [ ] 全テストがパスする (`pytest`)
- [ ] 型チェックがパスする (`mypy --strict`)
- [ ] リントがパスする (`ruff check .`)
- [ ] カバレッジ 80% 以上 (`pytest --cov`)

### ドキュメント

- [ ] BLUEPRINT.md の更新が必要な場合は更新済み
- [ ] CHANGELOG.md に変更内容を記載
- [ ] 新規APIの場合はインターフェース文書を更新

### セキュリティ

- [ ] 認証情報がコードに含まれていない
- [ ] 環境変数またはsecret storeの使用を確認

## レビューチェック

### 機能

- [ ] 要件を満たしている
- [ ] エッジケースが考慮されている
- [ ] エラーハンドリングが適切

### 構造

- [ ] 単一責任の原則に従っている
- [ ] 過度な抽象化をしていない
- [ ] テスト可能性が確保されている

### 互換性

- [ ] typed_ref は 4 セグメント形式で出力
- [ ] 既存の 3 セグメント形式を読み込める（移行期間中）