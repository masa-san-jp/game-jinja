#!/usr/bin/env bash
# ゲーム神社 をデモ用に起動する。
# Claude Code(エージェント)を落としてもサーバが生き続けるよう nohup + disown で独立起動する。
#
# 使い方:
#   ./run.sh            # 起動（モデルを温めてから）
#   ./run.sh stop       # 停止
#
# 前提: GX10 の ollama に gpt-oss:20b がある（DESIGN_MODEL を使わない build-only 構成）。
# 別ホストの ollama を使う場合: OLLAMA_URL=http://<host>:11434 ./run.sh
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8770}"
LOG="${LOG:-/tmp/game-jinja-server.log}"

stop() {
  pkill -f "python3 server.py" 2>/dev/null && echo "stopped" || echo "no server running"
}

if [[ "${1:-}" == "stop" ]]; then
  stop; exit 0
fi

# 既存があれば止める
pkill -f "python3 server.py" 2>/dev/null || true

export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-30m}"
# Claude Code から切り離して起動（--prewarm で最初の1本が遅くならないよう温める）
nohup python3 server.py --prewarm > "$LOG" 2>&1 &
disown
echo "ゲーム神社 server started (pid $!)."
echo "  open : http://localhost:${PORT}"
echo "  log  : ${LOG}"
echo "  stop : ./run.sh stop"
