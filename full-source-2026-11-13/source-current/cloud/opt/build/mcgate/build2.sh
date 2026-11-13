#!/bin/bash
set -euo pipefail
JDK=/opt/build/jdk21
API=/opt/build/paper-api.jar
cd /opt/build/mcgate
echo "--- 源码 ---"; find src -type f
rm -rf out && mkdir -p out
"$JDK/bin/javac" -encoding UTF-8 -cp "$API" -d out $(find src -name "*.java")
cp src/plugin.yml out/
cd out && "$JDK/bin/jar" cf ../McGate-0.1.0.jar . && cd ..
echo "BUILD-OK"; ls -l McGate-0.1.0.jar; "$JDK/bin/jar" tf McGate-0.1.0.jar | head -10