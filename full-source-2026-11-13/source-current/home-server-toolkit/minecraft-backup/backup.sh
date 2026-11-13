#!/usr/bin/env bash
set -uo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
DEST="$BASE/backups"; KEEP=7
mkdir -p "$DEST"
STAMP=$(date -u +%Y%m%d-%H%M%S)
if systemctl --user is-active --quiet minecraft; then
  timeout 5 bash -c "echo 'save-all flush' > '$BASE/console.in'" 2>/dev/null || true
  sleep 4
fi
TARGETS=""
for d in world world_nether world_the_end plugins; do [ -e "$BASE/$d" ] && TARGETS="$TARGETS $d"; done
[ -f "$BASE/server.properties" ] && TARGETS="$TARGETS server.properties"
[ -f "$BASE/ops.json" ] && TARGETS="$TARGETS ops.json"
[ -f "$BASE/whitelist.json" ] && TARGETS="$TARGETS whitelist.json"
OUT="$DEST/world-$STAMP.tar.gz"
tar czf "$OUT" -C "$BASE" $TARGETS 2>/dev/null
ls -1t "$DEST"/world-*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | xargs -r rm -f
echo "备份完成: $OUT ($(du -h "$OUT" | cut -f1))"
