#!/bin/bash
set -u
# 等待 apt/dpkg 锁释放，最长 20 分钟
for i in $(seq 1 240); do
  fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break
  sleep 5
done
command -v chromium >/dev/null || { echo "chromium missing"; exit 1; }
mkdir -p /data2/browser/home /data2/browser-downloads
ln -sfn /data2/browser-downloads /data2/browser/home/Downloads
cat > /usr/local/sbin/browser-kiosk.sh <<'SH'
#!/bin/bash
export DISPLAY=:99
export HOME=/data2/browser/home
mkdir -p "$HOME/Downloads"
pkill -f "Xvfb :99" 2>/dev/null; sleep 1
Xvfb :99 -screen 0 1366x900x24 -nolisten tcp &
sleep 2
openbox &
x11vnc -display :99 -localhost -rfbport 5900 -nopw -forever -shared -quiet -bg
websockify --web=/usr/share/novnc 127.0.0.1:3010 localhost:5900 &
sleep 1
exec chromium --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --user-data-dir="$HOME/.config/chromium" --no-first-run --no-default-browser-check \
  --start-maximized --window-size=1366,900 about:blank
SH
chmod 755 /usr/local/sbin/browser-kiosk.sh
cat > /etc/systemd/system/browser-kiosk.service <<'UNIT'
[Unit]
Description=Cloud browser (Xvfb + Chromium + noVNC)
After=network.target
[Service]
Type=simple
ExecStart=/usr/local/sbin/browser-kiosk.sh
Restart=always
RestartSec=5
MemoryMax=1024M
MemoryHigh=900M
OOMScoreAdjust=800
KillMode=control-group
[Install]
WantedBy=multi-user.target
UNIT
cat > /usr/local/sbin/browser-oom-guard.sh <<'SH'
#!/bin/bash
THRESH=${THRESH:-350}
STATE=/run/browser-oom-guard.count
LOG=/var/log/browser-oom-guard.log
avail=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
if ! systemctl is-active --quiet browser-kiosk; then echo 0 > "$STATE"; exit 0; fi
if [ "$avail" -lt "$THRESH" ]; then
  n=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STATE"
  if [ "$n" -ge 2 ]; then
    echo "$(date -Is) WARN avail=${avail}MiB, stopping browser-kiosk" >> "$LOG"
    systemctl stop browser-kiosk >> "$LOG" 2>&1
    echo 0 > "$STATE"
  fi
else
  echo 0 > "$STATE"
fi
SH
chmod 755 /usr/local/sbin/browser-oom-guard.sh
systemctl daemon-reload
systemctl enable --now browser-kiosk
sleep 8
systemctl is-active browser-kiosk
ss -tln | grep -E ":3010|:5900" || echo NO_PORTS
