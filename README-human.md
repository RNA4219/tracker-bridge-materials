# tracker-bridge

Agent 向けの正本は [README.md](README.md) を参照してください。人間向けの概要はこのファイルです。

tracker-bridge は、Jira / GitHub Issues / Linear などの外部トラッカーと、`agent-taskstate` / `memx-core` の間をつなぐ同期ブリッジです。

## 読み始める順番

| 対象 | ファイル |
|------|----------|
| 人間 | `README-human.md` |
| 実装担当 | `RUNBOOK.md` |
| 要件確認 | `docs/tracker-bridge-requirements.md` |
| スキーマ確認 | `docs/tracker-bridge-sqlite-spec.md` |
| Agent / 自動化 | `README.md` |
| Agent / 自動化 | `skills/tracker-bridge-materials/SKILL.md` |

## リポジトリ構成

| パス | 内容 |
|------|------|
| `tracker_bridge/` | Python 実装本体 |
| `tests/` | テスト |
| `docs/` | 要件、SQLite 仕様、ロードマップ |
| `skills/` | repo 同梱 Codex skill |
| `RUNBOOK.md` | 実行・検証手順 |
| `BLUEPRINT.md` | 設計方針 |
| `EVALUATION.md` | 検収観点 |

## クイックスタート

```bash
pip install -e ".[dev]"
ruff check .
mypy tracker_bridge tests
pytest
pytest --cov
```

## 参照

- Agent 向け入口: [README.md](README.md)
- repo 同梱 skill: [skills/tracker-bridge-materials/SKILL.md](skills/tracker-bridge-materials/SKILL.md)
- 要件: [docs/tracker-bridge-requirements.md](docs/tracker-bridge-requirements.md)
- DB: [docs/tracker-bridge-sqlite-spec.md](docs/tracker-bridge-sqlite-spec.md)
- SQL: [docs/0001_init_tracker_bridge.sql](docs/0001_init_tracker_bridge.sql)
- 実行: [RUNBOOK.md](RUNBOOK.md)

## ライセンス

Apache-2.0
