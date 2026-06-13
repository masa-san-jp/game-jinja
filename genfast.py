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

DESIGN_SYS = (
    "あなたはゲームデザイナー。与えられた『遊びの気配』から、その場で小さく確実に遊べる"
    "1 画面ゲームの核を **短く** 設計する。長文禁止。"
    "出力フォーマット（Markdown・各 1〜2 行）:\n"
    "## title  … 短い英語のゲーム名\n"
    "## core   … 何をするゲームか・面白さの核\n"
    "## rules  … 勝敗/スコア/終了条件\n"
    "## controls … 矢印/Z/C に何を割り当てるか\n"
    "前置き・説明・コードは書かない。"
)

BUILD_SYS = (
    "あなたはゲームプログラマー。game-spec を満たす、単一ファイルで動く HTML5 ゲームを書く。"
    "出力は **完全な index.html のみ**（<!DOCTYPE html> から </html> まで）。"
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


def build_brief(elements, prayer=""):
    """2択の答え(=遊びの気配のラベル列)と任意の祈りから brief を組む。"""
    lines = [
        "次の『遊びの気配』を組み合わせた、小さく確実に遊べる 1 画面ゲームをその場で作る。",
        "気配: " + "、".join(e for e in elements if e),
    ]
    if prayer:
        lines.append("祈り(テーマ): " + prayer)
    lines.append("制約: " + CONSTRAINTS)
    return "\n".join(lines)


def generate(brief, design_tokens=1000, build_tokens=3500, do_fix=False):
    """ライブ生成。dict を返す: {title, html, spec, t_design, t_build, syntax, elapsed}."""
    t0 = time.time()
    t = time.time()
    spec = _chat(DESIGN_MODEL, DESIGN_SYS, brief + "\n短い game-spec を出力。", design_tokens)
    t_design = time.time() - t

    t = time.time()
    html = _extract_html(_chat(
        BUILD_MODEL, BUILD_SYS,
        f"game-spec:\n{spec}\n\n上記を満たす完全な index.html を出力。", build_tokens))
    t_build = time.time() - t

    syntax = _check_js(html)
    if do_fix and syntax.startswith("error"):
        t = time.time()
        html = _extract_html(_chat(
            BUILD_MODEL, BUILD_SYS,
            f"game-spec:\n{spec}\n現在のindex.html:\n{html[:3000]}\n"
            f"JS構文エラー: {syntax}\n修正した完全な index.html を出力。", build_tokens))
        t_build += time.time() - t
        syntax = _check_js(html)

    return {
        "title": _extract_title(spec),
        "html": html,
        "spec": spec,
        "t_design": round(t_design, 1),
        "t_build": round(t_build, 1),
        "syntax": syntax,
        "elapsed": round(time.time() - t0, 1),
    }


if __name__ == "__main__":
    import sys
    sample = build_brief(["スピード重視", "攻める", "一発勝負(タイムアタック)"], "")
    b = sys.argv[1] if len(sys.argv) > 1 else sample
    r = generate(b)
    print(f"title={r['title']}  design={r['t_design']}s build={r['t_build']}s "
          f"total={r['elapsed']}s syntax={r['syntax']} bytes={len(r['html'])}")
