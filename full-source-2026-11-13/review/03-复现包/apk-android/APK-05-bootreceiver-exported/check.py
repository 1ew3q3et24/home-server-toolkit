# -*- coding: utf-8 -*-
"""APK-05 复现检查：BootReceiver 以 exported=true 导出，且 onReceive 不校验 action/来源。
任意应用可发显式广播给 top.lzj2012.toolbox/.BootReceiver：
 - 有令牌时 → 后台调用 startForegroundService；Android 12+ 无 BOOT_COMPLETED 豁免 →
   ForegroundServiceStartNotAllowedException 未捕获 → 应用崩溃（可被反复触发）
 - 旧系统 → 常驻轮询服务被外部拉起
系统 BOOT_COMPLETED 广播由 system 发送，exported=false 也能收到（checkComponentPermission 对
SYSTEM_UID 直接放行），所以 exported=false 不影响正常开机自启。"""
import pathlib
import sys
import xml.etree.ElementTree as ET

ID = "APK-05"
TITLE = "导出的 BootReceiver 无 action 校验：任意应用可显式触发（Android 12+ 崩溃 / 拉起常驻服务）"
MAN = "apk/src/AndroidManifest.xml"
BR = "apk/src/java/top/lzj2012/toolbox/BootReceiver.java"
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
    man_txt = read(src / MAN)
    br = read(src / BR)
    root = ET.fromstring("\n".join(man_txt))
    out = []
    ok = True

    def check(cond, desc, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    recv = None
    for r in root.iter("receiver"):
        if r.get(NS + "name") == ".BootReceiver":
            recv = r
    check(recv is not None, "清单中找到 .BootReceiver", "AndroidManifest.xml:58")
    exported = recv.get(NS + "exported") if recv is not None else None
    check(exported == "true", "BootReceiver 显式 android:exported=\"true\" → 可被任意应用显式 Intent 命中",
          "AndroidManifest.xml:58")
    check(recv is not None and recv.get(NS + "permission") is None,
          "BootReceiver 未设置 android:permission（无签名级权限门槛）")
    actions = [a.get(NS + "name") for f in (recv.findall("intent-filter") if recv is not None else [])
               for a in f.findall("action")]
    check(actions == ["android.intent.action.BOOT_COMPLETED"],
          "intent-filter 只声明 BOOT_COMPLETED（但 exported=true 时显式 Intent 不受 filter 限制）",
          "AndroidManifest.xml:59-61")

    check("getAction" not in "\n".join(br),
          "BootReceiver.onReceive 不校验 intent.getAction()", "BootReceiver.java:9-13")
    check("startForegroundService" in "\n".join(br),
          "无条件下调用 startForegroundService（仅以“本地是否有令牌”为条件）", "BootReceiver.java:12")
    check("catch" not in "\n".join(br),
          "未捕获 ForegroundServiceStartNotAllowedException（Android 12+ 后台启动 FGS 会抛）",
          "BootReceiver.java:8-14")

    out.append("外部应用可复制执行的触发命令（R3，需真机安装 APP 且本机无 adb，未执行）：")
    out.append('  adb shell am broadcast -n top.lzj2012.toolbox/.BootReceiver \\')
    out.append('      -a top.lzj2012.toolbox.EVIL --receiver-include-background   # 任意 action')
    out.append("判定：logcat 出现 FATAL EXCEPTION + ForegroundServiceStartNotAllowedException（Android 12+）")
    out.append("      或 dumpsys activity services 出现 top.lzj2012.toolbox/.WatchService（旧系统）")
    out.append("平台依据：BOOT_COMPLETED 是 protected broadcast，由 SYSTEM_UID 投递；")
    out.append("          ActivityManagerService.checkComponentPermission 对 SYSTEM_UID 直接放行，")
    out.append("          故 exported=false 不影响系统广播，却可挡住外部显式 Intent。")

    status = "复现通过" if ok else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R2（清单+代码静态可证）；运行时验证需真机（R3），本机无 adb/模拟器未执行",
        "环境: Windows + Python 3.12 + xml.etree；无 Android SDK",
        "检查对象: %s, %s" % (MAN, BR),
    ] + out + ["结论: %s" % status])
    return {"id": ID, "title": TITLE, "status": status, "ok": ok, "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
