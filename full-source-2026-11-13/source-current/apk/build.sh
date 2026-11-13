#!/bin/bash
set -euo pipefail
SDK=$HOME/apk/sdk
BT=$SDK/android-16
AJ=$SDK/android-36/android.jar
SRC=$HOME/apk/src
OUT=$HOME/apk/out
KEY=$HOME/apk/keys
VC=${VC:-4}
VN=${VN:-1.11.3}
HARDENED=${HARDENED:-0}
SUFFIX=""
[ "$HARDENED" = "1" ] && SUFFIX="-hardened"
APK=$OUT/LZJ-Chat-$VN$SUFFIX.apk
rm -rf "$OUT"; mkdir -p "$OUT/res" "$OUT/classes" "$OUT/dex" "$OUT/gen" "$KEY"

if [ ! -f "$KEY/lzj-release.jks" ]; then
  python3 -c "import secrets;print(secrets.token_urlsafe(24),end='')" > "$KEY/keystore.pass"
  chmod 600 "$KEY/keystore.pass"
  keytool -genkeypair -keystore "$KEY/lzj-release.jks" -alias lzj -keyalg RSA -keysize 2048 -validity 10950     -storepass:file "$KEY/keystore.pass" -keypass:file "$KEY/keystore.pass"     -dname "CN=LZJ Toolbox, OU=Personal, O=LZJ, L=Home, ST=Home, C=CN" >/dev/null 2>&1
fi
chmod 600 "$KEY/lzj-release.jks"

# 让 manifest 与本次版本号一致（aapt2 也会写，双保险）
python3 - "$SRC/AndroidManifest.xml" "$VC" "$VN" <<'PY'
import re,sys
p,vc,vn=sys.argv[1],sys.argv[2],sys.argv[3]
s=open(p).read()
s=re.sub(r'android:versionCode="[0-9]+"','android:versionCode="%s"'%vc,s,count=1)
s=re.sub(r'android:versionName="[^"]*"','android:versionName="%s"'%vn,s,count=1)
open(p,'w').write(s)
PY

echo "== compile ($VN / $VC)"
"$BT/aapt2" compile --dir "$SRC/res" -o "$OUT/res/resources.zip"

echo "== link"
"$BT/aapt2" link -o "$OUT/base.apk" -I "$AJ" --manifest "$SRC/AndroidManifest.xml"   -R "$OUT/res/resources.zip" -A "$SRC/assets" --java "$OUT/gen" --auto-add-overlay   --min-sdk-version 23 --target-sdk-version 34 --version-code "$VC" --version-name "$VN"

echo "== javac"
mkdir -p "$SRC/java/top/lzj2012/toolbox"
if [ "$HARDENED" = "1" ]; then HF=true; else HF=false; fi
printf 'package top.lzj2012.toolbox;\npublic final class BuildFlags { public static final boolean HARDENED = %s; }\n' "$HF" > "$SRC/java/top/lzj2012/toolbox/BuildFlags.java"
javac -encoding UTF-8 -source 11 -target 11 -classpath "$AJ" -d "$OUT/classes"   $(find "$SRC/java" "$OUT/gen" -name '*.java')

echo "== d8"
"$BT/d8" --lib "$AJ" --min-api 23 --output "$OUT/dex" $(find "$OUT/classes" -name '*.class')

echo "== package"
python3 - "$OUT/base.apk" "$OUT/unsigned.apk" "$OUT/dex/classes.dex" <<'PY'
import sys, shutil, zipfile
base, out, dex = sys.argv[1], sys.argv[2], sys.argv[3]
shutil.copyfile(base, out)
with zipfile.ZipFile(out, 'a', zipfile.ZIP_DEFLATED) as z:
    z.write(dex, 'classes.dex')
PY
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"

echo "== sign ($APK)"
"$BT/apksigner" sign --ks "$KEY/lzj-release.jks" --ks-key-alias lzj   --ks-pass "file:$KEY/keystore.pass" --key-pass "file:$KEY/key.pass"   --out "$APK" "$OUT/aligned.apk"

echo "== verify"
"$BT/apksigner" verify --print-certs "$APK" | head -6
ls -lh "$APK"
