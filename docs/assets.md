# ゲーム用 画像アセット — game-jinja

「生成ゲームが地味」対策として、ローカル画像生成（ComfyUI / Qwen-Lightning）で事前生成した
リッチな共通アセット。`web/assets/` に同梱、サーバが `/web/assets/<file>` で配信する。
カタログは `web/assets/manifest.json`（機械可読）。

## アセット一覧

| id | 種類 | サイズ | 用途 |
|----|------|--------|------|
| bg_arcade | 背景 | 1024×576 | スピード/アクション系 |
| bg_shrine | 背景 | 1024×576 | 神社テーマ |
| bg_space | 背景 | 1024×576 | 宇宙/シューティング |
| bg_forest | 背景 | 1024×576 | 自然/探索 |
| orb_player | オブジェクト | 512×512 | プレイヤー/自機（発光） |
| gem | オブジェクト | 512×512 | 取得アイテム/得点 |
| star | オブジェクト | 512×512 | ボーナス |
| explosion | オブジェクト | 512×512 | 爆発/ヒット演出 |
| enemy_slime | オブジェクト | 512×512 | 敵/ターゲット |
| coin | オブジェクト | 512×512 | コイン/スコア |

## 使い方（ゲーム HTML から）

```js
// 事前ロード
const bg = new Image(); bg.src = "/web/assets/bg_shrine.png";
const orb = new Image(); orb.src = "/web/assets/orb_player.png";

// 背景を敷く
ctx.drawImage(bg, 0, 0, canvas.width, canvas.height);

// 発光オブジェクトは黒背景なので加算合成で“抜く”
ctx.globalCompositeOperation = "lighter";
ctx.drawImage(orb, x - 32, y - 32, 64, 64);
ctx.globalCompositeOperation = "source-over";
```

- object 系は **黒背景**で生成。`globalCompositeOperation = "lighter"`（加算）で発光体として綺麗に乗る。
- 非発光オブジェクト（coin/gem/slime）は枠付きスプライトとしてそのまま `drawImage` でも可。

## ⚠ 生成 brief との方針衝突（要判断）

現在 `genfast.py` の `VISUAL_STYLE` は **「画像ファイルは使わず canvas 描画のみ」** を明示している
（ネオン・ベクター調で統一する安全策）。このままでは生成ゲームはアセットを使わない。

アセットを効かせるには brief 方針の変更が必要。選択肢:

1. **ハイブリッド（推奨）**: 背景だけ画像、ゲーム本体は今のネオン・ベクター描画を維持。
   背景 1 枚で見栄えが大きく上がり、ベクター描画の信頼性（壊れにくさ）は保つ。
2. 全面アセット化: プレイヤー/敵/アイテムも画像に。リッチだが生成 LLM が壊れたパス参照を出す
   リスクが上がる（要試行）。
3. 現状維持: 画像を使わずベクターのまま。

### ハイブリッド用 brief 追記スニペット（案・aiko-dev 連携）

`build_brief` に以下を 1 行足し、`VISUAL_STYLE` の「画像を使わず」を「背景のみ画像可」に緩める:

```
利用可能な背景画像（任意・1枚だけ背景に使ってよい）: /web/assets/bg_arcade.png, /web/assets/bg_shrine.png,
/web/assets/bg_space.png, /web/assets/bg_forest.png。new Image() で読み、ctx.drawImage(bg,0,0,W,H) で背景に敷く。
ゲーム本体（自機/敵/弾/エフェクト）は引き続き canvas 描画で表現する。
```

生成は `Agent-Lab/.../tools/local-image-gen`（= imggen）を使用。再生成・追加は `scripts/gen-assets`（本リポ同梱の生成スクリプト）参照。
