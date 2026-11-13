# APK-07 复现说明：build.sh 无法产出一致可复现的签名 APK

- **finding**：`APK-07`（P2，配置错误 / 构建）
- **复现级别**：R1（本机用 JDK keytool 实际复跑 keystore 步骤）+ R2（其余静态断言）
- **关联位置**：`apk/build.sh:2,4-5,12-14,22,25,38-44`；
  `apk/src/AndroidManifest.xml:4`；`apk/src/res/drawable/splash.xml:9`；
  `apk/src/tools/make_icon.py:106,113-119`

## 环境要求

- Python 3.8+；JDK 的 `keytool`（本机 JDK 25 可用）。
- **不需要** aapt2/d8/zipalign/apksigner/android.jar：这些只做静态审查（本机确实没有）。
- 不联网、不改 `work/src`（scratch 目录建在 repro 目录内，跑完即删）。

## 一条可复制命令

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-07-build-sh-unreproducible/check.py"
```

## 期望输出（关键行）

```
R1  | keytool 实际执行: exit=0, lzj-release.jks=True, keystore.pass=True, key.pass=False
R1  | 模拟 apksigner --key-pass file:...\key.pass → FileNotFoundError=True
PASS | apksigner 的 --key-pass 指向不存在的 key.pass  [build.sh:41]
PASS | aapt2 link 传入 --version-code 2（与清单 3 不一致）  [build.sh:22]
PASS | 工程中不存在 apk/src/assets → aapt2 link 会因目录不存在失败（高可能）
PASS | BT=$SDK/android-16 被当作 build-tools 目录使用  [build.sh:4]
PASS | apksigner verify | head -6 在 pipefail 下可能 SIGPIPE 使构建失败  [build.sh:44]
PASS | splash.xml 引用 @mipmap/ic_splash  [res/drawable/splash.xml:9]
PASS | make_icon.py 输出目录硬编码 /home/lzj  [tools/make_icon.py:106]
结论: 复现通过
```

判定标准：`R1` 两行出现（keytool exit=0 且 key.pass=False / FileNotFoundError=True）+ 其余断言
全部 PASS → “签名必然失败 + 版本/资源不一致”成立。

## 六个独立问题（按阻塞顺序）

| # | 位置 | 问题 |
|---|---|---|
| 1 | `build.sh:12,14,41` | 只生成 `keystore.pass`，`--key-pass "file:$KEY/key.pass"` 指向从未创建的文件 → apksigner 读取口令失败，构建终止 |
| 2 | `build.sh:22` vs `AndroidManifest.xml:4` | `--version-code 2` 与清单 `versionCode=3` 冲突（aapt2 会写入/覆盖清单值）→ 产物版本矩阵不自洽 |
| 3 | `build.sh:22` | `-A "$SRC/assets"` 但工程无 `assets/` 目录 → aapt2 link 报错（高可能） |
| 4 | `build.sh:4-5` | `BT=$SDK/android-16` 被当 build-tools 用（aapt2/d8/apksigner/zipalign 属 build-tools 26+）；`AJ` 又取 `android-36` 平台 jar |
| 5 | `build.sh:2,44` | `set -euo pipefail` + `apksigner verify ... | head -6` → head 提前退出触发 SIGPIPE(141)，在签名成功后反而让构建失败 |
| 6 | `res/drawable/splash.xml:9` + `tools/make_icon.py:113-119` | 引用 `@mipmap/ic_splash`，生成器不产出该资源；`make_icon.py` 输出目录硬编码 `/home/lzj/apk/src/res` |

（`zipalign` 在签名之前执行，顺序正确，无需改；`javac -source/-target 11` 与 `d8 --min-api 23`
本身兼容，但 javac 未用 `--release`/Android bootclasspath，属构建健壮性问题，见 fix.md。）

## 未执行说明

本机无 aapt2/d8/zipalign/apksigner/android.jar 与 Android SDK，**未实际执行完整构建**；
仅用本机 JDK keytool 实际复跑了 `build.sh:12-14` 的 keystore 生成命令（R1，输出见
`actual-output.txt`），其余为 R2 静态断言。完整构建验证需在装有对应 SDK 的构建机上进行。
按红线要求未联网、未改动 `work/src`。

> 环境残留说明：本目录可能残留 2 个空目录 `_tmp_*`。它们是首次调试时本机沙箱创建后
> 无法删除的临时目录（Windows 文件权限问题，非 finding 一部分，内容为空），可忽略或由
> 打包方跳过。正常的 check.py 使用固定目录 `_kt_scratch` 并在结束时删除。
