# tracker-bridge SQLite 仕様書

## 1. 目的
tracker-bridge は、外部トラッカー（Jira / GitHub Issues / Backlog / Linear など）と内部システム（`agent-taskstate` / `memx-core`）の間に入る同期ブリッジである。

SQLite では以下を保持する。

- 接続先定義
- 外部 issue のローカルキャッシュ
- 内部 task と外部 issue の対応関係
- 同期イベント履歴

本DBは **外部トラッカーとの同期状態のローカル正本**であり、
`agent-taskstate.task` や `memx.evidence` の正本は持たない。

## 2. 前提
### 2.1 DBエンジン
- SQLite 3.39 以上を想定
- JSON は `TEXT` 保存とし、必要に応じて JSON1 関数を使う
- 日時は ISO 8601 UTC 文字列で保存する

### 2.2 ID方針
- 主キー `id` は `TEXT`
- ULID または UUID を利用可能
- 外部参照は typed_ref 文字列で持つ

例:
- `agent-taskstate:task:01HXXXX`
- `memx:evidence:01HYYYY`
- `tracker:jira:PROJ-123`

### 2.3 秘密情報
- API token / secret は DB に保存しない
- DBには secret の参照名のみ保存する

## 3. 責務境界
### tracker-bridge が保持するもの
- tracker_connection
- issue_cache
- entity_link
- sync_event

### tracker-bridge が保持しないもの
- task の内部状態
- decision / open_question
- evidence / knowledge 本体
- 外部 issue の完全履歴

## 4. テーブル一覧
### 4.1 `tracker_connection`
外部トラッカー接続定義。

### 4.2 `issue_cache`
外部 issue の最新観測結果キャッシュ。

### 4.3 `entity_link`
外部 issue と内部 entity の対応表。

### 4.4 `sync_event`
同期イベント履歴。

## 5. DDL
```sql
PRAGMA foreign_keys = ON;

CREATE TABLE tracker_connection (
  id TEXT PRIMARY KEY,
  tracker_type TEXT NOT NULL,         -- jira / github / linear / backlog / redmine
  name TEXT NOT NULL,
  base_url TEXT NOT NULL,
  workspace_key TEXT,
  project_key TEXT,
  secret_ref TEXT,                    -- env key / secret store key
  is_enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT,

  CHECK (tracker_type IN ('jira', 'github', 'linear', 'backlog', 'redmine')),
  CHECK (is_enabled IN (0, 1))
);

CREATE TABLE issue_cache (
  id TEXT PRIMARY KEY,
  tracker_connection_id TEXT NOT NULL,
  remote_issue_id TEXT NOT NULL,      -- provider固有の内部ID
  remote_issue_key TEXT NOT NULL,     -- PROJ-123 / #45 など表示用キー
  title TEXT NOT NULL,
  status TEXT,
  assignee TEXT,
  reporter TEXT,
  labels_json TEXT,
  issue_type TEXT,
  priority TEXT,
  raw_json TEXT NOT NULL,             -- 元レスポンスの最小保持
  last_seen_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,

  FOREIGN KEY (tracker_connection_id) REFERENCES tracker_connection(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX idx_issue_cache_remote
  ON issue_cache(tracker_connection_id, remote_issue_key);

CREATE INDEX idx_issue_cache_status
  ON issue_cache(tracker_connection_id, status);

CREATE INDEX idx_issue_cache_updated
  ON issue_cache(tracker_connection_id, updated_at);

CREATE TABLE entity_link (
  id TEXT PRIMARY KEY,
  local_ref TEXT NOT NULL,            -- agent-taskstate:task:... / memx:artifact:...
  remote_ref TEXT NOT NULL,           -- tracker:jira:PROJ-123
  link_role TEXT NOT NULL,            -- primary / related / duplicate / blocks / caused_by
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  metadata_json TEXT,

  CHECK (link_role IN ('primary', 'related', 'duplicate', 'blocks', 'caused_by'))
);

CREATE UNIQUE INDEX idx_entity_link_pair
  ON entity_link(local_ref, remote_ref, link_role);

CREATE INDEX idx_entity_link_local
  ON entity_link(local_ref);

CREATE INDEX idx_entity_link_remote
  ON entity_link(remote_ref);

CREATE TABLE sync_event (
  id TEXT PRIMARY KEY,
  tracker_connection_id TEXT NOT NULL,
  direction TEXT NOT NULL,            -- inbound / outbound
  remote_ref TEXT NOT NULL,
  local_ref TEXT,                     -- agent-taskstate:task:* など
  event_type TEXT NOT NULL,           -- issue_created / issue_updated / comment_created / status_changed / link_created
  fingerprint TEXT,                   -- 冪等性制御用
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,               -- pending / applied / failed / skipped
  error_message TEXT,
  occurred_at TEXT NOT NULL,
  processed_at TEXT,
  created_at TEXT NOT NULL,

  FOREIGN KEY (tracker_connection_id) REFERENCES tracker_connection(id) ON DELETE CASCADE,

  CHECK (direction IN ('inbound', 'outbound')),
  CHECK (status IN ('pending', 'applied', 'failed', 'skipped'))
);

CREATE UNIQUE INDEX idx_sync_event_fingerprint
  ON sync_event(tracker_connection_id, fingerprint)
  WHERE fingerprint IS NOT NULL;

CREATE INDEX idx_sync_event_remote
  ON sync_event(remote_ref);

CREATE INDEX idx_sync_event_local
  ON sync_event(local_ref);

CREATE INDEX idx_sync_event_status
  ON sync_event(status);

CREATE INDEX idx_sync_event_occurred
  ON sync_event(occurred_at);
```

## 6. 各テーブル仕様
### 6.1 `tracker_connection`
#### 役割
接続先トラッカーの定義を持つ。

#### カラム
- `id`: 内部ID
- `tracker_type`: トラッカー種別
- `name`: 接続名
- `base_url`: API/Workspace の基底URL
- `workspace_key`: ワークスペース識別子
- `project_key`: プロジェクト識別子
- `secret_ref`: 認証情報参照名
- `is_enabled`: 有効/無効
- `metadata_json`: 任意拡張

#### 備考
- 認証トークンは保存しない
- 複数接続を持てる

### 6.2 `issue_cache`
#### 役割
外部 issue の最新状態を保持するローカル投影。

#### カラム
- `remote_issue_id`: provider内部ID
- `remote_issue_key`: 人間向けキー
- `title`, `status`, `assignee`, `reporter`
- `labels_json`: ラベル配列
- `issue_type`, `priority`
- `raw_json`: 元レスポンス最小保存
- `last_seen_at`: 最終取得時刻

#### 備考
- 履歴テーブルではなく「最新キャッシュ」
- 詳細差分は `sync_event` に残す
- `raw_json` は監査・再解釈用

### 6.3 `entity_link`
#### 役割
外部 issue と内部 entity の対応関係を保持する。

#### カラム
- `local_ref`: `agent-taskstate:task:*` を主用途とする
- `remote_ref`: `tracker:jira:PROJ-123` など
- `link_role`: 関係種別

#### 備考
- 1 issue : N task を許容
- 1 task : N issue も許容
- DB外参照なので FK は張らない

### 6.4 `sync_event`
#### 役割
同期イベントの履歴と結果を保持する。

#### カラム
- `direction`: inbound / outbound
- `remote_ref`: 外部参照
- `local_ref`: 内部参照
- `event_type`: イベント種別
- `fingerprint`: 冪等性キー
- `payload_json`: 同期ペイロード
- `status`: pending / applied / failed / skipped
- `error_message`: 失敗理由
- `occurred_at`: 外部イベント発生時刻
- `processed_at`: 内部処理時刻

#### 備考
- 冪等性は `fingerprint` により担保する
- 完全イベントソーシングではなく、同期監査用ログ

## 7. typed_ref 仕様
tracker-bridge では DB をまたぐ参照を typed_ref で統一する。

### 7.1 形式
```text
<domain>:<type>:<id_or_key>
```

### 7.2 例
```text
agent-taskstate:task:01JABCDEF...
memx:evidence:01JXYZ...
tracker:jira:PROJ-123
tracker:github:repo#45
```

### 7.3 用途
- `entity_link.local_ref`
- `entity_link.remote_ref`
- `sync_event.local_ref`
- `sync_event.remote_ref`

## 8. 冪等性ルール
### 8.1 目的
同じ webhook / poll 結果を再処理しても、二重反映を避ける。

### 8.2 方法
`sync_event.fingerprint` を一意制御に使う。

### 8.3 生成例
```text
sha256(
  tracker_connection_id + "|" +
  direction + "|" +
  remote_ref + "|" +
  event_type + "|" +
  provider_event_id_or_updated_at
)
```

### 8.4 挙動
- 既存 fingerprint がある場合は `skipped`
- 新規なら `pending → applied/failed`

## 9. 同期方針
### 9.1 inbound
外部 → 内部

対象:
- issue 作成
- issue 更新
- status 変更
- 必要最小の comment 取得

処理:
1. `issue_cache` を更新
2. 必要なら `entity_link` 作成
3. `sync_event` を追加

### 9.2 outbound
内部 → 外部

対象:
- task 完了報告
- status 更新
- 短文コメント投影

処理:
1. 外部APIへ送信
2. 結果を `sync_event` に記録
3. 必要に応じて `issue_cache` を再取得

## 10. 更新ルール
### 10.1 `issue_cache`
- 同じ `tracker_connection_id + remote_issue_key` が存在すれば UPDATE
- なければ INSERT

### 10.2 `entity_link`
- 同じ `local_ref + remote_ref + link_role` は重複禁止

### 10.3 `sync_event`
- `fingerprint` があれば重複処理を抑制
- `failed` は再試行対象とする

## 11. 代表クエリ例
### 11.1 接続ごとの issue 一覧
```sql
SELECT remote_issue_key, title, status, assignee, updated_at
FROM issue_cache
WHERE tracker_connection_id = ?
ORDER BY updated_at DESC;
```

### 11.2 外部 issue に紐づく内部 task 参照
```sql
SELECT local_ref, link_role
FROM entity_link
WHERE remote_ref = ?;
```

### 11.3 task に紐づく外部 issue 参照
```sql
SELECT remote_ref, link_role
FROM entity_link
WHERE local_ref = ?;
```

### 11.4 失敗同期の確認
```sql
SELECT remote_ref, event_type, error_message, occurred_at
FROM sync_event
WHERE status = 'failed'
ORDER BY occurred_at DESC;
```

### 11.5 未処理イベントの確認
```sql
SELECT id, remote_ref, event_type, occurred_at
FROM sync_event
WHERE status = 'pending'
ORDER BY occurred_at ASC;
```

## 12. MVPの制約
MVP では以下を割り切る。

- コメント全文の完全同期はしない
- 添付ファイル同期はしない
- issue 履歴の完全再現はしない
- ボード / スプリント / エピックの完全表現はしない
- `issue_cache` は最新状態のみ持つ
- 外部と内部の競合解決は単純ルールに留める

## 13. 将来拡張
後で足せるもの:

- `issue_comment_cache`
- `attachment_cache`
- `status_mapping`
- `sync_outbox`
- `webhook_event_raw`
- `remote_user_cache`
- `project_mapping`
- `field_mapping_rule`

## 14. 設計上の判断
この SQLite 仕様では、tracker-bridge を **同期ブリッジ専用** に留めている。

そのため:

- task の現在状態は `agent-taskstate`
- 根拠や証拠は `memx-core`
- 外部 tracker 状態は `tracker-bridge`

という境界が維持される。

これにより、Jira/BTS が内部思考の正本になることを防ぐ。
