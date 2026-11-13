# APK-07 修复建议（含完整修订版 build.sh）

## 1. 逐项修复

### 1.1 签名口令 —— `build.sh:12-14,41`（必然失败点）

只生成一个口令文件，`--ks-pass` 与 `--key-pass` 都用它（keystore 生成时 keypass 就是 storepass）：

```diff
-  python3 -c "import secrets;print(secrets.token_urlsafe(24),end='')" > "$KEY/keystore.pass"
+  python3 -c "import secrets;print(secrets.token_urlsafe(24),end='')" > "$KEY/keystore.pass"
   chmod 600 "$KEY/keystore.pass"
   keytool -genkeypair -keystore "$KEY/lzj-release.jks" -alias lzj \
     -keyalg RSA -keysize 2048 -validity 10950 \
     -storepass:file "$KEY/keystore.pass" -keypass:file "$KEY/keystore.pass" \
     -dname "CN=LZJ Toolbox, OU=Personal, O=LZJ, L=Home, ST=Home, C=CN"
@@ sign
-  --ks-pass "file:$KEY/keystore.pass" --key-pass "file:$KEY/key.pass"
+  --ks-pass "file:$KEY/keystore.pass" --key-pass "file:$KEY/keystore.pass"
```

**迁移风险**：`keystore.pass` 是唯一口令，必须与 `lzj-release.jks` 一起备份（口令丢失 = 无法再
用同一签名密钥发布更新）。若历史上已存在 `key.pass`，先确认其内容与 storepass 一致再使用，
否则改用 package 结构更简单的 PKCS12 并统一口令。

### 1.2 版本号 —— `build.sh:22` vs `AndroidManifest.xml:4`

```diff
-  --version-code 2 --version-name 1.11.2
+  --version-code 3 --version-name 1.11.2
```

或直接删除 `--version-code`/`--version-name`，让清单成为唯一事实来源；发布脚本应从
`AndroidManifest.xml` 读取版本号并做一致性断言（见 1.6 修订版）。

**迁移风险**：versionCode 必须单调递增；已发布 3，下一次发布必须 ≥4（而不是把脚本改回 2）。
若历史上安装过 versionCode=2 的构建，系统会拒绝“降级安装”（`INSTALL_FAILED_VERSION_DOWNGRADE`）。

### 1.3 assets 目录 —— `build.sh:22`

```diff
-  -A "$SRC/assets"
+  -A "$SRC/assets"
```
并在脚本开头 `mkdir -p "$SRC/assets"`（或确认 `assets/` 已随源码入库）。**不要**直接删除 `-A`，
否则将来加入 assets（如 WebView 本地页、图标）会被静默漏打包。

### 1.4 工具链路径 —— `build.sh:4-5`

```diff
-  BT=$SDK/android-16
-  AJ=$SDK/android-36/android.jar
+  BT=$SDK/build-tools/36.0.0        # 必须是 build-tools 目录（含 aapt2/d8/zipalign/apksigner）
+  AJ=$SDK/platforms/android-34/android.jar
```
aapt2/d8/zipalign/apksigner 均从 build-tools 26+ 才提供；`android-16` 是平台目录语义，
不存在这些工具。`android.jar` 建议与 `targetSdkVersion` 对应（34）而非 36。

### 1.5 pipefail + head —— `build.sh:2,44`

```diff
-  "$BT/apksigner" verify --print-certs "$OUT/LZJ-Chat-1.11.2.apk" | head -6
+  "$BT/apksigner" verify --print-certs "$OUT/LZJ-Chat-1.11.2.apk" > "$OUT/verify.txt"
+  sed -n '1,6p' "$OUT/verify.txt"
```
或写成 `... | head -6 || true`（但更推荐落盘，便于留证）。`head` 在读到 6 行后关闭管道，
apksigner 继续写会收到 SIGPIPE，`pipefail` 下整条流水线返回 141，`set -e` 使构建在**签名成功之后**
整体失败。

### 1.6 资源 —— `splash.xml:9` 与 `make_icon.py`

`make_icon.py` 增加 ic_splash 生成（或在 splash.xml 改引用 `@mipmap/ic_launcher`）：

```diff
 for name,scale in dens:
     d=os.path.join(root,"mipmap-"+name); os.makedirs(d,exist_ok=True)
     ls=int(48*scale); bs=int(108*scale); fs=int(108*scale)
     png(os.path.join(d,"ic_launcher.png"), ls, ls, legacy if ls==192 else down(legacy,192,ls))
+    png(os.path.join(d,"ic_splash.png"), ls, ls, legacy if ls==192 else down(legacy,192,ls))
     ...
```
并把 `root="/home/lzj/apk/src/res"` 改为相对脚本/环境变量：

```diff
-root="/home/lzj/apk/src/res"
+import sys
+root=os.environ.get("APK_RES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "res"))
```

**迁移风险**：新增 PNG 会让 APK 体积增加（每个密度 ~几十 KB，可接受）；若仅改 splash.xml 引用
`@mipmap/ic_launcher`，Android 12+ 启动画布会复用应用图标，视觉差异需 UI 确认。

### 1.7 javac（健壮性）

```diff
-  javac -encoding UTF-8 -source 11 -target 11 -classpath "$AJ" -d "$OUT/classes" \
-    $(find "$SRC/java" "$OUT/gen" -name '*.java')
+  javac -encoding UTF-8 --release 11 -classpath "$AJ" -d "$OUT/classes" \
+    $(find "$SRC/java" "$OUT/gen" -name '*.java')
```
（真正隔离 Android API 需用 `-bootclasspath "$AJ"`；`--release` 至少能防止误用 JDK 新增 API。
JDK 25 对 `-source/-target 11` 会给警告，建议固定构建 JDK 17 LTS。）

## 2. 修订后的完整 build.sh（可直接替换）

```bash
#!/bin/bash
set -euo pipefail
SDK=${ANDROID_HOME:-$HOME/apk/sdk}
BT=$SDK/build-tools/36.0.0
AJ=$SDK/platforms/android-34/android.jar
SRC=${APK_SRC:-$HOME/apk/src}
OUT=$HOME/apk/out
KEY=$HOME/apk/keys
VER_CODE=$(grep -oP 'android:versionCode="\K[0-9]+' "$SRC/AndroidManifest.xml")
VER_NAME=$(grep -oP 'android:versionName="\K[^"]+' "$SRC/AndroidManifest.xml")
APK=$OUT/LZJ-Chat-$VER_NAME.apk

mkdir -p "$KEY" "$SRC/assets"
rm -rf "$OUT"; mkdir -p "$OUT/res" "$OUT/classes" "$OUT/dex" "$OUT/gen"

if [ ! -f "$KEY/lzj-release.jks" ]; then
  python3 -c "import secrets;print(secrets.token_urlsafe(24),end='')" > "$KEY/keystore.pass"
  chmod 600 "$KEY/keystore.pass"
  keytool -genkeypair -keystore "$KEY/lzj-release.jks" -alias lzj \
    -keyalg RSA -keysize 2048 -validity 10950 \
    -storepass:file "$KEY/keystore.pass" -keypass:file "$KEY/keystore.pass" \
    -dname "CN=LZJ Toolbox, OU=Personal, O=LZJ, L=Home, ST=Home, C=CN" >/dev/null 2>&1
fi
chmod 600 "$KEY/lzj-release.jks" "$KEY/keystore.pass"

echo "== compile"
"$BT/aapt2" compile --dir "$SRC/res" -o "$OUT/res/resources.zip"

echo "== link (versionCode=$VER_CODE versionName=$VER_NAME)"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$AJ" --manifest "$SRC/AndroidManifest.xml" \
  -R "$OUT/res/resources.zip" -A "$SRC/assets" --java "$OUT/gen" --auto-add-overlay \
  --min-sdk-version 23 --target-sdk-version 34 \
  --version-code "$VER_CODE" --version-name "$VER_NAME"

echo "== javac"
javac -encoding UTF-8 --release 11 -classpath "$AJ" -d "$OUT/classes" \
  $(find "$SRC/java" "$OUT/gen" -name '*.java')

echo "== d8"
"$BT/d8" --lib "$AJ" --min-api 23 --release --output "$OUT/dex" \
  $(find "$OUT/classes" -name '*.class')

echo "== package"
python3 - "$OUT/base.apk" "$OUT/unsigned.apk" "$OUT/dex/classes.dex" <<'PY'
import sys, shutil, zipfile
base, out, dex = sys.argv[1], sys.argv[2], sys.argv[3]
shutil.copyfile(base, out)
with zipfile.ZipFile(out, 'a', zipfile.ZIP_DEFLATED) as z:
    z.write(dex, 'classes.dex')
PY

echo "== align"
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
"$BT/zipalign" -c -p 4 "$OUT/aligned.apk"

echo "== sign"
"$BT/apksigner" sign --ks "$KEY/lzj-release.jks" --ks-key-alias lzj \
  --ks-pass "file:$KEY/keystore.pass" --key-pass "file:$KEY/keystore.pass" \
  --out "$APK" "$OUT/aligned.apk"

echo "== verify"
"$BT/apksigner" verify --print-certs "$APK" > "$OUT/verify.txt"
sed -n '1,8p' "$OUT/verify.txt"
ls -lh "$APK"
```

## 3. 为什么能堵住复现路径

- 口令文件一致 → 签名步骤不再因 `FileNotFoundException` 中止；
- `--version-code` 由清单派生 → 消除 2/3 冲突，升级矩阵可预期；
- assets 目录显式创建 → aapt2 link 不再失败；
- build-tools/platform 路径正确 → aapt2/d8/apksigner 可执行；
- verify 落盘 + sed → 不再有 SIGPIPE 导致的假失败；
- ic_splash 有生成逻辑 → 资源链接不再缺项；
- 签名密钥可复现、可验证 → 交付物可证明由该源码构建（供应链可追溯）。

## 4. 兼容 / 迁移风险

- 历史 APK 若已用其他 versionCode（2）发布，本次修复后必须用更高的 versionCode（≥4）发布，
  否则已安装用户无法覆盖升级。
- 若历史签名密钥非 `lzj-release.jks`，换钥会导致已装用户必须卸载重装；
  发布前用 `apksigner verify --print-certs` 比对旧 APK 证书指纹。
- 建议把 `keystore.pass` 与 `lzj-release.jks` 放入受控的密码管理器/CI secret，而非 `$HOME/apk/keys`
  明文目录（当前脚本已 chmod 600，但同机用户仍可读）。
