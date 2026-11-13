#!/usr/bin/env bash
# APK-07 复现入口（R1 keytool 子测试 + R2 静态断言；不联网）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 完整构建验证（需装有 Android SDK 的构建机，本机未执行）----
# export ANDROID_HOME=$HOME/apk/sdk
# bash apk/build.sh
# 现状预期失败点（按顺序）：
#   1) aapt2 link: -A "$SRC/assets" 目录不存在
#   2) apksigner sign: --key-pass file:$KEY/key.pass 文件不存在（Failed to read key password）
#   3) 修正签名后：apksigner verify | head -6 在 set -o pipefail 下可能以 141 退出
# 产物校验：$ANDROID_HOME/build-tools/<ver>/aapt2 dump badging out/LZJ-Chat-1.11.2.apk | head -3
#   → 观察 versionCode 是 2 还是 3（与清单 3 不一致）
