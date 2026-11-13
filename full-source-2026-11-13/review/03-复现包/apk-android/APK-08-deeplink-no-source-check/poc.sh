#!/usr/bin/env bash
# APK-08 复现入口（R2 静态断言；R3 需真机 adb，见 README.md）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 运行时验证（R3，未在本机执行）----
# adb install -r LZJ-Chat-1.11.2.apk
# adb shell am start -a android.intent.action.VIEW -d "lzjapp://approve"
# adb shell am start -a android.intent.action.VIEW -d "lzjapp://chat"
# 期望（修复前）：APP 被外部拉起并切到“批准”页 => APK-08 成立
