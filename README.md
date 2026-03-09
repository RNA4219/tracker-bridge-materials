# tracker-bridge Agent README

人間向けの概要は [README-human.md](README-human.md) を参照してください。

## 同梱 Skill

- Skill 名: `$tracker-bridge-materials`
- 格納先: `skills/tracker-bridge-materials/`
- 入口: `skills/tracker-bridge-materials/SKILL.md`

## 最初に読む順番

| 順番 | ファイル |
|------|----------|
| 1 | `skills/tracker-bridge-materials/SKILL.md` |
| 2 | `BLUEPRINT.md` |
| 3 | `docs/kv-priority-roadmap/` |
| 4 | `GUARDRAILS.md` |
| 5 | `RUNBOOK.md` |
| 6 | `docs/tracker-bridge-requirements.md` |
| 7 | `docs/tracker-bridge-sqlite-spec.md` |
| 8 | `README-human.md` |

## 実施ルール

| 項目 | ルール |
|------|--------|
| 優先順 | `P1 -> P2 -> P3 -> P4` を崩さない |
| typed_ref | 新規出力は 4 セグメント canonical |
| 疎結合 | `agent-taskstate` / `memx-core` とは typed_ref による論理参照のみ |
| 秘密情報 | 認証情報を DB に保存しない |

## 検証

```bash
pip install -e ".[dev]"
ruff check .
mypy tracker_bridge tests
pytest
pytest --cov
```

## 参照

- `RUNBOOK.md`
- `EVALUATION.md`
- `docs/tracker-bridge-requirements.md`
- `docs/tracker-bridge-sqlite-spec.md`
