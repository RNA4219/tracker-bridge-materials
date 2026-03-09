---
name: "tracker-bridge-materials"
description: "Use when working in the tracker-bridge-materials repository on typed_ref canonicalization, tracker integration, issue_cache/entity_link/sync_event behavior, context rebuild flows, docs consistency, acceptance checks, or test updates. Trigger when the user mentions tracker-bridge-materials, this repo's README/BLUEPRINT/GUARDRAILS/RUNBOOK, or asks for review/fixes inside this repository."
---

# Tracker Bridge Materials Skill

Treat this skill as the default operating guide for work inside the `tracker-bridge-materials` repository.

## Start here

1. Confirm you are in the repository root.
   - Look for `README.md`, `README-human.md`, `BLUEPRINT.md`, and `pyproject.toml`.
2. Read the repo's agent-first guide first: `README.md`.
3. Read `BLUEPRINT.md` and `docs/kv-priority-roadmap/` before changing implementation.
4. Read `GUARDRAILS.md` before changing architecture, refs, or persistence behavior.

## Operating rules

- Preserve the execution order P1 -> P2 -> P3 -> P4.
- Emit canonical typed_ref values in 4 segments only.
- Allow legacy 3-segment refs only for read compatibility.
- Keep `tracker-bridge` as a helper layer; do not make external trackers the source of truth.
- Keep tracker connection boundaries intact. If a lookup can be ambiguous across connections, resolve by connection-specific metadata or fail explicitly.
- Update docs when you change typed_ref, schema, sync semantics, or acceptance expectations.

## Common task routing

Read `references/repo-map.md` when you need file-level guidance.

- For typed_ref changes: inspect `tracker_bridge/refs.py`, `tracker_bridge/models.py`, `tests/test_refs.py`, and `docs/kv-priority-roadmap/01-typed-ref-unification.md`.
- For tracker integration fixes: inspect `tracker_bridge/services/tracker_integration_service.py`, `tracker_bridge/repositories/issue_cache.py`, `tracker_bridge/repositories/sync_event.py`, `tracker_bridge/services/issue_service.py`, and the service/repository tests.
- For context rebuild or resolver work: inspect `tracker_bridge/services/context_rebuild_service.py`, `tracker_bridge/resolver/`, `tests/test_context_rebuild.py`, and `tests/test_resolver*.py`.
- For acceptance or inspection work: compare code and tests against `docs/tracker-bridge-requirements.md`, `docs/tracker-bridge-sqlite-spec.md`, `BLUEPRINT.md`, and `EVALUATION.md`.

## Verification baseline

Run the standard checks after meaningful changes:

```bash
ruff check .
mypy tracker_bridge tests
pytest
pytest --cov
```

For review requests, prioritize concrete findings first: broken behavior, regression risk, missing tests, and requirement mismatches.
