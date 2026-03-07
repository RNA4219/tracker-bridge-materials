-- P3: State History and Bundle Audit Tables

-- 状態遷移履歴（append-only）
CREATE TABLE IF NOT EXISTS state_transition (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('sync_event', 'issue_cache', 'entity_link')),
    entity_id TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('system', 'user', 'agent')),
    actor_id TEXT,
    run_id TEXT,
    changed_at TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_state_transition_entity
    ON state_transition(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_state_transition_changed_at
    ON state_transition(changed_at DESC);

-- コンテキストバンドル（監査情報付き）
CREATE TABLE IF NOT EXISTS context_bundle (
    id TEXT PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (purpose IN ('resume', 'handoff', 'checkpoint', 'audit')),
    summary TEXT NOT NULL,
    rebuild_level TEXT NOT NULL CHECK (rebuild_level IN ('full', 'summary', 'minimal')),
    raw_included INTEGER NOT NULL CHECK (raw_included IN (0, 1)),
    generator_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    decision_digest TEXT,
    open_question_digest TEXT,
    diagnostics_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_context_bundle_generated_at
    ON context_bundle(generated_at DESC);

-- バンドルソース参照（append-only）
CREATE TABLE IF NOT EXISTS context_bundle_source (
    id TEXT PRIMARY KEY,
    context_bundle_id TEXT NOT NULL,
    typed_ref TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('evidence', 'artifact', 'decision', 'tracker_issue', 'task')),
    selected_raw INTEGER NOT NULL DEFAULT 0 CHECK (selected_raw IN (0, 1)),
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (context_bundle_id) REFERENCES context_bundle(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_context_bundle_source_bundle
    ON context_bundle_source(context_bundle_id);

CREATE INDEX IF NOT EXISTS idx_context_bundle_source_ref
    ON context_bundle_source(typed_ref);