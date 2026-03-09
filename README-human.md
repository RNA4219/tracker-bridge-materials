# tracker-bridge

Agent 向けの正本は [README.md](README.md) を参照してください。人間向けの概要はこのファイルです。

tracker-bridge は、Jira / GitHub Issues / Linear などの外部トラッカーと、`agent-taskstate` / `memx-core` の間をつなぐ同期ブリッジです。

補足: Agent で作業する場合は repo 同梱の `$tracker-bridge-materials` skill を使う前提で、入口は `README.md` と `skills/tracker-bridge-materials/SKILL.md` です。

## このリポジトリで分かること

- 外部 issue を内部で扱うための最小データモデル
- typed_ref を使った疎結合な参照ルール
- inbound / outbound sync_event の記録方法
- issue_cache / entity_link / context rebuild の最小実装
- OSS として配布できる repo 同梱 skill

## 読み始める順番

| 対象 | まず読むもの | 目的 |
|------|--------------|------|
| 人間 | `README-human.md` | 概要、入口、主要ドキュメントの把握 |
| 実装担当 | `RUNBOOK.md` | セットアップ、実行、確認手順 |
| 要件確認 | `docs/tracker-bridge-requirements.md` | MVP 範囲と受入条件の確認 |
| スキーマ確認 | `docs/tracker-bridge-sqlite-spec.md` | DB 設計とクエリ方針の確認 |
| Agent / 自動化 | `README.md` | Agent 向け優先順、制約、確認観点の確認 |
| Agent / 自動化 | `skills/tracker-bridge-materials/SKILL.md` | repo 同梱 skill の即時利用 |

## リポジトリ構成

| パス | 内容 |
|------|------|
| `tracker_bridge/` | Python 実装本体 |
| `tests/` | 単体テスト、結合寄りテスト |
| `docs/` | 要件、SQLite 仕様、ロードマップ |
| `skills/` | repo と一緒に配布する Codex skill |
| `RUNBOOK.md` | 実行・検証・運用手順 |
| `BLUEPRINT.md` | 優先順位付きの設計方針 |
| `EVALUATION.md` | 検収観点と確認項目 |

## クイックスタート

```bash
pip install -e ".[dev]"
ruff check .
mypy tracker_bridge tests
pytest
pytest --cov
```

## この実装の前提

- typed_ref の canonical format は `<domain>:<entity_type>:<provider>:<entity_id>`
- `tracker-bridge` は外部トラッカーとの同期補助層であり、内部状態の正本ではありません
- 認証情報は DB に保存せず、環境変数や secret store 参照を前提にします

## 次に見るべき資料

- Agent 向け入口: [README.md](README.md)
- repo 同梱 skill: [skills/tracker-bridge-materials/SKILL.md](skills/tracker-bridge-materials/SKILL.md)
- 仕様確認: [docs/tracker-bridge-requirements.md](docs/tracker-bridge-requirements.md)
- DB 詳細: [docs/tracker-bridge-sqlite-spec.md](docs/tracker-bridge-sqlite-spec.md)
- SQL 初期化: [docs/0001_init_tracker_bridge.sql](docs/0001_init_tracker_bridge.sql)
- 実行手順: [RUNBOOK.md](RUNBOOK.md)

## ライセンス

Apache-2.0
