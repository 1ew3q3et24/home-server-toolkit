#!/usr/bin/env bash
# APK-06 复现入口（R2 静态断言；R3 需 Android 13+ 真机，见 README.md）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 运行时验证（R3，未在本机执行）----
# adb install -r LZJ-Chat-1.11.2.apk
# adb shell dumpsys package top.lzj2012.toolbox | grep POST_NOTIFICATIONS   # 期望 denied
# # APP 内点“测试通知” → 无系统权限弹窗（APK-06 成立）
