# tracker-bridge 要件定義

## 1. 目的
tracker-bridge は、外部トラッカー（Jira / GitHub Issues / Backlog / Linear など）と、内部の `agent-taskstate` / `memx-core` を接続するための同期ブリッジである。

本システムの目的は、外部チケットを内部作業状態へ安全に写像し、エージェントが扱える形で取り込み・反映できるようにすることにある。

tracker-bridge 自体は知識の正本でも作業状態の正本でもなく、**外部トラッカーとの接続・投影・同期履歴管理**を責務とする。

## 2. 背景
`memx-core` は知識・証拠・要約を扱う記憶基盤であり、`agent-taskstate` は task / decision / open_question / context_bundle など内部作業状態を扱う。

一方、現実の開発運用では Jira や GitHub Issues などの外部トラッカーが存在し、対外的な進捗共有・担当・ステータス管理が必要になる。

しかし、外部トラッカーは内部の思考過程・失敗履歴・仮説・証拠断片を保持する場所としては不十分である。
そのため、外部トラッカーを内部状態の正本にせず、内部状態を壊さずに接続するための専用ブリッジ層が必要となる。

## 3. スコープ
### 3.1 対象
- 外部トラッカーとの接続定義
- 外部 issue / ticket の取得
- 外部 issue と `agent-taskstate.task` の対応付け
- 同期イベントの記録
- 最小限の inbound / outbound 同期

### 3.2 非対象
- `agent-taskstate` の task state 自体の管理
- `memx-core` の evidence / knowledge の保存
- エージェント本体の推論やオーケストレーション
- 外部トラッカーの完全ミラーリング
- 全コメント・全履歴・全添付ファイルの完全再現

## 4. システムの位置づけ
tracker-bridge は以下の位置づけを持つ。

- `memx-core`: 知識・証拠・要約の正本
- `agent-taskstate`: 内部 task / decision / question / run の正本
- `tracker-bridge`: 外部トラッカーとの同期・写像・履歴の正本

外部トラッカーは「外界との窓口」であり、内部作業状態そのものではない。

## 5. ユースケース
### UC-01: 外部 issue 取り込み
- Jira / GitHub Issues 等の issue を取得する
- issue の基本情報をローカルに保持する
- 必要に応じて `agent-taskstate.task` を生成する

### UC-02: 外部 issue と内部 task の対応付け
- 1件の外部 issue に対し、1件以上の内部 task を紐づける
- primary / related / duplicate / blocks などの関係を保持する

### UC-03: ステータス同期
- 外部 issue の status 変更を観測する
- 必要に応じて内部 task の status 更新候補を作る
- 逆に内部 task の完了やレビュー完了を外部 issue に反映する

### UC-04: コメント・要約反映
- 内部で得られた decision / summary を外部 issue 向けの短い報告として投影する
- 外部コメントを内部 evidence または run の材料として利用可能にする

### UC-05: 同期監査
- いつ、どの issue に、どの方向で、何を同期したかを記録する
- 失敗時の再試行や原因調査を可能にする

## 6. 機能要件
### FR-01 接続管理
- 複数の tracker connection を保持できること
- tracker_type, base_url, project/workspace, 認証情報参照先を管理できること

### FR-02 Issue 取得
- 外部 issue を取得し、ローカル cache に保存できること
- 最低限、remote_id, remote_key, title, status, assignee, labels, raw_payload を保持できること

### FR-03 Entity Link
- 外部 issue と内部 `agent-taskstate.task` を対応付けできること
- 1:N および N:N の関係を許容すること
- link_role を持てること

### FR-04 同期イベント記録
- inbound / outbound の同期イベントを履歴として保存できること
- status, payload, error_message, occurred_at, processed_at を持てること

### FR-05 最小 inbound 同期
- 外部 issue の新規作成・更新・ステータス変更を検知できること
- 更新を issue_cache に反映できること

### FR-06 最小 outbound 同期
- 内部 task 完了やレビュー結果を、外部 issue に短い報告として反映できること
- MVP では full sync ではなく、限定的な status / comment 反映でよい

### FR-07 冪等性
- 同じイベントを再処理しても二重登録・二重反映が起きにくいこと
- remote_ref + event fingerprint 等で重複制御できること

### FR-08 障害耐性
- 外部 API 失敗時に sync_event へ failed を記録できること
- 後から再試行可能であること

## 7. 非機能要件
### NFR-01 単純性
MVP では複雑な双方向整合よりも、責務分離と追跡可能性を優先する。

### NFR-02 可観測性
同期の成否、失敗理由、対象 issue、方向をログとDB上で確認可能であること。

### NFR-03 拡張性
Jira 以外の tracker_type を後から追加しやすい構造であること。

### NFR-04 疎結合
`agent-taskstate` / `memx-core` と DB レベルで密結合しないこと。
repo 間参照は typed_ref による論理参照とする。

### NFR-05 セキュリティ
アクセストークン等の秘密情報は DB 平文保持を避け、環境変数または secret store 参照とする。

## 8. データ境界
### tracker-bridge が持つもの
- tracker_connection
- issue_cache
- entity_link
- sync_event

### tracker-bridge が持たないもの
- task の正本
- decision の正本
- evidence / knowledge の正本

### 参照先
- `agent-taskstate:task:*`
- `memx:evidence:*`
- `tracker:jira:PROJ-123`

## 9. MVP 範囲
MVP では以下のみを対象とする。

1. tracker_connection の登録
2. 外部 issue の取得と issue_cache 保存
3. issue と `agent-taskstate.task` の entity_link 作成
4. inbound sync_event 記録
5. outbound の最小反映（status または短文コメントのどちらか一方）

MVP では以下は後回しとする。

- 添付ファイル完全同期
- コメント全文同期
- 双方向リアルタイム同期
- スプリント/ボード/エピック完全対応
- 権限細分化
- 複雑な競合解決

## 10. 成功条件
以下を満たしたとき MVP 完了とする。

- 外部 issue 1件を取得できる
- issue_cache に保存できる
- `agent-taskstate.task` 1件とリンクできる
- inbound sync_event を履歴として残せる
- 内部完了イベントを外部へ 1 回反映できる
- 失敗時に failed 履歴と原因を確認できる

## 11. 今後の拡張候補
- 複数 tracker の同時運用
- webhook ベースのリアルタイム同期
- コメント差分同期
- issue 更新から context_bundle 自動生成
- decision / summary の自動外部投影
- GitHub PR / commit / release 連携
