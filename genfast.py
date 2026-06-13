#!/usr/bin/env python3
"""genfast — 1 分以内のライブ・ゲーム生成（ゲーム神社）。

その場で考える(=ライブ生成)を主軸に、spec §6 の高速パイプラインで作る:
  1. 設計: gpt-oss:120b に「短い game-spec」を作らせる（発想だけ・出力を絞る）
  2. 実装: gpt-oss:20b が単一 HTML を 1 パスで書く（テスト修正ループは回さない）
  3. 構文: node --check で JS 構文のみ確認（無ければスキップ）

両モデルは keep_alive で常駐させ、コールド読込を避ける。
時間予算を超えたら呼び出し側がフォールバックする(§6.4)。

Env:
  OLLAMA_URL    default http://localhost:11434   (本番は GX10 のアドレス)
  DESIGN_MODEL  default gpt-oss:120b
  BUILD_MODEL   default gpt-oss:20b
"""
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DESIGN_MODEL = os.environ.get("DESIGN_MODEL", "gpt-oss:120b")
BUILD_MODEL = os.environ.get("BUILD_MODEL", "gpt-oss:20b")
KEEP_ALIVE = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
# gpt-oss は reasoning モデル。effort=low で思考トークンを削り 1 分以内に収める(GX10実測:
# 20b 完全なゲーム=29s, 120b 設計=warm約7s)。num_predict は思考+本文を賄える大きさが必要。
REASONING_EFFORT = os.environ.get("REASONING_EFFORT", "low")

# 全ゲームに必須の制約 (C1/C3)。brief に必ず注入する。
CONSTRAINTS = (
    "操作は矢印キー(↑↓←→)と Z と C のみ。マウス・テキスト入力は使わない。"
    "1 プレイは 3 分以内に必ず終わる（制限時間 or 明確なクリア/ゲームオーバー）。"
    "終了時に結果画面（スコア/クリア/タイムアップ）を出し、Z で再挑戦・C でタイトルへ。"
    "単一 HTML・素の JavaScript・1 画面・外部ライブラリ禁止。"
)

# 見た目の世界観を統一（リッチに見せる安全策）。画像不要・canvas 描画で実現。
VISUAL_STYLE = (
    "見た目はネオン・ベクター(ワイヤーフレーム)調で統一する: "
    "真っ黒な背景、発光する細い線と幾何形状、ctx.shadowBlur によるグロー、"
    "シアン/マゼンタ/イエローのネオン配色、薄いグリッドやスキャンライン。"
    "画像ファイルは使わず canvas 描画のみで表現する。"
)

# 面白さの条件（最重要）。退屈なゲームを防ぐため設計に必ず効かせる。
FUN_PRINCIPLES = (
    "【面白さの条件・必ず満たす】"
    "(1) 説明不要で、見た瞬間に遊び方が分かる。"
    "(2) 後ろから見ているだけでも楽しい（動きが派手・状況が一目で分かる・派手な演出）。"
    "(3) 3 分以内に必ず決着する。"
    "(4) 次のイディオムを最低 1 つ、強く効かせる— "
    "タイムアタック / スコアアタック / デストラクション(壊す快感) / スピード(加速) / ペナルティ(制約・蓄積)。"
    "(5) 『緊張の蓄積と解放』のループを作る。テトリスの本質＝積み上がること自体がペナルティ(蓄積)で、"
    "列が消える瞬間に緊張が解放される。これと同型の、溜まる→弾ける リズムを必ず入れる。"
    "(6) 時間とともにジワジワ難しくする（加速・増殖・制約強化）。単調な作業ゲーにしない。"
)

# ゲーム仕様は質問の答え(=各軸の選択)を合成して決まる。軸の定義は server.py の QUESTIONS 側。
# build_brief は選ばれた仕様フラグメント(各軸 1 行)を受け取って brief を組む。

DESIGN_SYS = (
    "あなたは敏腕ゲームデザイナー。与えられたアーキタイプから、その場で小さく確実に遊べて"
    "**ちゃんと面白い** 1 画面ゲームの核を **短く** 設計する。長文禁止。"
    "退屈な作業ゲーは絶対に作らない。緊張の蓄積と解放のリズムを核に据える。"
    "出力フォーマット（Markdown・各 1〜2 行）:\n"
    "## title  … 短い英語のゲーム名\n"
    "## core   … 何をするゲームか・面白さの核（どのイディオムで、何が溜まり何が弾けるか）\n"
    "## tension … 緊張がどう蓄積し、どの瞬間に解放されるか\n"
    "## rules  … 勝敗/スコア/終了条件・どう難化するか\n"
    "## controls … 矢印/Z/C に何を割り当てるか\n"
    "前置き・説明・コードは書かない。"
)

BUILD_SYS = (
    "あなたは腕利きゲームプログラマー。game-spec を満たす、単一ファイルで動く"
    "**手触りの良い** HTML5 ゲームを書く。"
    "壊れる・消える・加速する瞬間に派手な視覚フィードバック（パーティクル/画面シェイク/フラッシュ/色変化）"
    "を必ず入れ、後ろから見ても楽しくする。スコアと残り時間/残機を画面に大きく出す。"
    "時間経過で必ず難しくする（加速・増殖）。説明文なしで遊べるUIにする。"
    "入力は必ず addEventListener('keydown', ...) で矢印キー(↑↓←→)と Z と C を処理する。"
    "requestAnimationFrame でゲームループを回す。スコアと結果画面を必ず実装する。"
    "コードを途中で省略したり『…』『以下省略』等で省かない。最後まで完全に書く。"
    "出力は **完全な index.html のみ**（<!DOCTYPE html> から </html> まで・閉じタグ必須）。"
    "canvas + 素の JavaScript、外部ライブラリ禁止、1 ファイル完結。"
    "コードブロックや説明で囲まない、HTML だけを出力する。"
)


def _chat(model, system, user, num_predict):
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "reasoning_effort": REASONING_EFFORT,
        "options": {"num_predict": num_predict, "temperature": 0.7},
    }
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        # gpt-oss は content(本文) と thinking(推論) を返す。本文のみ使う。
        return json.load(r).get("message", {}).get("content", "").strip()


def prewarm():
    """両モデルを常駐させる(コールド読込をデモ前に済ませる)。"""
    for m in (DESIGN_MODEL, BUILD_MODEL):
        try:
            _chat(m, "warmup", "ok", 8)
        except Exception:
            pass


def _extract_html(text):
    m = re.search(r"<!DOCTYPE html>.*?</html>", text, re.S | re.I)
    if m:
        return m.group(0)
    m = re.search(r"```(?:html)?\s*(.*?)```", text, re.S)
    return m.group(1).strip() if m else text.strip()


def _extract_title(spec):
    m = re.search(r"##\s*title\s*\n+\s*(.+)", spec)
    return m.group(1).strip().strip("*# ") if m else "Game"


def quality_issues(html):
    """遊べないゲームを弾く最低ライン。問題のリストを返す（空なら合格）。"""
    g = html.lower()
    issues = []
    if not g.startswith("<!doctype"):
        issues.append("no-doctype")
    if "</html>" not in g:
        issues.append("truncated")               # 途中で切れた
    if "addeventlistener" not in g and "onkeydown" not in g:
        issues.append("no-input")                 # キー入力処理が無い＝操作不能
    if "requestanimationframe" not in g and "setinterval" not in g:
        issues.append("no-loop")                  # ゲームループが無い
    if len(html) < 2500:
        issues.append("too-small")                # 中身が薄い
    return issues


def _check_js(html):
    """node があれば JS 構文だけ確認。無ければ skip。"""
    js = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", html, re.S))
    if not js.strip():
        return "no-js"
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
            path = f.name
        p = subprocess.run(["node", "--check", path], capture_output=True, text=True, timeout=20)
        os.unlink(path)
        return "ok" if p.returncode == 0 else f"error:{p.stderr.strip()[:160]}"
    except FileNotFoundError:
        return "skip"


def build_brief(spec_axes, prayer=""):
    """選ばれた仕様フラグメント(各軸1行)を合成して brief を組む。
    spec_axes: ["ねらい: ...", "動き: ...", ...] の形の文字列リスト。"""
    lines = ["次の指定に従って、小さく確実に遊べて『ちゃんと面白い』1 画面ゲームをその場で作る。"]
    lines += [" ・" + a for a in spec_axes if a]
    if prayer:
        lines.append("祈り(テーマ): " + prayer)
    lines.append(FUN_PRINCIPLES)
    lines.append("見た目: " + VISUAL_STYLE)
    lines.append("制約: " + CONSTRAINTS)
    return "\n".join(lines)


def generate(brief, design_tokens=1000, build_tokens=4000, max_build=3):
    """ライブ生成。品質ゲートに通るまで build を最大 max_build 回まで作り直す。
    dict を返す: {title, html, spec, t_design, t_build, syntax, issues, attempts, elapsed}."""
    t0 = time.time()
    t = time.time()
    spec = _chat(DESIGN_MODEL, DESIGN_SYS, brief + "\n短い game-spec を出力。", design_tokens)
    t_design = time.time() - t

    user = f"game-spec:\n{spec}\n\n上記を満たす **完全に動く** index.html を出力。途中で省略しない。"
    html, issues, attempts = "", ["init"], 0
    t = time.time()
    while issues and attempts < max_build:
        attempts += 1
        html = _extract_html(_chat(BUILD_MODEL, BUILD_SYS, user, build_tokens))
        issues = quality_issues(html)
        if issues:
            # 何が欠けているかを具体的に指摘して作り直させる
            user = (f"game-spec:\n{spec}\n\n前回の出力に問題: {', '.join(issues)}。"
                    "操作(矢印/Z/C)を addEventListener('keydown') で実装し、"
                    "requestAnimationFrame のゲームループ、スコア/結果画面、難化を必ず入れ、"
                    "<!DOCTYPE html> から </html> まで省略せず完全に出力する。")
    t_build = time.time() - t

    return {
        "title": _extract_title(spec),
        "html": html,
        "spec": spec,
        "t_design": round(t_design, 1),
        "t_build": round(t_build, 1),
        "syntax": _check_js(html),
        "issues": issues,
        "attempts": attempts,
        "elapsed": round(time.time() - t0, 1),
    }


if __name__ == "__main__":
    import sys
    sample = build_brief([
        "ねらい: 高得点を狙うスコアアタック",
        "動き: 攻めて壊すデストラクション",
        "テンポ: 高速でめまぐるしい",
        "緊張の源: 敵が増え続ける(蓄積)",
        "快感の瞬間: 一掃・連鎖でまとめてスカッと",
        "難化: どんどん加速していく",
    ])
    b = sys.argv[1] if len(sys.argv) > 1 else sample
    r = generate(b)
    print(f"title={r['title']}  design={r['t_design']}s build={r['t_build']}s "
          f"total={r['elapsed']}s syntax={r['syntax']} bytes={len(r['html'])}")
