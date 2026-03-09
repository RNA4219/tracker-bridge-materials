# tracker-bridge

Agent 向けの正本は [README.md](README.md) を参照してください。  
このファイルは、人間がリポジトリの目的、責務、構成、読み方を理解するための説明用 README です。

tracker-bridge は、Jira / GitHub Issues / Linear / Backlog などの外部トラッカーと、内部の `agent-taskstate` / `memx-core` を接続するための同期ブリッジです。  
外部 issue をそのまま内部状態の正本にせず、接続定義、ローカル投影、リンク、同期履歴という中間層を明示的に持つことで、内部状態を壊さずに外部運用と接続することを目的にしています。

## 保守方針

このリポジトリは `v1.0.0` を正式リリースとし、以後の保守は最低限に留めます。

- 重大な不具合修正
- 公開情報やドキュメントの是正
- 既存利用者への互換性維持

新機能追加や大規模な設計変更は、原則としてこの repo では積極的に進めません。

## このリポジトリがやること

- 外部トラッカーへの接続定義を保持する
- 外部 issue を `issue_cache` としてローカルに投影する
- 外部 issue と内部 task / artifact を `typed_ref` で疎結合に関連付ける
- inbound / outbound の同期イベントを `sync_event` に残し、監査可能にする
- Agent が扱える最小限の bridge 実装と資料を OSS として提供する

## やらないこと

- `agent-taskstate` の task state 自体を管理すること
- `memx-core` の evidence / knowledge を保存すること
- 外部トラッカーを完全ミラーリングすること
- 全コメント、全履歴、全添付ファイルを完全再現すること
- エージェント本体の推論やオーケストレーションを持つこと

## 位置づけ

この repo の責務は「外部トラッカーとの接続・写像・同期履歴」に限定されます。

- `agent-taskstate`
  - 内部 task / decision / open_question / context_bundle の正本
- `memx-core`
  - 知識・証拠・要約の正本
- `tracker-bridge`
  - 外部トラッカーとの接続、ローカル投影、リンク、同期監査の正本

この分離により、外部トラッカーを使った現場運用と、内部での詳細な思考・作業状態管理を混ぜずに扱えます。

## 典型的な使い方

### 1. 外部 issue を取り込む

Jira や GitHub Issues などから issue を取得し、外部 API の結果をそのまま業務ロジックに渡すのではなく、まず `issue_cache` に正規化して保存します。  
これにより、後続の link 作成、同期判定、再試行、監査を tracker ごとの API 仕様に引きずられずに扱えます。

### 2. 外部 issue と内部 task を結びつける

外部 issue は `tracker:issue:<provider>:<id>` のような `typed_ref` で扱い、内部 task や artifact は `agent-taskstate:*` や `memx:*` として参照します。  
両者の関係は `entity_link` に保存され、primary / related / duplicate / blocks などの link_role を持てます。

### 3. 同期イベントを監査する

外部からの更新反映や、内部から外部への status / comment 反映は `sync_event` に残します。  
そのため、失敗時の再試行、原因調査、重複反映の抑制、後追い確認がしやすい構成です。

## 主要な設計ルール

### typed_ref を正本にする

repo 間の参照は DB の外部キーや直接依存ではなく、`typed_ref` による論理参照で扱います。  
canonical format は次の 4 セグメントです。

```text
<domain>:<entity_type>:<provider>:<entity_id>
```

例:

- `agent-taskstate:task:local:01JABCDEF...`
- `memx:evidence:local:01JXYZ...`
- `tracker:issue:jira:PROJ-123`
- `tracker:issue:github:owner/repo#45`

新規出力は canonical 4 セグメントのみを扱い、legacy 形式は必要最小限の read 互換に留めます。

### 外部トラッカーを正本にしない

この repo は同期ブリッジであり、内部 state の所有者ではありません。  
外部トラッカーの情報を取り込み、内部 state と対応付け、必要最小限の同期を行いますが、内部の思考・証拠・作業状態を外部 tracker に押し込む設計にはしません。

### connection 境界を保つ

同じ `tracker_type + issue_key` であっても、connection が違えば別物として扱う必要があります。  
そのため、lookup や link 解決、snapshot、resolver では `tracker_connection_id` を落とさないことが重要です。

## 最小データモデル

### `tracker_connection`

どの tracker に、どの base URL / workspace / project で接続するかを表します。  
認証情報そのものは DB に保存せず、環境変数や secret store の参照先だけを持ちます。

### `issue_cache`

外部 issue の現在状態を保持するローカル投影です。  
title、status、assignee、labels、raw payload などを保持し、外部 API を毎回直接叩かなくても現在状態を参照できます。

### `entity_link`

外部 issue と内部 entity の対応付けです。  
`local_ref` と `remote_ref` を中心に、どの関係で紐づいているかを `link_role` で表します。

### `sync_event`

同期履歴と冪等制御のためのイベントログです。  
direction、status、payload、error_message、occurred_at、processed_at などを保持し、成功・失敗・再処理を追跡できます。

## リポジトリ構成

| パス | 内容 |
|------|------|
| `tracker_bridge/` | Python 実装本体 |
| `tests/` | 単体テスト、統合寄りテスト |
| `docs/` | 要件、SQLite 仕様、ロードマップ、SQL |
| `skills/` | repo 同梱 Codex skill |
| `RUNBOOK.md` | セットアップ、実行、検証手順 |
| `BLUEPRINT.md` | 優先順位付きの設計方針 |
| `EVALUATION.md` | 検収観点、確認項目 |

## 読み始める順番

### 人間が全体像を掴みたい場合

1. `README-human.md`
2. `docs/tracker-bridge-requirements.md`
3. `docs/tracker-bridge-sqlite-spec.md`
4. `RUNBOOK.md`

### 実装やレビューに入る場合

1. `README.md`
2. `skills/tracker-bridge-materials/SKILL.md`
3. `BLUEPRINT.md`
4. `docs/kv-priority-roadmap/`

## クイックスタート

```bash
pip install -e ".[dev]"
ruff check .
mypy tracker_bridge tests
pytest
pytest --cov
```

## この repo で確認しやすいこと

- typed_ref の canonical 化が一貫しているか
- 外部 issue の取り込みとローカル投影ができているか
- link 作成時に canonical ref と connection 境界が保たれているか
- sync_event による監査、冪等制御、失敗追跡ができるか
- 要件、SQL、実装、テストの整合が取れているか

## Agent / OSS 配布について

この repo は Agent ファーストの OSS として、repo 内に skill を同梱しています。  
Codex などの Agent は [skills/tracker-bridge-materials/SKILL.md](skills/tracker-bridge-materials/SKILL.md) を入口に、実装レビュー、受入確認、typed_ref 修正、tracker integration 修正、docs 整合確認を進められます。

一方で、運用者やレビュー担当者が全体像を理解するための説明はこの `README-human.md` に集約します。  
つまり、`README.md` は最小導線、`README-human.md` は背景説明、`SKILL.md` は Agent 実務手順、という分担です。

## 参照

- Agent 向け入口: [README.md](README.md)
- repo 同梱 skill: [skills/tracker-bridge-materials/SKILL.md](skills/tracker-bridge-materials/SKILL.md)
- 要件: [docs/tracker-bridge-requirements.md](docs/tracker-bridge-requirements.md)
- DB: [docs/tracker-bridge-sqlite-spec.md](docs/tracker-bridge-sqlite-spec.md)
- SQL: [docs/0001_init_tracker_bridge.sql](docs/0001_init_tracker_bridge.sql)
- 実行: [RUNBOOK.md](RUNBOOK.md)
- 検収: [EVALUATION.md](EVALUATION.md)

## ライセンス

Apache-2.0
