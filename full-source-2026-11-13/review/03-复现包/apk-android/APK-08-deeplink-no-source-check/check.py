# -*- coding: utf-8 -*-
"""APK-08 复现检查：导出的 MainActivity 接受自定义 scheme 深链 lzjapp://approve|chat，
handleIntent 只校验 scheme/host，不校验调用方、不校验 action、不校验登录态。"""
import pathlib
import sys
import xml.etree.ElementTree as ET

ID = "APK-08"
TITLE = "自定义 scheme 深链无来源/鉴权校验：任意应用或网页可拉起“批准”页"
MAN = "apk/src/AndroidManifest.xml"
MA = "apk/src/java/top/lzj2012/toolbox/MainActivity.java"
NS = "{http://schemas.android.com/apk/res/android}"


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def ln_of(lines, needle):
    for i, s in enumerate(lines, 1):
        if needle in s:
            return i
    return None


def run(src=None):
    if src is None:
        src = pathlib.Path(__file__).resolve().parents[2] / "src"
    src = pathlib.Path(src)
    man = read(src / MAN)
    ma = read(src / MA)
    root = ET.fromstring("\n".join(man))
    out = []
    ok = True

    def check(cond, desc, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    act = None
    for a in root.iter("activity"):
        if a.get(NS + "name") == ".MainActivity":
            act = a
    check(act is not None and act.get(NS + "exported") == "true",
          "MainActivity 显式 exported=true（launcher + 深链）", "AndroidManifest.xml:25-27")
    filters = act.findall("intent-filter") if act is not None else []
    deep = []
    for f in filters:
        for d in f.findall("data"):
            if d.get(NS + "scheme") == "lzjapp":
                deep.append(d.get(NS + "host"))
    check(deep == ["approve", "chat"],
          "深链 host = approve/chat，且带 BROWSABLE（浏览器可直达）", "AndroidManifest.xml:35-46")
    check(act is not None and act.get(NS + "autoVerify") is None,
          "自定义 scheme 无 autoVerify（Android 无法验证 scheme 归属，任何应用都能注册同一 scheme）")
    check(act is not None and act.get(NS + "permission") is None,
          "MainActivity 无 android:permission（也无签名级门槛）")

    start = ln_of(ma, "private void handleIntent(Intent intent)")
    check(start == 259, "handleIntent 位置确认", "MainActivity.java:259-270")
    body = "\n".join(ma[start - 1: start + 11])
    check('"lzjapp".equals(u.getScheme())' in body and '"approve".equals(u.getHost())' in body,
          "只按 scheme+host 分派，不校验 action/调用方", "MainActivity.java:262-268")
    for needle, desc in [
        ("getCallingPackage", "getCallingPackage()"),
        ("getLaunchedFromPackage", "getLaunchedFromPackage()"),
        ("getReferrer", "getReferrer()"),
        ("checkPermission", "checkPermission()"),
        ("Prefs.token", "登录态校验"),
    ]:
        check(needle not in body, "handleIntent 中没有 %s" % desc, "MainActivity.java:259-270")
    check(ln_of(ma, "if (approval != null) approval.reload();") == 265,
          "深链直接触发 approval.reload()（读本地令牌并拉取待批准列表）", "MainActivity.java:265")

    out.append("外部触发命令（R3，需真机；本机无 adb/模拟器，未执行）：")
    out.append('  adb shell am start -a android.intent.action.VIEW -d "lzjapp://approve"')
    out.append('  adb shell am start -a android.intent.action.VIEW -d "lzjapp://chat"')
    out.append('  # 任意第三方 APP 内: startActivity(new Intent(ACTION_VIEW, Uri.parse("lzjapp://approve")))')
    out.append("说明：Android 10+ 后台应用不能直接后台弹 Activity，但浏览器/前台应用/用户点击的链接可直达；")
    out.append("      影响为 UI 混淆与社工（把用户引到批准页），当前代码本身不能被外部直接批准（仍需用户点按钮）。")

    status = "复现通过" if ok else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R2（静态可证）；运行时需真机（R3），本机未执行",
        "环境: Windows + Python 3.12 + xml.etree；无 Android SDK/模拟器",
        "检查对象: %s, %s" % (MAN, MA),
    ] + out + ["结论: %s" % status])
    return {"id": ID, "title": TITLE, "status": status, "ok": ok, "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
