#!/usr/bin/env bash
# APK-05 复现入口（R2 静态断言；R3 需真机 adb，见 README.md）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 运行时验证（R3，未在本机执行）----
# adb install -r LZJ-Chat-1.11.2.apk
# # 先在 APP 内登录一次（保证本地有令牌）
# adb shell am broadcast -n top.lzj2012.toolbox/.BootReceiver \
#     -a top.lzj2012.toolbox.EVIL --receiver-include-background
# adb logcat -d | grep -iE "ForegroundServiceStartNotAllowed|AndroidRuntime"
# # 期望（修复前，Android 12+）：FATAL EXCEPTION；修复后：广播被忽略
