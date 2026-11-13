#!/bin/bash
export DISPLAY=:99
export HOME=/data2/browser/home
export LANG=zh_CN.UTF-8
export LANGUAGE=zh_CN:zh
mkdir -p "$HOME/Downloads"
pkill -f "Xvfb :99" 2>/dev/null; sleep 1
Xvfb :99 -screen 0 1366x900x24 -nolisten tcp &
sleep 2
openbox &
x11vnc -display :99 -localhost -rfbport 5900 -nopw -forever -shared -quiet -bg
websockify --web=/usr/share/novnc 127.0.0.1:3010 localhost:5900 &
sleep 1
exec microsoft-edge --lang=zh-CN --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --user-data-dir="$HOME/.config/microsoft-edge" --no-first-run --no-default-browser-check \
  --start-maximized --window-size=1366,900 about:blank
