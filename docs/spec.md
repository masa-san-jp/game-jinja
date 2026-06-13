# 設計仕様書 — AIゲームセンター「ゲーム神社」

DGX Spark ハッカソン 2026-06-13 / 本書が実装の SSOT（Single Source of Truth）。
実装はここに書かれた内容のみを行う。仕様変更は本書を更新してから着手する。

> 前提の確認（マサさん用・1行で訂正可）：
> 「AIゲームセンター」= 来場者が **ゲーム神社で祈ってAIゲームを授かり、その場で遊ぶ** 一連の体験全体。
> 「ゲーム神社」= その中の生成儀式（要素選択→祈り→神託生成）。生成済みゲームは「ゲームセンター（賽銭箱の奥の遊技場）」に並んで誰でも遊べる。
> この枠組みが違う場合はここだけ直してください。

---

## 1. 目的とゴール

- **デモのゴール**：来場者が要素を選んで「祈る」と、DGX Spark 上のローカル LLM がその場で遊べる HTML ゲームを生成し、すぐ遊べる。生成されたゲームはセンターに蓄積され、他の来場者も遊べる。
- **見せ場**：プロンプト＝「祈り」、AI生成＝「神託」という演出で、生成AIの体験を「授かりもの」に昇華する。
- **非ゴール**（今回スコープ外）：ユーザー認証、課金、永続クラウド保存、複雑な3D、マルチプレイ同時対戦。

## 2. 体験フロー（ユーザー視点）

1. トップ（拝殿）：「ゲーム神社」に参拝。`参拝する` で開始。
2. 要素選択（おみくじ）：遊びの要素を **最大7つ** 選ぶ（concept.md の要素リスト）。
3. 祈り：`あなたのゲームを出します。祈りなさい。` と表示 → 祈りの言葉（短文）を入力。
4. 神託生成（待ち演出）：祈り＋選択要素を brief に変換 → 生成エンジンが game-spec とゲームを生成（数十秒〜）。待機中は「神託を授かっています…」の演出。
5. 授与：生成された `index.html` ゲームをその場で全画面プレイ。タイトル・操作・スコアを表示。
6. 奉納：遊んだゲームは「ゲームセンター」一覧に追加され、他の来場者も遊べる。

## 3. システム構成

```
[ブラウザ: 神社フロント]
   │ ① 要素+祈り を POST /api/pray
   ▼
[神社サーバ (Python http.server 拡張 / cockpit ベース)]
   │ ② brief 文字列に整形
   ▼
[生成エンジン game_team.py]  ← agent-game-team（既存・SSOT は当該 README）
   │ ③ designer→builder→runner→orchestrator ループ
   │    (ollama: gpt-oss:20b / gpt-oss:120b @ DGX Spark)
   ▼
[games/<ts>-<slug>/index.html + game-spec.md + bus.jsonl]
   │ ④ 生成完了を神社サーバが検知
   ▼
[ブラウザ: 授与画面でプレイ] ──→ [ゲームセンター一覧に追加]
```

- 生成エンジンは **新規実装しない**。既存 `agent-game-team`（Agent-Lab の `Agent-team/tools/agent-game-team`）をこのリポに取り込んで利用する。本書の §6 で取り込み方法を定義。
- ollama は DGX Spark 上で稼働。神社サーバから `OLLAMA_URL` で接続。

## 4. コンポーネント仕様

### 4.1 神社フロント（`web/index.html` 単一ファイル想定）
- 画面状態：`shrine`（拝殿）/ `select`（要素選択）/ `pray`（祈り入力）/ `oracle`（生成待ち）/ `play`（プレイ）/ `center`（一覧）。
- 要素選択：concept.md のリストをチップ表示。選択は最大7つ、超過時は選べない。
- 祈り入力：1行テキスト（最大120字）。空でも可（要素のみで生成）。
- 生成待ち：`POST /api/pray` 後、`GET /api/status/<job_id>` をポーリング。完了で `play` へ。
- プレイ：生成 `index.html` を `<iframe>` で全画面表示。
- 神社らしいトーン（鳥居・賽銭・神託）。世界観は神社、ただしUIは指で完結。

### 4.2 神社サーバ（`server.py`・既存 cockpit/server.py を拡張）
- `POST /api/pray` : body `{elements: string[], prayer: string}` → brief 整形 → 生成ジョブ起動（非同期）→ `{job_id}` を返す。
- `GET /api/status/<job_id>` : `{state: "running"|"done"|"error", game_path?, title?}`。
- `GET /api/games` : 生成済みゲーム一覧 `[{id, title, path, created_at}]`。
- `GET /games/<id>/index.html` : 生成ゲーム本体を配信。
- 同時祈り：当面は **直列実行**（キュー）。DGX Spark の VRAM 次第で並列度を上げる（§7）。

### 4.3 brief 整形（祈り → エンジン入力）
- 入力：`elements`（最大7）＋ `prayer`（任意短文）。
- 出力：`game_team.py` の brief 文字列。テンプレ例：
  ```
  次の遊びの要素を組み合わせた、小さく確実に遊べる1画面ゲームを作る:
  要素: <elements をカンマ区切り>
  祈り(テーマ): <prayer>
  制約: 単一HTML・素のJS・1プレイ短時間・スコアまたは勝敗あり・スマホ操作可。
  ```
- 整形は神社サーバ内の純関数（テスト対象・§8 T3）。

### 4.4 ゲームセンター（一覧・`center` 画面）
- `GET /api/games` の結果をカード表示（タイトル＋遊ぶボタン）。
- 新しい順。タイトルは game-spec の `## title` 由来。

## 5. データ / ファイル構成（このリポ）

```
game-jinja/
├── README.MD
├── docs/
│   ├── concept.md        体験コンセプト（既存・上位の意図）
│   ├── spec.md           本書（実装SSOT）
│   └── aiko-log.md       全アイコ共有作業ログ
├── web/
│   └── index.html        神社フロント（単一ファイル）
├── server.py             神社サーバ（API + 静的配信）
├── engine/               生成エンジン（agent-game-team 取り込み）
│   ├── game_team.py
│   └── ...
├── games/                生成ゲーム（gitignore・成果物は揮発で可）
└── scripts/aiko-log.sh   共有ログ（既存）
```

## 6. エンジン取り込み方針

- `agent-game-team` を `engine/` にコピー（clean copy・履歴なし）。`games/` `state/` は gitignore。
- 神社サーバはサブプロセスまたは関数呼び出しで `game_team.run(brief, max_turns)` 相当を起動。
- ollama 接続は `OLLAMA_URL`（DGX Spark のアドレス）を環境変数で渡す。
- ※ エンジンの内部仕様（designer/builder/runner/orchestrator）は変更しない。神社側は **brief を渡し、生成物パスを受け取る** だけの薄い結合にする。

## 7. 非機能・制約

- 生成時間：1ゲーム 数十秒〜数分（モデル・turn 数依存）。`--max-turns` は 3〜5 で開始。
- 同時実行：MVP は直列キュー。DGX Spark の VRAM が許せば 20b を並列。
- 失敗時：エンジンが完成宣言に至らない場合も、最後の `index.html` を「授与」して遊べる状態にする（神託は必ず降りる）。
- オフライン前提（会場ネット不安定でもローカル ollama で完結）。

## 8. 受け入れ条件（テスト・完成ゲート）

- **T1**: トップで `参拝する` → 要素選択画面に遷移する。
- **T2**: 要素を7つ選ぶと8つ目が選べない（上限が効く）。
- **T3**: brief 整形関数が `elements`＋`prayer` から所定テンプレ文字列を生成する（純関数の単体テスト）。
- **T4**: `POST /api/pray` が job_id を返し、`GET /api/status` が最終的に `done` と game_path を返す（ollama スタブ可）。
- **T5**: 授与画面で生成 `index.html` が iframe 表示され、操作で状態が動く（実機 ollama でE2E 1本）。
- **T6**: `GET /api/games` が生成済みゲームを新しい順で返し、センター画面に並ぶ。

MVP 完成 = T1〜T5 が通り、実機で「要素選択→祈り→生成→プレイ」が1周する。T6 は nice-to-have（時間が余れば）。

## 9. ハッカソン作業分担（提案・確定はマサさん）

- **aiko-dev**：server.py（API・brief整形・エンジン結合）、エンジン取り込み、テスト。
- **builder 役（人/別アイコ）**：web/index.html（神社UI・世界観）。
- **生成エンジン**：agent-game-team（既存・無改造で利用）。
- **演出/コピー（aiko-pr）**：神託・祈りの文言、鳥居/賽銭ビジュアル方針。
- **進行/段取り（hisyo）**：17:00 までのマイルストーン管理。

## 10. マイルストーン（〜17:00 JST）

1. （〜15:00）本書確定＋エンジン取り込み＋server.py の API 骨組み（スタブで T1〜T4）。
2. （〜16:00）web/index.html で神社UI、実機 ollama で生成1本通す（T5）。
3. （〜16:45）演出・コピー反映、センター一覧（T6）、デモ通し練習。
4. （17:00）デモ。

---

### 改訂履歴
- v0.1 (14:1x JST, aiko-dev) 初版。concept.md と agent-game-team エンジンを接続する実装SSOTとして起草。
