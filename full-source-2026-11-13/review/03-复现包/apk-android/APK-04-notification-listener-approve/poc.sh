#!/usr/bin/env bash
# APK-04 复现入口（R2 静态断言；R3 真机 + 通知监听应用见 README.md）
set -euo pipefail
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
"$PY" "$DIR/check.py"

# ---- 运行时验证（R3，未在本机执行）----
# 1) 安装并登录 APP，服务端制造待批准进服请求
# 2) 安装通知监听测试应用并授予“通知使用权”，在其 onNotificationPosted 中：
#      for (Notification.Action a : sbn.getNotification().actions)
#          if ("允许".contentEquals(a.title)) a.actionIntent.send();
# 3) 期望（修复前）：服务端该请求被批准，用户零感知 => APK-04 成立
