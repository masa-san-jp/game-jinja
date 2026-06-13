#!/usr/bin/env python3
"""Tiny local image-gen HTTP service for the hackathon games.

Wraps ComfyUI + Qwen behind ONE simple endpoint so a browser game or a game
server can get an image without speaking ComfyUI's graph protocol.

Endpoints (CORS open for localhost browser games):
  GET  /health
      -> {"ok": true, "comfy": true, "profile": "qwen-lightning"}
  POST /generate   body: {"prompt": str, "width"?: 720, "height"?: 720,
                          "seed"?: int, "format"?: "png"|"dataurl"}
      format "png"     -> image/png bytes (default)
      format "dataurl" -> {"image": "data:image/png;base64,...", "seconds": 9.1}

Run:
  python3 server.py [--port 8771] [--profile qwen-lightning] [--warmup]
Needs ComfyUI up (use serve.sh first, or pass --warmup to load weights here).
"""
import argparse
import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen  # noqa: E402  (local module)

PROFILE = "qwen-lightning"
PORT = 8771


def _comfy_up():
    try:
        gen._get("/system_stats")
        return True
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            self._json(200, {"ok": True, "comfy": _comfy_up(), "profile": PROFILE})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/generate":
            self._json(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._json(400, {"error": f"bad json: {e}"})
            return
        prompt = (req.get("prompt") or "").strip()
        if not prompt:
            self._json(400, {"error": "prompt required"})
            return
        w = int(req.get("width", 720))
        h = int(req.get("height", 720))
        seed = int(req.get("seed", 42))
        fmt = req.get("format", "png")
        try:
            dt, imgs = gen.generate(PROFILE, prompt, w, h, seed)
            data = open(imgs[0], "rb").read()
        except Exception as e:
            self._json(500, {"error": str(e)[:400]})
            return
        if fmt == "dataurl":
            b64 = base64.b64encode(data).decode()
            self._json(200, {"image": "data:image/png;base64," + b64, "seconds": round(dt, 1)})
        else:
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self._cors()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def log_message(self, *a):
        pass  # quiet


def main():
    global PROFILE, PORT
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--profile", default=PROFILE, choices=list(gen.PROFILES))
    ap.add_argument("--warmup", action="store_true")
    args = ap.parse_args()
    PROFILE, PORT = args.profile, args.port
    if args.warmup:
        d, _ = gen.generate(PROFILE, "warmup", 256, 256, 1)
        print(f"[imggen] warmed {PROFILE} in {d:.1f}s", flush=True)
    print(f"[imggen] serving on http://127.0.0.1:{PORT}  profile={PROFILE}  comfy={_comfy_up()}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
