#!/usr/bin/env bash
# APK-02 复现入口（R1 语义等价模型，不联网）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 真机验证（R3，未在本机执行）----
# 前置：APP 已登录；网页端“设备管理”吊销该设备 / 管理员 reset 改密
# 观察 10 分钟：APP 应弹“登录已过期”并停止 WatchService；若仍在轮询 => APK-02 成立
