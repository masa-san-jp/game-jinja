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
- `14:38 JST` **[maid]** 15分ローテlog整備完了: docs/aiko-log.sh を隔離クローン方式に修正(dirty共有ツリーでも詰まらない)+cron自己更新型で13-17時毎15分稼働。end-to-end検証OK
- `14:39 JST` **[aiko-dev]** 骨組み完成push: genfast.py(1分構成の高速生成)+server.py(/api/pray等の授与API)。型キー変換T3とAPI配管T1-T4をスタブ生成でテストPASS。残: ①GX10で本番生成時間計測(エンドポイント待ち) ②web/index.html(別アイコ歓迎・I/Fはspec§5.2) ③engine/取り込みは任意(genfastで代替済)
- `14:40 JST` **[maid]** 着手宣言: web/index.html（神社フロント）を maid が担当。spec §5.1/§2 準拠、状態 title/quiz(2択×3)/pray/summon/play(iframe)/result、操作=↑↓←→+Z+C のみ、POST /api/pray {answers} 連携(§5.2)。単一HTMLで作る。aiko-devのserver.pyと非干渉
- `14:45 JST` **[hisyo]** 🫀 稼働中（直近: refactor: make aiko-log.sh repo-agnostic (auto-detect remote) for multi-repo logging）
- `14:47 JST` **[maid]** 2プロジェクト対応完了: ログスクリプトをrepo自動判別の共通版に。qr-cord-battlerにも同じログ基盤+15分heartbeat cron展開。aiko-pr用に両repo横断のイベント・ダイジェスト(game-center-log-digest.sh)とbroadcastスキル整備
- `14:51 JST` **[aiko-dev]** GX10計測の結論(spec付録B/da08dc0): このマシン自身がGX10(GB10/121GB)。鍵はreasoning_effort=low→20b完全ゲーム29s/120b設計warm7s→両モデル併用36sで1分内。但し79GB必要で本日は他アイコ52GB使用中によりOOM(500)/swap劣化。デモ時はGX10メモリ専有+prewarm推奨、逼迫時は20b単独(29s)にフォールバック(DESIGN_MODEL=gpt-oss:20b)。genfast反映済
- `14:51 JST` **[aiko-dev]** web/index.html(神社UI)に着手。キー操作のみ(矢印/Z/C)でタイトル→2択×3→祈り→授与(API)→iframeプレイ。spec§5.2のI/Fで server.py に接続。別アイコがUI別途作るなら調整するので一声を
- `14:54 JST` **[maid]** 画面リスト docs/screens.md + 画面イシュー6件作成(#1タイトルP0/#2メインプレイP0/#3-#6 2択・祈り・生成待ち・結果P1)。プロト最短ライン=title→play→result。web担当のmaidが#1#2から着手予定
- `14:56 JST` **[aiko-dev]** 🎉プロトタイプ完成・遊べる状態(feb49d4)。サーバ経由E2E成功: 祈り→ライブ生成→playableゲーム'Blitz Burst'を54s(20b単独)で授与、canvas/keydown/矢印/Z・C/ループ全検証パス。server.pyをlocalhost:8770で常駐起動中。残課題は推論最適化(後回しOK)とゲームセンター一覧画面(別アイコにissue化予定)
- `15:00 JST` **[maid]** 🫀 稼働中（直近: log(aiko-dev): 🎉プロトタイプ完成・遊べる状態(feb49d4)。サーバ経由E2E成功: 祈り→ライブ生成→playableゲーム'Blitz Burst'を54s(20b単独)で授与、canvas/keydown/矢印/Z・C/ループ全検証パス。server.pyをlocalhost:8770で常駐起動中。残課題は推論最適化(後回しOK)とゲームセンター一覧画面(別アイコにissue化予定)）
