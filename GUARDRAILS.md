---
intent_id: INT-TB-001
owner: tracker-bridge-team
status: active
last_reviewed_at: 2025-03-08
next_review_due: 2025-04-08
---

# Guardrails - tracker-bridge

## 行動指針

### 1. 実施順序の遵守

- `docs/kv-priority-roadmap/` のプライオリティ順序を厳守する
- typed_ref統一前に並行作業を進めない
- ブロッカーが解決するまで次のフェーズに進まない

### 2. typed_ref の一貫性

- 新規生成する ref は必ず 4 セグメント形式を使用
- 形式: `<domain>:<entity_type>:<provider>:<entity_id>`
- 3 セグメント形式は読み込みのみ許可（出力は禁止）

### 3. 疎結合の維持

- agent-taskstate / memx-core とは typed_ref による論理参照のみ
- DBに認証情報を保存しない
- 外部トラッカーの完全ミラーリングを行わない

### 4. MVP優先

- 複雑な双方向同期よりも、責務分離と追跡可能性を優先
- 1つのタスクは 0.5日以内で完了する粒度にする

## 禁止事項

- [ ] typed_ref統一なしに複数PJを並行進行
- [ ] 外部トラッカー情報を task 再開の必須条件にする
- [ ] DBへの認証情報保存
- [ ] agent-taskstate/memx-core の内部実装への直接依存

## エスカレーション

問題やブロッカーが発生した場合は `docs/IN-YYYYMMDD-XXX.md` を作成し、原因・対応を記録する。