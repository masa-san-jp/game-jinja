#!/usr/bin/env bash
# aiko-log.sh — append a time-stamped entry to docs/aiko-log.md and push.
# Repo-agnostic: detects its own repo from `git remote`, so the SAME script
# works in any repo it is dropped into (game-jinja / qr-cord-battler / ...).
#
# All Aiko agents may share a working tree with in-progress edits to other
# files. To stay isolated from that, logging runs in a DEDICATED clone under
# ~/.cache/aiko-log/<repo>/<persona> that only holds aiko-log.md commits — so a
# dirty main tree never blocks logs. Concurrent pushes are absorbed by retry.
#
# Usage:
#   docs/aiko-log.sh <persona> <message...>   # event log
#   docs/aiko-log.sh maid "issue #3 着手"
#   docs/aiko-log.sh --heartbeat              # 15-min rotation heartbeat (auto persona)
#
# persona: maid / aiko-dev / aiko-pr / hisyo
# Rotation: slot = floor((now - 13:00 JST)/15min); persona = AGENTS[slot % 4].
set -euo pipefail

AGENTS=(maid aiko-dev aiko-pr hisyo)

# --- detect this script's repo (works from main tree or any clone) ---
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF_REPO="$(git -C "$SELF_DIR" rev-parse --show-toplevel)"
REMOTE="$(git -C "$SELF_REPO" remote get-url origin)"
REPO_NAME="$(basename "$REMOTE" .git)"

if [[ "${1:-}" == "--heartbeat" ]]; then
  base=$(TZ='Asia/Tokyo' date -d 'today 13:00' +%s)
  now=$(date +%s)
  slot=$(( (now - base) / 900 ))
  (( slot < 0 )) && slot=0
  persona="${AGENTS[slot % 4]}"
  heartbeat=1
elif [[ $# -lt 2 ]]; then
  echo "usage: $0 <persona> <message...>  |  $0 --heartbeat" >&2
  exit 1
else
  persona="$1"; shift
  message="$*"
  heartbeat=0
fi

WORK="$HOME/.cache/aiko-log/$REPO_NAME/$persona"
if [[ ! -d "$WORK/.git" ]]; then
  mkdir -p "$(dirname "$WORK")"
  git clone -q "$REMOTE" "$WORK"
fi
cd "$WORK"

ts="$(TZ='Asia/Tokyo' date '+%H:%M JST')"

# Retry loop: reset to latest origin/main, append, commit, push.
for attempt in 1 2 3 4 5; do
  git fetch -q origin main
  git reset -q --hard origin/main   # safe: this clone only holds log commits

  if [[ ! -f docs/aiko-log.md ]]; then
    mkdir -p docs
    printf '# アイコ作業ログ — %s\n\n全アイコの稼働を記録する。追記は docs/aiko-log.sh 経由。\n\n## ログ\n\n' "$REPO_NAME" > docs/aiko-log.md
  fi

  if [[ "$heartbeat" == 1 ]]; then
    last="$(git log -1 --format='%s' 2>/dev/null || true)"
    message="🫀 稼働中（直近: ${last}）"
  fi
  entry="- \`${ts}\` **[${persona}]** ${message}"

  printf '%s\n' "$entry" >> docs/aiko-log.md
  git add docs/aiko-log.md
  git commit -q -m "log(${persona}): ${message}" || { echo "nothing to commit" >&2; exit 0; }

  if git push -q origin main 2>/dev/null; then
    echo "logged [$REPO_NAME]: $entry"
    exit 0
  fi
  sleep 1
done

echo "failed to log after retries: ${entry:-}" >&2
exit 1
