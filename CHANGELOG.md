# Changelog

## [0.2.0] - 2026-03-09

### Added

- live adapter test coverage and integration-oriented service workflow tests
- repo-bundled Codex skill under `skills/tracker-bridge-materials/`
- human-oriented documentation split via `README-human.md`
- release note source under `docs/releases/v0.2.0.md`

### Changed

- standardized typed_ref handling around canonical 4-segment refs for write paths
- tightened tracker connection boundary handling in link resolution, snapshots, cache lookups, and sync event flows
- aligned SQL spec, requirements, and README structure with the accepted roadmap state
- reorganized README roles into agent-first `README.md`, human-facing `README-human.md`, and compatibility `AGENTS.md`

### Fixed

- ambiguous tracker issue resolution when the same issue key exists across multiple connections
- legacy ref leakage on canonical write paths
- documentation leakage of local absolute paths in public repository content

## [0.1.0] - 2026-03-09

### Added

- initial tracker-bridge materials bundle
- base SQLite schema, repositories, services, resolvers, and tests
- roadmap, requirements, evaluation, and runbook documentation
