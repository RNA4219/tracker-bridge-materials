# tracker-bridge

External tracker sync bridge for agent-taskstate/memx-core integration.

## Overview

tracker-bridge is a synchronization layer between external trackers (Jira, GitHub Issues, Backlog, Linear, etc.) and internal systems (agent-taskstate/memx-core).

It is responsible for:
- Connection management to external trackers
- Local caching of external issues
- Entity linking between external issues and internal tasks
- Sync event logging and auditing

## Quick Start

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type check
mypy tracker_bridge

# Lint
ruff check .
```

## Project Structure

```
tracker-bridge-materials/
├── docs/                           # Requirements and SQL schema
│   ├── tracker-bridge-requirements.md
│   ├── tracker-bridge-sqlite-spec.md
│   └── 0001_init_tracker_bridge.sql
├── tracker_bridge/                 # Python package
│   ├── models.py                   # Data models
│   ├── db.py                       # Database connection
│   ├── errors.py                   # Custom exceptions
│   ├── refs.py                     # typed_ref utilities
│   ├── repositories/               # Data access layer
│   ├── services/                   # Business logic layer
│   ├── adapters/                   # External tracker adapters
│   └── cli/                        # CLI (planned)
├── tests/                          # Test suite
├── BLUEPRINT.md                    # Requirements blueprint
├── RUNBOOK.md                      # Operations guide
├── EVALUATION.md                   # Acceptance criteria
└── pyproject.toml                  # Project configuration
```

## Data Models

### tracker_connection
External tracker connection definition.

### issue_cache
Local cache of external issue state.

### entity_link
Mapping between external issues and internal entities (e.g., agent-taskstate:task:local:*).

### sync_event
Sync event history for auditing.

## typed_ref Format

References across systems use typed_ref format:

```
<domain>:<entity_type>:<provider>:<entity_id>
```

Examples:
- `agent-taskstate:task:local:01JABCDEF...`
- `memx:evidence:local:01JXYZ...`
- `tracker:issue:jira:PROJ-123`
- `tracker:issue:github:owner/repo#45`

## License

Apache-2.0




