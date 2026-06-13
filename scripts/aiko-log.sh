#!/usr/bin/env bash
# aiko-log.sh — append a time-stamped entry to docs/aiko-log.md and push.
# Safe for concurrent use by multiple Aiko agents: rebase + retry on push race.
#
# Usage:
#   scripts/aiko-log.sh <persona> <message...>   # event log
#   scripts/aiko-log.sh maid "issue #3 着手"
#   scripts/aiko-log.sh --heartbeat              # 15-min rotation heartbeat (auto persona)
#
# persona: maid / aiko-dev / aiko-pr / hisyo ...
# Rotation: slot = floor((now - 13:00 JST)/15min); persona = AGENTS[slot % 4].
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/docs/aiko-log.md"
AGENTS=(maid aiko-dev aiko-pr hisyo)

if [[ "${1:-}" == "--heartbeat" ]]; then
  base=$(TZ='Asia/Tokyo' date -d 'today 13:00' +%s)
  now=$(date +%s)
  slot=$(( (now - base) / 900 ))
  (( slot < 0 )) && slot=0
  persona="${AGENTS[slot % 4]}"
  last="$(cd "$REPO_DIR" && git log -1 --format='%s' 2>/dev/null || true)"
  message="🫀 稼働中（直近: ${last}）"
elif [[ $# -lt 2 ]]; then
  echo "usage: $0 <persona> <message...>  |  $0 --heartbeat" >&2
  exit 1
else
  persona="$1"; shift
  message="$*"
fi

ts="$(TZ='Asia/Tokyo' date '+%H:%M JST')"
entry="- \`${ts}\` **[${persona}]** ${message}"

cd "$REPO_DIR"

# Retry loop: rebase onto latest, append, commit, push. Re-sync if push races.
for attempt in 1 2 3 4 5; do
  git fetch -q origin main
  git rebase -q origin/main || { git rebase --abort 2>/dev/null || true; sleep 1; continue; }

  printf '%s\n' "$entry" >> "$LOG_FILE"
  git add docs/aiko-log.md
  git commit -q -m "log(${persona}): ${message}" || { echo "nothing to commit" >&2; exit 0; }

  if git push -q origin main 2>/dev/null; then
    echo "logged: $entry"
    exit 0
  fi

  # Push rejected (another agent pushed first). Undo local commit, retry.
  git reset -q --soft HEAD~1
  git restore --staged docs/aiko-log.md 2>/dev/null || true
  git checkout -- docs/aiko-log.md 2>/dev/null || true
  sleep 1
done

echo "failed to log after retries: $entry" >&2
exit 1
