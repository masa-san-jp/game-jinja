# ゲームへの画像生成組み込み手順

DGX Spark 上のローカル画像生成（Qwen-Image）を、ハッカソンのゲームから使うための手順。
対象: `game-jinja` / `qr-cord-battler-for-ai-game-center`。

## 1. サービスを起動（1 回）

```bash
Agent-Lab/Agent-team/tools/local-image-gen/serve.sh
```

これで ComfyUI 起動 + モデル事前ロード（初回 85 秒をここで消化）+ 画像生成 HTTP
サービス（`:8771`）が立ち上がる。以降の生成は **720px で約 9 秒/枚**。

## 2. ゲームから呼ぶ

エンドポイント（CORS 開放済み、ブラウザから直接叩ける）:

```
POST http://127.0.0.1:8771/generate
body: {"prompt": "...", "width": 720, "height": 720, "seed": 123, "format": "dataurl"|"png"}
  dataurl -> {"image": "data:image/png;base64,...", "seconds": 9.1}
  png     -> image/png のバイト列
GET http://127.0.0.1:8771/health -> {"ok":true,"comfy":true,...}
```

### ブラウザ（神社フロント等）

`imggen.js` をコピーして:

```html
<script src="imggen.js"></script>
<script>
  const url = await generateImage("a torii gate at dawn, anime game art, vivid");
  document.getElementById("bg").src = url;   // data URL を img/背景に
</script>
```

### Python ゲームサーバ（`server.py`）

`imggen_client.py` をコピーして:

```python
from imggen_client import generate_image
generate_image("a glowing omikuji fortune slip, anime game art",
               out_path="web/assets/omikuji.png")
```

## 3. 重要：使いどころ（C2「1 分以内」/ C3「3 分プレイ」を壊さない）

1 枚 ~9 秒なので、**プレイ中のホットパスで呼ばない**。

- ✅ 推奨：タイトル/待機/「祈り」演出中などの**裏で事前生成**して data URL をキャッシュ。
  ゲーム本体（事前生成プール）と同じ「先に作っておく」戦略に揃える。
- ✅ アセット（背景・カード絵・お札・鳥居など）は**ビルド時に一括生成**してリポジトリに同梱してもよい（`imggen_client.py` で PNG 保存）。
- ❌ 非推奨：1 プレイ中に毎フレーム/毎ターン生成。

## 4. 速度の今後

会場回線が遅く軽量モデル（FLUX.2 klein / Z-Image, 数秒台）の DL は保留中。
速い回線で DL 後に profile を差し替えれば、同じエンドポイントのまま高速化できる
（ゲーム側のコード変更不要）。
