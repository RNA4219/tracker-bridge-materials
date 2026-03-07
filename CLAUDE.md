# CLAUDE.md - tracker-bridge-materials

## Priority Reference

**`docs/kv-priority-roadmap/` is the highest priority reference for this project.**

Always consult this directory first when making decisions about implementation order or priorities.

### Priority Order

1. `kv-cache-independence-amendments.md`
2. `01-typed-ref-unification.md`
3. `02-workx-state-history-and-bundle-audit.md`
4. `03-workx-memx-context-rebuild-resolver.md`
5. `04-tracker-bridge-minimum-integration.md`

### Critical Rules

- **Do not deviate from the implementation order.**
- **Do not proceed with projects in parallel before typed_ref unification is complete.** Doing so is dangerous and may cause inconsistencies across projects.

## Project Overview

tracker-bridge is a synchronization layer between external trackers (Jira, GitHub Issues, Backlog, Linear, etc.) and internal systems (workx/memx-core).

### Key Concepts

- **typed_ref format**: `<domain>:<type>:<id_or_key>`
  - Examples: `workx:task:01JABCDEF...`, `tracker:jira:PROJ-123`

### Development Commands

```bash
pip install -e ".[dev]"  # Install with dev dependencies
pytest                   # Run tests
mypy tracker_bridge      # Type check
ruff check .             # Lint
```