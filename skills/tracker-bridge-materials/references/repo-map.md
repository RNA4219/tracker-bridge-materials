# Repo Map

Use this file when the task is inside `tracker-bridge-materials` and you need to locate the right implementation or validation surface quickly.

## High-signal files by concern

| Concern | Primary files | Validation |
|---------|---------------|------------|
| typed_ref contract | `tracker_bridge/refs.py`, `tracker_bridge/models.py` | `tests/test_refs.py`, roadmap P1 docs |
| link creation / canonical write | `tracker_bridge/services/link_service.py`, `tracker_bridge/repositories/entity_link.py` | `tests/test_service_workflows.py`, `tests/test_repositories.py` |
| issue import / idempotency | `tracker_bridge/services/issue_service.py`, `tracker_bridge/repositories/issue_cache.py`, `tracker_bridge/repositories/sync_event.py` | `tests/test_services.py`, `tests/test_repositories.py` |
| tracker integration flow | `tracker_bridge/services/tracker_integration_service.py` | `tests/test_services.py`, `tests/test_service_workflows.py` |
| context rebuild | `tracker_bridge/services/context_rebuild_service.py`, `tracker_bridge/services/context_bundle_service.py` | `tests/test_context_rebuild.py`, `tests/test_context_bundle.py` |
| tracker resolver | `tracker_bridge/resolver/tracker_resolver.py` | `tests/test_resolver.py`, `tests/test_resolver_integration.py` |
| memx resolver | `tracker_bridge/resolver/memx_resolver.py` | `tests/test_resolver_integration.py` |
| schema / persistence | `docs/0001_init_tracker_bridge.sql`, `docs/tracker-bridge-sqlite-spec.md` | schema-oriented repository tests |
| acceptance / roadmap fit | `BLUEPRINT.md`, `EVALUATION.md`, `docs/kv-priority-roadmap/`, `docs/tracker-bridge-requirements.md` | code + tests + docs consistency review |

## Task-specific reminders

### Review or acceptance work
- Compare implementation to roadmap acceptance criteria, not only to current tests.
- Flag mismatches between code, docs, and SQL examples.
- Check whether new tests cover regressions, not just happy paths.

### Multi-connection tracker behavior
- Treat `tracker_type + remote_issue_key` as potentially ambiguous across connections.
- Verify issue lookup, snapshot export, and linked issue resolution preserve `tracker_connection_id` boundaries.

### Docs updates
- When changing behavior that users or agents depend on, update both the repo guide (`README.md` / `README-human.md`) and the relevant spec docs.
