BEGIN;

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- tracker_connection
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tracker_connection (
  id TEXT PRIMARY KEY,
  tracker_type TEXT NOT NULL,         -- jira / github / linear / backlog / redmine
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  workspace_key TEXT,
  project_key TEXT,
  secret_ref TEXT,                    -- env key / secret store key
  is_enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,           -- ISO 8601 UTC
  updated_at TEXT NOT NULL,           -- ISO 8601 UTC
  metadata_json TEXT,

  CHECK (tracker_type IN ('jira', 'github', 'linear', 'backlog', 'redmine')),
  CHECK (is_enabled IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_tracker_connection_type
  ON tracker_connection(tracker_type);

CREATE INDEX IF NOT EXISTS idx_tracker_connection_enabled
  ON tracker_connection(is_enabled);

-- ------------------------------------------------------------
-- issue_cache
-- 最新の外部 issue 状態を保持するローカル投影
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issue_cache (
  id TEXT PRIMARY KEY,
  tracker_connection_id TEXT NOT NULL,
  remote_issue_id TEXT NOT NULL,      -- provider 固有内部ID
  remote_issue_key TEXT NOT NULL,     -- PROJ-123 / repo#45 など
  title TEXT NOT NULL,
  status TEXT,
  assignee TEXT,
  reporter TEXT,
  labels_json TEXT,
  issue_type TEXT,
  priority TEXT,
  raw_json TEXT NOT NULL,             -- 元レスポンスの最小保持
  last_seen_at TEXT NOT NULL,         -- ISO 8601 UTC
  created_at TEXT NOT NULL,           -- 初回取り込み時刻
  updated_at TEXT NOT NULL,           -- 最終更新時刻

  FOREIGN KEY (tracker_connection_id)
    REFERENCES tracker_connection(id)
    ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_issue_cache_remote
  ON issue_cache(tracker_connection_id, remote_issue_key);

CREATE INDEX IF NOT EXISTS idx_issue_cache_remote_id
  ON issue_cache(tracker_connection_id, remote_issue_id);

CREATE INDEX IF NOT EXISTS idx_issue_cache_status
  ON issue_cache(tracker_connection_id, status);

CREATE INDEX IF NOT EXISTS idx_issue_cache_updated_at
  ON issue_cache(tracker_connection_id, updated_at);

CREATE INDEX IF NOT EXISTS idx_issue_cache_last_seen_at
  ON issue_cache(tracker_connection_id, last_seen_at);

-- ------------------------------------------------------------
-- entity_link
-- 外部 issue と内部 entity(agent-taskstate:task:*, memx:artifact:* など) の対応
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entity_link (
  id TEXT PRIMARY KEY,
  local_ref TEXT NOT NULL,            -- agent-taskstate:task:... / memx:artifact:...
  remote_ref TEXT NOT NULL,           -- tracker:jira:PROJ-123 / tracker:github:repo#45
  link_role TEXT NOT NULL,            -- primary / related / duplicate / blocks / caused_by
  created_at TEXT NOT NULL,           -- ISO 8601 UTC
  updated_at TEXT NOT NULL,           -- ISO 8601 UTC
  metadata_json TEXT,

  CHECK (link_role IN ('primary', 'related', 'duplicate', 'blocks', 'caused_by'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_link_pair
  ON entity_link(local_ref, remote_ref, link_role);

CREATE INDEX IF NOT EXISTS idx_entity_link_local
  ON entity_link(local_ref);

CREATE INDEX IF NOT EXISTS idx_entity_link_remote
  ON entity_link(remote_ref);

CREATE INDEX IF NOT EXISTS idx_entity_link_role
  ON entity_link(link_role);

-- ------------------------------------------------------------
-- sync_event
-- 同期イベント履歴と冪等制御
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_event (
  id TEXT PRIMARY KEY,
  tracker_connection_id TEXT NOT NULL,
  direction TEXT NOT NULL,            -- inbound / outbound
  remote_ref TEXT NOT NULL,
  local_ref TEXT,                     -- agent-taskstate:task:* など
  event_type TEXT NOT NULL,           -- issue_created / issue_updated / comment_created / status_changed / link_created
  fingerprint TEXT,                   -- 冪等制御用
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,               -- pending / applied / failed / skipped
  error_message TEXT,
  occurred_at TEXT NOT NULL,          -- 外部イベント発生時刻
  processed_at TEXT,                  -- 内部処理完了時刻
  created_at TEXT NOT NULL,           -- レコード作成時刻

  FOREIGN KEY (tracker_connection_id)
    REFERENCES tracker_connection(id)
    ON DELETE CASCADE,

  CHECK (direction IN ('inbound', 'outbound')),
  CHECK (status IN ('pending', 'applied', 'failed', 'skipped'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sync_event_fingerprint
  ON sync_event(tracker_connection_id, fingerprint)
  WHERE fingerprint IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sync_event_remote
  ON sync_event(remote_ref);

CREATE INDEX IF NOT EXISTS idx_sync_event_local
  ON sync_event(local_ref);

CREATE INDEX IF NOT EXISTS idx_sync_event_status
  ON sync_event(status);

CREATE INDEX IF NOT EXISTS idx_sync_event_direction
  ON sync_event(direction);

CREATE INDEX IF NOT EXISTS idx_sync_event_occurred_at
  ON sync_event(occurred_at);

CREATE INDEX IF NOT EXISTS idx_sync_event_processed_at
  ON sync_event(processed_at);

-- ------------------------------------------------------------
-- optional view: 最新の issue と内部 task の対応を見やすくする
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_issue_links AS
SELECT
  ic.tracker_connection_id,
  ic.remote_issue_key,
  ic.remote_issue_id,
  ic.title,
  ic.status,
  ic.assignee,
  el.local_ref,
  el.link_role,
  ic.updated_at
FROM issue_cache ic
LEFT JOIN entity_link el
  ON el.remote_ref = (
    'tracker:' ||
    (SELECT tc.tracker_type
       FROM tracker_connection tc
      WHERE tc.id = ic.tracker_connection_id) ||
    ':' || ic.remote_issue_key
  );

COMMIT;
