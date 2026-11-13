#!/usr/bin/env bash
# APK-03 复现入口（R1 静态断言；R3 真机/服务端验证见 README.md）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 真机/服务端验证（R3，未在本机执行）----
# 1) APP 登录 → 网页端「设备管理」出现该设备
# 2) APP 点“退出” → 刷新「设备管理」：
#    修复后：该设备消失；现状：仍在（APK-03 成立）
# 3) 切“聊天” tab：现状仍为登录态（chq 未清理）
