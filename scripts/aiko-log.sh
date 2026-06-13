#!/usr/bin/env bash
# aiko-log.sh — append a time-stamped entry to docs/aiko-log.md and push.
# Safe for concurrent use by multiple Aiko agents: rebase + retry on push race.
#
# Usage:
#   scripts/aiko-log.sh <persona> <message...>
#   scripts/aiko-log.sh maid "issue #3 着手"
#
# persona: maid / aiko-dev / aiko-pr / hisyo ...
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$REPO_DIR/docs/aiko-log.md"

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <persona> <message...>" >&2
  exit 1
fi

persona="$1"; shift
message="$*"
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
