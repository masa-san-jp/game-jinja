#!/usr/bin/env python3
"""ゲーム神社 — 神社サーバ。

体験フロー(spec §2):
  タイトル → 2択質問×3 → 祈り → 授与(その場でライブ生成) → プレイ → 結果

API (spec §5.2):
  GET  /                      web/index.html
  GET  /web/<path>           静的ファイル
  POST /api/pray             body {answers:[a|b,...], prayer?} -> {job_id}
  GET  /api/status/<job_id>  -> {state, game_id?, title?, elapsed?, error?}
  GET  /games/<game_id>/index.html  生成ゲーム本体
  GET  /api/questions        2択質問の定義（フロントが描画に使う）
  GET  /api/games            授かったゲーム一覧（センター用）

生成は genfast.generate をバックグラウンドスレッドで実行。
時間予算超過/失敗時は同型フォールバック(§6.4)。

Env: PORT (default 8770), GEN_BUDGET_S (default 55), 他は genfast.py 参照。
"""
import json
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import genfast

BASE = Path(__file__).resolve().parent
WEB = BASE / "web"
GAMES = BASE / "games"
PORT = int(os.environ.get("PORT", "8770"))
GEN_BUDGET_S = float(os.environ.get("GEN_BUDGET_S", "55"))

# 2択質問。各問が「ゲーム仕様の1軸」を決め、答えに従って仕様が定まる(spec §3)。
# answer は "a"(左) / "b"(右)。各選択肢は label(表示) と spec(brief へ注入する仕様片) を持つ。
QUESTIONS = [
    {"id": "aim",
     "a": {"label": "高得点を狙う", "spec": "ねらい: 高得点を狙うスコアアタック"},
     "b": {"label": "速さを競う", "spec": "ねらい: クリア速度を競うタイムアタック"}},
    {"id": "move",
     "a": {"label": "攻めて壊す", "spec": "動き: 攻めて壊すデストラクション(壊す快感が主役)"},
     "b": {"label": "避けて生き残る", "spec": "動き: 避けて生き残るサバイバル"}},
    {"id": "tempo",
     "a": {"label": "高速でめまぐるしい", "spec": "テンポ: 高速でめまぐるしい反射神経系"},
     "b": {"label": "一手ずつ考える", "spec": "テンポ: 一手ずつ考える思考系"}},
    {"id": "tension",
     "a": {"label": "敵がどんどん増える", "spec": "緊張の源: 敵やブロックが増え続ける蓄積プレッシャー"},
     "b": {"label": "時間・手数に追われる", "spec": "緊張の源: 制限時間や手数の制約に追われるペナルティ"}},
    {"id": "release",
     "a": {"label": "一掃してスカッと", "spec": "快感の瞬間: 一掃・連鎖でまとめて片づく解放感"},
     "b": {"label": "ギリギリ回避の安堵", "spec": "快感の瞬間: ギリギリで切り抜ける安堵"}},
    {"id": "ramp",
     "a": {"label": "どんどん加速する", "spec": "難化: 時間とともにどんどん加速していく"},
     "b": {"label": "どんどん増える", "spec": "難化: 時間とともにどんどん物量が増えていく"}},
]

# job_id -> {state, game_id?, title?, elapsed?, error?}
JOBS = {}
JOBS_LOCK = threading.Lock()


def now_id():
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + os.urandom(2).hex()


def type_key(answers):
    """2択の答え列 -> 決定的な型キー（例 'a-b-a'）。テスト対象 T3。"""
    if len(answers) != len(QUESTIONS):
        raise ValueError("answers length mismatch")
    norm = []
    for ans in answers:
        a = str(ans).strip().lower()
        if a not in ("a", "b"):
            raise ValueError(f"invalid answer: {ans}")
        norm.append(a)
    return "-".join(norm)


def answers_to_specs(answers):
    """答え列 -> 仕様フラグメント列（brief 用）。各問の選択肢の spec を集める。"""
    out = []
    for q, ans in zip(QUESTIONS, answers):
        opt = q["a"] if str(ans).lower() == "a" else q["b"]
        out.append(opt["spec"])
    return out


def public_questions():
    """フロント表示用に label だけ返す。"""
    return [{"id": q["id"], "a": q["a"]["label"], "b": q["b"]["label"]} for q in QUESTIONS]


def _fallback_game(key):
    """同型の既存ゲームを優先で 1 本返す。無ければ直近の任意ゲーム（§6.4・デモを止めない）。"""
    type_dir = GAMES / key
    if type_dir.is_dir():
        cands = sorted([d for d in type_dir.iterdir() if (d / "index.html").exists()], reverse=True)
        if cands:
            return f"{key}/{cands[0].name}"
    # フォールバック: 全ゲームから最新
    allg = sorted([p.parent for p in GAMES.glob("*/*/index.html")],
                  key=lambda d: d.name, reverse=True)
    return f"{allg[0].parent.name}/{allg[0].name}" if allg else None


def _save_game(key, html, spec, title):
    gid = now_id()
    d = GAMES / key / gid
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")
    (d / "game-spec.md").write_text(spec or "", encoding="utf-8")
    (d / "meta.json").write_text(
        json.dumps({"title": title, "key": key, "created_at": datetime.now().isoformat()},
                   ensure_ascii=False), encoding="utf-8")
    return f"{key}/{gid}"


def _run_job(job_id, answers, prayer):
    key = type_key(answers)
    brief = genfast.build_brief(answers_to_specs(answers), prayer)
    t0 = time.time()
    try:
        result = genfast.generate(brief)
        if not result["html"].lower().startswith("<!doctype"):
            raise RuntimeError("no valid html produced")
        game_id = _save_game(key, result["html"], result["spec"], result["title"])
        with JOBS_LOCK:
            JOBS[job_id] = {"state": "done", "game_id": game_id,
                            "title": result["title"], "elapsed": round(time.time() - t0, 1),
                            "source": "live"}
    except Exception as e:  # 失敗/超過 → 同型フォールバック
        fb = _fallback_game(key)
        if fb:
            with JOBS_LOCK:
                JOBS[job_id] = {"state": "done", "game_id": fb, "title": "授かりもの",
                                "elapsed": round(time.time() - t0, 1), "source": "fallback"}
        else:
            with JOBS_LOCK:
                JOBS[job_id] = {"state": "error", "error": str(e)[:200],
                                "elapsed": round(time.time() - t0, 1)}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass  # quiet

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return self._serve_file(WEB / "index.html", "text/html")
        if path == "/api/questions":
            return self._send(200, {"questions": public_questions()})
        if path == "/api/games":
            return self._send(200, {"games": self._list_games()})
        if path.startswith("/api/status/"):
            job_id = path[len("/api/status/"):]
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            return self._send(200, job) if job else self._send(404, {"error": "unknown job"})
        if path.startswith("/games/"):
            rel = path[len("/games/"):]
            return self._serve_file(GAMES / rel, "text/html")
        if path.startswith("/web/"):
            return self._serve_file(WEB / path[len("/web/"):], None)
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/pray":
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            answers = body.get("answers", [])
            type_key(answers)  # validate -> ValueError if bad
        except (ValueError, json.JSONDecodeError) as e:
            return self._send(400, {"error": str(e)[:200]})
        job_id = now_id()
        with JOBS_LOCK:
            JOBS[job_id] = {"state": "running"}
        threading.Thread(target=_run_job, args=(job_id, answers, body.get("prayer", "")),
                         daemon=True).start()
        return self._send(200, {"job_id": job_id})

    def _serve_file(self, fpath, ctype):
        fpath = fpath.resolve()
        if not str(fpath).startswith((str(WEB), str(GAMES))) or not fpath.is_file():
            return self._send(404, {"error": "not found"})
        ext = fpath.suffix.lower()
        ctype = ctype or {".html": "text/html", ".js": "text/javascript",
                          ".css": "text/css", ".png": "image/png",
                          ".json": "application/json"}.get(ext, "application/octet-stream")
        self._send(200, fpath.read_bytes(), f"{ctype}; charset=utf-8")

    def _list_games(self):
        out = []
        if not GAMES.is_dir():
            return out
        for meta in GAMES.glob("*/*/meta.json"):
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
                m["id"] = f"{meta.parent.parent.name}/{meta.parent.name}"
                out.append(m)
            except Exception:
                continue
        out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return out


def main():
    GAMES.mkdir(exist_ok=True)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"ゲーム神社 server on http://0.0.0.0:{PORT}  (ollama={genfast.OLLAMA})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
