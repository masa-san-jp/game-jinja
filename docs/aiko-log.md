# アイコ作業ログ — ゲーム神社（DGX Spark ハッカソン 2026-06-13）

全アイコ（maid / aiko-dev / aiko-pr / hisyo）の稼働を **15 分刻みのハートビート**で記録する。
基準は本日 **13:00 JST**。15 分ごとにスロットが進み、担当アイコがローテーションする。

## ローテーション

スロット番号 = `floor((現在時刻 − 13:00 JST) / 15分)`。担当は番号 mod 4 で決まる:

| 番号 mod 4 | 担当 |
|---|---|
| 0 | maid |
| 1 | aiko-dev |
| 2 | aiko-pr |
| 3 | hisyo |

例: 13:00→maid / 13:15→aiko-dev / 13:30→aiko-pr / 13:45→hisyo / 14:00→maid …

## 記法

- **ハートビート**（15 分ごと・自動）: `- HH:MM JST **[persona]** 🫀 稼働中（…）`
- **イベント**（着手・完了・ブロッカー・引き継ぎ・随時）: `- HH:MM JST **[persona]** 内容`
- 末尾に追記のみ。上書き禁止。時刻は JST。
- 追記は必ず `docs/aiko-log.sh` 経由（並行 push でも壊れない）。
  - ハートビート: `docs/aiko-log.sh --heartbeat`（担当はスロット時刻から自動判定）
  - イベント: `docs/aiko-log.sh <persona> "<メッセージ>"`

---

## ログ

- `13:00 JST` **[maid]** 🫀 稼働中（backfill）— ハッカソン準備
- `13:15 JST` **[aiko-dev]** 🫀 稼働中（backfill）— キックオフ。masa が全エージェント協力を宣言（13:21）
- `13:30 JST` **[aiko-pr]** 🫀 稼働中（backfill）
- `13:45 JST` **[hisyo]** 🫀 稼働中（backfill）— repo game-jinja セットアップ
- `14:00 JST` **[maid]** 🫀 稼働中（backfill）— repo クローン確認・concept.md 読了
- `14:02 JST` **[maid]** aiko-log.md を新規作成。記法を定義。repo はクローン済み・最新（bb835b2）、README と docs/concept.md 読了。イシュー着手の合図待ち。
- `14:04 JST` **[maid]** aiko-log.sh + game-jinja-log スキル整備完了。全アイコ ~/dev/game-jinja/docs/aiko-log.sh で追記可
- `14:16 JST` **[aiko-dev]** AIゲームセンター設計仕様書 docs/spec.md の起草に着手。agent-game-team(生成エンジン)のI/O確認済み。神社UI→brief→エンジン→playable game→センター展示 の構成で書く
- `14:18 JST` **[aiko-dev]** docs/spec.md v0.1 push完了(57deecd)。AIゲームセンター=神社で祈りAIゲームを授かり遊ぶ体験全体、と定義。受け入れT1-T6・分担・17時マイルストーン記載。エンジンはagent-game-team無改造でengine/に取り込む方針。マサさん確認待ち→OKならserver.py骨組み着手
- `14:24 JST` **[aiko-dev]** spec v0.2 push。マサさん指定の制約反映: 操作=矢印+Z+C/生成1分以内/プレイ3分以内。生成は事前プール基本(1分担保)+ライブは演出。2択は3問8型案。GO待ち→server.py骨組み着手
- `14:28 JST` **[codex]** aiko-log 関連を docs 配下へ統合。追記ツールを docs/aiko-log.sh に移動し、docs/spec.md の構成表も更新。
- `14:33 JST` **[aiko-pr]** 🫀 稼働中（直近: fix: isolate aiko-log in dedicated per-persona clone so a dirty shared tree never blocks logging）
- `14:35 JST` **[aiko-dev]** 実機生成計測完了→spec付録A(32c6e55)。20b単独フルHTML=56s, 120b設計700tok=85s, 両モデル切替はこの開発PCのメモリでOOM(500)。1分達成はGX10前提。構成案=120b発想~300tok+20b実装1パス(テストループ無し)+両モデルkeep_alive常駐+streaming。GX10のollamaエンドポイント要取得→本番計測
- `14:36 JST` **[aiko-dev]** 着手宣言: server.py（2択答え→型キー→ライブ生成→授与API）＋ genfast.py（120b発想/20b実装1パスの高速生成・1分構成）＋ engine/取り込み を aiko-dev が担当。web/index.htmlは別アイコ歓迎、API I/Fはspec §5.2準拠で繋ぐ
