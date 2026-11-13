#!/usr/bin/env bash
# APK-01 复现入口（R2 静态断言；真机部分见 README.md）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 真机验证（R3，未在本机执行；勿对生产发起任何请求）----
# adb install -r LZJ-Chat-1.11.2.apk
# adb shell am start -a android.intent.action.VIEW -d "https://chat.lzj2012.top/"
# # chrome://inspect → Console:
# #   document.cookie    # 出现 "chq=" => 会话 Cookie 已非 HttpOnly（APK-01 成立）
