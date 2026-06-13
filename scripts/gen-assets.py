#!/usr/bin/env python3
"""Pre-generate a reusable game-asset pack via the local imggen HTTP service (:8771).

前提: imggen サービス起動済み（Agent-Lab/.../tools/local-image-gen/serve.sh）。
出力: web/assets/*.png + manifest.json。再生成・アセット追加はこの ASSETS を編集。
"""
import json, time, urllib.request, pathlib

ENDPOINT = "http://127.0.0.1:8771/generate"
OUTDIR = pathlib.Path(__file__).resolve().parent.parent / "web" / "assets"
OUTDIR.mkdir(parents=True, exist_ok=True)

BG_STYLE = "anime arcade game background art, vivid saturated colors, high contrast, detailed, no text, no characters, no UI"
OBJ_STYLE = "single game asset, centered, isolated on solid flat pure black background, glossy, vivid, high contrast, no text, no shadow on ground"

# (id, kind, w, h, prompt, use)
ASSETS = [
    ("bg_arcade",  "background", 1024, 576, f"retro neon synthwave arcade, glowing purple and cyan grid, sunset horizon. {BG_STYLE}", "汎用背景（スピード/アクション系）"),
    ("bg_shrine",  "background", 1024, 576, f"japanese shrine at dawn, red torii gate, soft mist, cherry petals, mystical golden light. {BG_STYLE}", "神社テーマ背景"),
    ("bg_space",   "background", 1024, 576, f"deep space starfield with colorful nebula and distant planets, cosmic. {BG_STYLE}", "宇宙/シューティング背景"),
    ("bg_forest",  "background", 1024, 576, f"vibrant fantasy forest clearing, glowing plants, magical bioluminescence. {BG_STYLE}", "自然/探索背景"),
    ("orb_player", "object",     512,  512, f"glowing blue energy orb sphere with bright core. {OBJ_STYLE}", "プレイヤー/自機"),
    ("gem",        "object",     512,  512, f"shiny faceted crystal gem, emerald green, sparkling. {OBJ_STYLE}", "取得アイテム/得点"),
    ("star",       "object",     512,  512, f"golden five-pointed star, glossy, glowing rim. {OBJ_STYLE}", "取得アイテム/ボーナス"),
    ("explosion",  "object",     512,  512, f"vivid orange explosion burst with sparks and smoke. {OBJ_STYLE}", "爆発/ヒット演出"),
    ("enemy_slime","object",     512,  512, f"cute round purple slime monster with big eyes. {OBJ_STYLE}", "敵/ターゲット"),
    ("coin",       "object",     512,  512, f"shiny gold coin with star emblem, metallic. {OBJ_STYLE}", "コイン/スコア"),
]

manifest = {"note": "事前生成アセット。games は /assets/<file> で参照可。object は黒背景=透過扱い(canvas 'lighter' 合成 or 黒キー)。", "assets": []}

for i, (aid, kind, w, h, prompt, use) in enumerate(ASSETS):
    body = json.dumps({"prompt": prompt, "width": w, "height": h, "seed": 1000 + i, "format": "png"}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
    except Exception as e:
        print(f"[FAIL] {aid}: {e}")
        continue
    (OUTDIR / f"{aid}.png").write_bytes(data)
    print(f"[ok] {aid:12s} {len(data)//1024:4d}KB {time.time()-t0:4.1f}s  {w}x{h}")
    manifest["assets"].append({"id": aid, "kind": kind, "file": f"/web/assets/{aid}.png", "w": w, "h": h, "use": use})

(OUTDIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {len(manifest['assets'])} assets + manifest.json to {OUTDIR}")
