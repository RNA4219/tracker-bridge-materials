# AGENTS.md

人間向けの概要は [README-human.md](README-human.md) を参照してください。

Agent 向けの正本は [README.md](README.md) です。このファイルは互換エントリです。

## 利用する Skill

- 推奨: `$tracker-bridge-materials`
- 格納先: `skills/tracker-bridge-materials/`
- 入口: `skills/tracker-bridge-materials/SKILL.md`

## 最低限の確認項目

| 項目 | 内容 |
|------|------|
| 優先順 | `BLUEPRINT.md` と `docs/kv-priority-roadmap/` を先に確認する |
| typed_ref | 新規出力は canonical 4 セグメントのみ |
| 疎結合 | `agent-taskstate` / `memx-core` への直接依存を増やさない |
| 検証 | `ruff check .` / `mypy tracker_bridge tests` / `pytest` / `pytest --cov` |

## 詳細参照

- Agent 向け正本: [README.md](README.md)
- repo 同梱 skill: [skills/tracker-bridge-materials/SKILL.md](skills/tracker-bridge-materials/SKILL.md)
- 人間向け README: [README-human.md](README-human.md)
- 実行手順: [RUNBOOK.md](RUNBOOK.md)
- ガードレール: [GUARDRAILS.md](GUARDRAILS.md)
