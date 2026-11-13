#!/bin/bash
set -uo pipefail
IN=/data2/openclaw-logs-incoming
REPO=/root/openclaw-logs-repo
LOG=/var/log/openclaw-logs-hub.log
ASKPASS=/root/gh-askpass-openclaw.sh
export GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0
mkdir -p "$REPO/logs" "$REPO/sessions" "$REPO/memory"
log(){ printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; tail -n 300 "$LOG" > "$LOG.t" && mv "$LOG.t" "$LOG"; }
[ -d "$IN" ] || { log "incoming missing"; exit 0; }
rsync -a --delete "$IN/logs/" "$REPO/logs/" || log "rsync logs FAIL"
if [ -d "$IN/sessions" ]; then rsync -a --delete "$IN/sessions/" "$REPO/sessions/" || log "rsync sessions FAIL"; fi
if [ -d "$IN/memory" ]; then rsync -a --delete "$IN/memory/" "$REPO/memory/" || log "rsync memory FAIL"; fi
if [ -f "$IN/meta.json" ]; then cp -f "$IN/meta.json" "$REPO/meta.json"; fi
cd "$REPO" || exit 1

git fetch -q origin 2>>"$LOG" || log "fetch FAIL"
if git rev-parse --verify -q origin/main >/dev/null; then
  if ! git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
    git reset --soft origin/main || log "reset FAIL"
  fi
fi

git add -A
if git diff --cached --quiet; then log "no changes"; exit 0; fi
git commit -q -m "logs $(date -Is)" || { log "commit FAIL"; exit 1; }
if git push -q origin HEAD:main 2>>"$LOG"; then
  R=$(git ls-remote origin HEAD 2>/dev/null | cut -f1)
  L=$(git rev-parse HEAD)
  if [ -n "$R" ] && [ "$R" = "$L" ]; then log "push ok ${L:0:8}"; else log "verify FAIL"; fi
else
  log "push FAIL"
fi
