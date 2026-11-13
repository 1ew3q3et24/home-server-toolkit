# -*- coding: utf-8 -*-
"""APK-06 复现检查：targetSdk=34 但从未请求 POST_NOTIFICATIONS 运行时权限。
Android 13+ 上新装用户 areNotificationsEnabled()==false →
Notifier.showApproval() 在 notify 之前 return → 审批通知全部静默丢失（核心功能失效）。"""
import pathlib
import sys
import xml.etree.ElementTree as ET

ID = "APK-06"
TITLE = "POST_NOTIFICATIONS 只声明不请求：Android 13+ 审批通知静默失效"
MAN = "apk/src/AndroidManifest.xml"
NOT = "apk/src/java/top/lzj2012/toolbox/Notifier.java"
WS = "apk/src/java/top/lzj2012/toolbox/WatchService.java"
JAVA_DIR = "apk/src/java/top/lzj2012/toolbox"
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
    notif = read(src / NOT)
    ws = read(src / WS)
    out = []
    ok = True

    def check(cond, desc, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    root = ET.fromstring("\n".join(man))
    perms = [p.get(NS + "name") for p in root.iter("uses-permission")]
    check("android.permission.POST_NOTIFICATIONS" in perms,
          "清单声明了 POST_NOTIFICATIONS", "AndroidManifest.xml:11")
    sdk = root.find("uses-sdk")
    check(sdk is not None and sdk.get(NS + "targetSdkVersion") == "34",
          "targetSdkVersion=34 → Android 13+ 必须运行时申请该权限", "AndroidManifest.xml:7")

    java_text = ""
    files = sorted((src / JAVA_DIR).glob("*.java"))
    for f in files:
        java_text += f.read_text(encoding="utf-8", errors="replace") + "\n"
    check("requestPermissions" not in java_text,
          "全部 Java 源码中没有 requestPermissions 调用（%d 个文件）" % len(files))
    check("POST_NOTIFICATIONS" not in java_text,
          "全部 Java 源码中没有引用 POST_NOTIFICATIONS（无 onRequestPermissionsResult 处理）")

    check(ln_of(notif, "if (!enabled(c)) return;") == 55,
          "showApproval 在 notify 之前因 enabled()==false 直接 return（通知静默丢失）",
          "Notifier.java:55")
    check(ln_of(notif, "if (Build.VERSION.SDK_INT >= 24 && !nm.areNotificationsEnabled()) return false;") == 30,
          "enabled() 用 areNotificationsEnabled()；Android 13+ 未授权时恒为 false", "Notifier.java:30")
    check(ln_of(ws, "notified.add(p.id);") == 69,
          "WatchService 在调用 showApproval 之前就把 id 标记为已通知 → 用户事后授权也不会补发",
          "WatchService.java:68-71")

    out.append("平台依据：Android 13(API 33)+ 新装应用通知默认关闭；未调用 requestPermissions 时，")
    out.append("          areNotificationsEnabled()==false，notify() 的调用被前置 return 短路。")
    out.append("真机验证（R3，未执行）：")
    out.append("  adb shell pm revoke top.lzj2012.toolbox android.permission.POST_NOTIFICATIONS")
    out.append("  adb shell dumpsys notification --noredact | findstr lzj2012   # 无审批通知")
    out.append("  # APP 内“测试通知”按钮只会提示“系统通知被关闭，请到设置里允许”，无权限弹窗")

    status = "复现通过" if ok else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R2（静态可证；行为需真机 Android 13+ 验证，本机未执行）",
        "环境: Windows + Python 3.12 + xml.etree；无 Android SDK/模拟器",
        "检查对象: %s, %s, %s" % (MAN, NOT, WS),
    ] + out + ["结论: %s" % status])
    return {"id": ID, "title": TITLE, "status": status, "ok": ok, "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
