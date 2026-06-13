#!/usr/bin/env bash
# Start ComfyUI (if needed) and pre-warm the image model so first real use is fast.
# Call this at startup ("ゲーム立ち上げ時") to pay the ~85s cold load up front;
# afterwards every gen.py call runs on the warm path (~10s for qwen-lightning).
set -euo pipefail

COMFY_DIR="/home/masa/dev/comfyui"
HOST="http://127.0.0.1:8188"
PROFILE="${1:-qwen-lightning}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! curl -s -m 3 "$HOST/system_stats" >/dev/null 2>&1; then
  echo "[serve] starting ComfyUI..."
  cd "$COMFY_DIR"
  nohup .venv/bin/python main.py --listen 127.0.0.1 --port 8188 \
    > /tmp/comfyui.log 2>&1 &
  for i in $(seq 1 120); do
    curl -s -m 2 "$HOST/system_stats" >/dev/null 2>&1 && break
    sleep 1
  done
fi
curl -s -m 3 "$HOST/system_stats" >/dev/null 2>&1 || { echo "[serve] ComfyUI failed to start; see /tmp/comfyui.log" >&2; exit 1; }
echo "[serve] ComfyUI up. warming '$PROFILE' (cold load happens now)..."
"$COMFY_DIR/.venv/bin/python" "$HERE/gen.py" --warmup --profile "$PROFILE"

# Start the HTTP adapter the games call (port 8771), if not already up.
if ! curl -s -m 3 http://127.0.0.1:8771/health >/dev/null 2>&1; then
  echo "[serve] starting image-gen HTTP service on :8771..."
  nohup "$COMFY_DIR/.venv/bin/python" "$HERE/server.py" --port 8771 --profile "$PROFILE" \
    > /tmp/imggen_server.log 2>&1 &
  for i in $(seq 1 20); do
    curl -s -m 2 http://127.0.0.1:8771/health >/dev/null 2>&1 && break
    sleep 1
  done
fi
echo "[serve] ready."
echo "  - games call:  POST http://127.0.0.1:8771/generate  {prompt,width,height,seed,format}"
echo "  - CLI:         $COMFY_DIR/.venv/bin/python $HERE/gen.py \"<prompt>\" --profile $PROFILE"
