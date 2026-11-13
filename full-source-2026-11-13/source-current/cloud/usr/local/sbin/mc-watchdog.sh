#!/bin/bash
# 云端 MC 看护 (2026-10-07)
# 由心跳驱动的状态机(state, 由 failover.sh 依心跳写成)决定"要不要恢复云端 MC",
# 取代 systemd 的 Restart (已设为 no), 不再由 systemd"检测到挂了就重启"。
# 规则(写死):
#   - 只在 state==CLOUD 时动作
#   - 冷却: 距上次尝试 < COOLDOWN 秒 -> 本轮不试
#   - 每次尝试都写一行到 failover.log (带 UTC 时间戳), 并记入 mc-restart.log 用于计数
#   - 硬放弃: 窗口 WINDOW 秒内尝试达到 MAXTRY 次 -> 写 mc-restart-giveup, 之后永不自动重启
#             人工确认后恢复: failover.sh resume-mc
set -o pipefail
BASE="$MC_BASE"; if [ -z "$BASE" ]; then BASE=/root/failover; fi
STATE_FILE="$MC_STATE_FILE"; if [ -z "$STATE_FILE" ]; then STATE_FILE="$BASE/state"; fi
LOG_FILE="$MC_LOG_FILE"; if [ -z "$LOG_FILE" ]; then LOG_FILE="$BASE/failover.log"; fi
RLOG="$MC_RESTART_LOG"; if [ -z "$RLOG" ]; then RLOG="$BASE/mc-restart.log"; fi
GIVEUP="$MC_RESTART_GIVEUP"; if [ -z "$GIVEUP" ]; then GIVEUP="$BASE/mc-restart-giveup"; fi
WINDOW="$MC_RESTART_WINDOW"; if [ -z "$WINDOW" ]; then WINDOW=600; fi
MAXTRY="$MC_RESTART_MAX"; if [ -z "$MAXTRY" ]; then MAXTRY=10; fi
COOLDOWN="$MC_RESTART_COOLDOWN"; if [ -z "$COOLDOWN" ]; then COOLDOWN=60; fi
DRY="$MC_DRY_RUN"; if [ -z "$DRY" ]; then DRY=0; fi
mkdir -p "$BASE"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_FILE"; tail -n 800 "$LOG_FILE" > "$LOG_FILE.t" && mv "$LOG_FILE.t" "$LOG_FILE"; }

state=$(cat "$STATE_FILE" 2>/dev/null) || state=HOME
if [ "$state" != "CLOUD" ]; then exit 0; fi   # 常态: 静默跳过, 不刷日志
if [ -f "$GIVEUP" ]; then echo "MC看护: 已硬放弃, 不再尝试 (人工恢复: failover.sh resume-mc)"; exit 0; fi
st=$(systemctl is-active mc 2>/dev/null) || true
case "$st" in active|activating|reloading) echo "MC看护: MC 正在运行 ($st), 无需动作"; exit 0;; esac

now=$(date +%s)
if [ -f "$RLOG" ]; then awk -v cut=$((now - WINDOW)) '$1+0 >= cut' "$RLOG" > "$RLOG.t" 2>/dev/null && mv "$RLOG.t" "$RLOG"; fi
cnt=0
if [ -f "$RLOG" ]; then cnt=$(wc -l < "$RLOG" 2>/dev/null) || cnt=0; fi
case "$cnt" in ''|*[!0-9]*) cnt=0;; esac
last=0
if [ -f "$RLOG" ]; then last=$(tail -1 "$RLOG" 2>/dev/null | awk '{print $1+0}') || last=0; fi
case "$last" in ''|*[!0-9]*) last=0;; esac

if [ "$cnt" -ge "$MAXTRY" ]; then
  { echo "时间: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "窗口 $WINDOW 秒内已尝试重启 $cnt 次, 达到上限 $MAXTRY"
    echo "判定: 硬放弃自动重启。多半是内存被反复打爆(被入侵/挂爬虫?) -> 先排查或考虑换服务器。"
    echo "恢复: failover.sh resume-mc   (或 rm -f $GIVEUP)"
  } > "$GIVEUP"
  log "!!! MC看护: 窗口 $WINDOW 秒内尝试 $cnt 次 >= 上限 $MAXTRY -> 硬放弃自动重启 (已写 $GIVEUP)"
  echo "MC看护: 已硬放弃 (窗口内 $cnt 次)"; exit 0
fi
if [ "$last" -gt 0 ] && [ $((now - last)) -lt "$COOLDOWN" ]; then
  echo "MC看护: 冷却中 (距上次 $((now - last)) 秒 < $COOLDOWN 秒), 本轮不试"; exit 0
fi
echo "$now" >> "$RLOG"
log "MC看护: 尝试重启云端 MC (窗口内第 $((cnt+1))/$MAXTRY 次, 当前状态=$st)"
if [ "$DRY" = "1" ]; then echo "MC看护: DRY-RUN 本应执行: systemctl start mc"; exit 0; fi
sync; echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true
if systemctl start mc; then log "MC看护: 已发出 start mc"; else log "MC看护: start mc 返回非零 (下一轮视情况再试)"; fi
