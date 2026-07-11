# Changelog

## [1.0.0] - 2026-03-09

### Added

- live adapter test coverage and integration-oriented service workflow tests
- repo-bundled Codex skill under `skills/tracker-bridge-materials/`
- human-oriented documentation split via `README-human.md`
- release note source under `docs/releases/v1.0.0.md`

### Changed

- standardized typed_ref handling around canonical 4-segment refs for write paths
- tightened tracker connection boundary handling in link resolution, snapshots, cache lookups, and sync event flows
- aligned SQL spec, requirements, and README structure with the accepted roadmap state
- set package metadata for the formal `1.0.0` release

### Fixed

- ambiguous tracker issue resolution when the same issue key exists across multiple connections
- legacy ref leakage on canonical write paths
- documentation leakage of local absolute paths in public repository content

### Maintenance

- project enters minimal-maintenance mode after `1.0.0`
- future changes should focus on severe bug fixes, documentation corrections, and compatibility preservation

## [0.1.0] - 2026-03-09

### Added

- initial tracker-bridge materials bundle
- base SQLite schema, repositories, services, resolvers, and tests
- roadmap, requirements, evaluation, and runbook documentation

## [1.1.0] - 2026-07-11

### Added

- audited GitHub Issue creation through TrackerIntegrationService
- durable handoff fingerprint and hidden idempotency marker reconciliation
- concurrent reservation ownership and outcome-unknown handling
- v1.1.0 CI and release documentation

### Security

- credentials are resolved only through tracker_connection.secret_ref
- tokens are excluded from DB payloads and sanitized errors

### Validation

- ruff check .
- mypy tracker_bridge tests
- pytest --cov --cov-fail-under=80
