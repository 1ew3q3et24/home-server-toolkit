# APK-08 复现说明：自定义 scheme 深链无来源/鉴权校验

- **finding**：`APK-08`（P3，组件暴露 / 逻辑缺陷）
- **复现级别**：R2（静态可证）+ R3（真机 adb am start / 浏览器链接）
- **关联位置**：`apk/src/AndroidManifest.xml:25-48`；
  `apk/src/java/top/lzj2012/toolbox/MainActivity.java:253-270`

## 环境要求

- 静态断言：Python 3.8+。
- 运行时：Android 真机/模拟器 + `adb`；或任意浏览器/第三方 APP 构造 `lzjapp://` 链接。
- 说明：本 finding 的“危害”是 UI 混淆/社工（把用户引到批准页），当前代码不能被外部直接批准
  （仍需用户点按钮），故定为 P3。

## 一条可复制命令（R2 静态断言）

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-08-deeplink-no-source-check/check.py"
```

## 期望输出（关键行）

```
PASS | MainActivity 显式 exported=true（launcher + 深链）  [AndroidManifest.xml:25-27]
PASS | 深链 host = approve/chat，且带 BROWSABLE（浏览器可直达）  [AndroidManifest.xml:35-46]
PASS | 自定义 scheme 无 autoVerify（Android 无法验证 scheme 归属）
PASS | 只按 scheme+host 分派，不校验 action/调用方  [MainActivity.java:262-268]
PASS | handleIntent 中没有 getCallingPackage() / getLaunchedFromPackage() / getReferrer() / 登录态校验
结论: 复现通过
```

判定标准：全部 PASS → 任何应用/浏览器可用 `lzjapp://approve` 拉起批准页。

## 运行时验证（R3，**未在本机执行**）

```bash
adb install -r LZJ-Chat-1.11.2.apk
adb shell am start -a android.intent.action.VIEW -d "lzjapp://approve"
# 期望：APP 被拉起并切到“批准”tab 且立即拉取待批准列表（用户未主动打开 APP）
# 在任意网页里放 <a href="lzjapp://approve">打开</a>，点击同样生效（BROWSABLE）
```

判定标准：外部命令/外部网页能使 APP 打开“批准”页 → 复现成功。

## 未执行说明

本机无 Android SDK/模拟器/adb，无法安装 APK，故只执行 R2 静态断言（输出见
`actual-output.txt`）；R3 需真机条件。按红线要求未对生产服务端发起请求。
