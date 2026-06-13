#!/usr/bin/env bash
# aiko-log.sh — append a time-stamped entry to docs/aiko-log.md and push.
#
# All Aiko agents share the SAME working tree (~/dev/game-jinja) and may have
# in-progress edits to other files. To stay isolated from that, logging runs in
# a DEDICATED per-persona clone under ~/.cache/game-jinja-log/<persona> that
# only ever holds aiko-log.md commits — so a dirty main tree never blocks logs.
#
# Usage:
#   scripts/aiko-log.sh <persona> <message...>   # event log
#   scripts/aiko-log.sh maid "issue #3 着手"
#   scripts/aiko-log.sh --heartbeat              # 15-min rotation heartbeat (auto persona)
#
# persona: maid / aiko-dev / aiko-pr / hisyo
# Rotation: slot = floor((now - 13:00 JST)/15min); persona = AGENTS[slot % 4].
set -euo pipefail

REMOTE="https://github.com/masa-san-jp/game-jinja.git"
AGENTS=(maid aiko-dev aiko-pr hisyo)

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

WORK="$HOME/.cache/game-jinja-log/$persona"
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

  if [[ "$heartbeat" == 1 ]]; then
    last="$(git log -1 --format='%s' 2>/dev/null || true)"
    message="🫀 稼働中（直近: ${last}）"
  fi
  entry="- \`${ts}\` **[${persona}]** ${message}"

  printf '%s\n' "$entry" >> docs/aiko-log.md
  git add docs/aiko-log.md
  git commit -q -m "log(${persona}): ${message}" || { echo "nothing to commit" >&2; exit 0; }

  if git push -q origin main 2>/dev/null; then
    echo "logged: $entry"
    exit 0
  fi
  sleep 1
done

echo "failed to log after retries: ${entry:-}" >&2
exit 1
