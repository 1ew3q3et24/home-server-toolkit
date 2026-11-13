#!/bin/bash
# 在云端构建 McGate (javac 直接对着服务端 jar 编译)
set -euo pipefail
JDK=/opt/build/jdk21
SRV=/opt/build/paper-server.jar
cd /opt/build/mcgate || exit 1
rm -rf out && mkdir -p out
"$JDK/bin/javac" -encoding UTF-8 -cp "$SRV" -d out $(find src -name "*.java")
cp src/plugin.yml out/
cd out && "$JDK/bin/jar" cf ../McGate-0.1.0.jar . && cd ..
echo "--- 产物 ---"; ls -l McGate-0.1.0.jar
echo "--- 内容抽查 ---"; "$JDK/bin/jar" tf McGate-0.1.0.jar | head -10