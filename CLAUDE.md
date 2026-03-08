# CLAUDE.md - tracker-bridge-materials

## Priority Reference

**`BLUEPRINT.md` が最上位方針です。必ず最初に参照してください。**

Blueprint内の「優先実施順序」セクションに記載された `docs/kv-priority-roadmap/` のプライオリティに従ってください。

### Critical Rules

- **実施順を崩さないこと**: P1 → P2 → P3 → P4 → P5
- **typed_ref統一前に並行作業を進めるのは危険**

## Project Overview

tracker-bridge is a synchronization layer between external trackers (Jira, GitHub Issues, Backlog, Linear, etc.) and internal systems (agent-taskstate/memx-core).

### Key Concepts

- **typed_ref format**: `<domain>:<entity_type>:<provider>:<entity_id>`
  - Examples: `agent-taskstate:task:local:01JABCDEF...`, `tracker:issue:jira:PROJ-123`

### Development Commands

```bash
pip install -e ".[dev]"  # Install with dev dependencies
pytest                   # Run tests
mypy tracker_bridge      # Type check
ruff check .             # Lint
```