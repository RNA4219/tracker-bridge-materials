# tracker-bridge Agent README

人間向けの概要は [README-human.md](README-human.md) を参照してください。

このリポジトリは Agent ファーストで運用する前提の materials bundle です。作業着手前に、優先順・typed_ref 契約・疎結合制約を確認してください。

## 同梱 Skill

- Skill 名: `$tracker-bridge-materials`
- 格納先: `skills/tracker-bridge-materials/`
- 入口: `skills/tracker-bridge-materials/SKILL.md`
- 使いどころ: このリポジトリで review、受入確認、typed_ref 修正、tracker integration 修正、docs 整合確認を行うとき

## 最初に読む順番

| 順番 | ファイル | 目的 | 必須度 |
|------|----------|------|--------|
| 1 | `skills/tracker-bridge-materials/SKILL.md` | repo 同梱 skill の運用ガイドを読む | 必須 |
| 2 | `BLUEPRINT.md` | 最上位の方針と実施順の確認 | 必須 |
| 3 | `docs/kv-priority-roadmap/` | P1-P4 の依存関係と受入条件の確認 | 必須 |
| 4 | `GUARDRAILS.md` | 禁止事項と行動制約の確認 | 必須 |
| 5 | `RUNBOOK.md` | 実行コマンドと確認手順の確認 | 推奨 |
| 6 | `docs/tracker-bridge-requirements.md` | 要件・MVP 範囲の確認 | 推奨 |
| 7 | `docs/tracker-bridge-sqlite-spec.md` | スキーマ・冪等性・クエリ方針の確認 | 推奨 |
| 8 | `README-human.md` | 人間向けの概要説明と導線確認 | 任意 |

## 実施順序ルール

| 項目 | ルール | 出典 |
|------|--------|------|
| 優先順 | P1 -> P2 -> P3 -> P4 を崩さない | `BLUEPRINT.md`, `CLAUDE.md` |
| typed_ref | 新規出力は常に 4 セグメント canonical | `GUARDRAILS.md`, `docs/kv-priority-roadmap/01-typed-ref-unification.md` |
| 疎結合 | `agent-taskstate` / `memx-core` とは typed_ref による論理参照のみ | `GUARDRAILS.md` |
| 秘密情報 | 認証情報を DB に保存しない | `GUARDRAILS.md`, `docs/tracker-bridge-sqlite-spec.md` |
| MVP 方針 | 完全同期より責務分離と追跡可能性を優先 | `GUARDRAILS.md`, `docs/tracker-bridge-requirements.md` |

## 主要コマンド

| 目的 | コマンド |
|------|----------|
| 依存関係導入 | `pip install -e ".[dev]"` |
| リント | `ruff check .` |
| 型チェック | `mypy tracker_bridge tests` |
| テスト | `pytest` |
| カバレッジ確認 | `pytest --cov` |

## 補助資料

| 目的 | ファイル |
|------|----------|
| repo 同梱 skill | `skills/tracker-bridge-materials/SKILL.md` |
| 人間向け概要 | `README-human.md` |
| 実行と運用 | `RUNBOOK.md` |
| 検収観点 | `EVALUATION.md` |
| 要件詳細 | `docs/tracker-bridge-requirements.md` |
| SQL/DB 仕様 | `docs/tracker-bridge-sqlite-spec.md` |
