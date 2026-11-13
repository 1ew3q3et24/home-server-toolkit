# -*- coding: utf-8 -*-
"""APK-04 复现检查：通知按钮直接调用 Api.approve，且以 Broadcast PendingIntent 承载。
FLAG_IMMUTABLE 只阻止“填充/篡改 Intent”，不阻止任何拿到该 PendingIntent 的组件调用 send()；
通知监听类应用（用户授予“通知使用权”即可获得 Notification.Action.actionIntent）可在无用户点击的情况下
触发 ALLOW 广播 → 直接批准进服请求。"""
import pathlib
import sys

ID = "APK-04"
TITLE = "通知“允许”动作是广播 PendingIntent：通知监听应用可无感自动审批（绕过用户二次确认）"
NOT = "apk/src/java/top/lzj2012/toolbox/Notifier.java"
AR = "apk/src/java/top/lzj2012/toolbox/ActionReceiver.java"
MAN = "apk/src/AndroidManifest.xml"


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
    notif = read(src / NOT)
    ar = read(src / AR)
    man = read(src / MAN)
    out = []
    ok = True

    def check(cond, desc, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    allow_pi = ln_of(notif, "PendingIntent.getBroadcast(c, 2000 + p.id, allow,")
    deny_pi = ln_of(notif, "PendingIntent.getBroadcast(c, 3000 + p.id, deny,")
    check(allow_pi == 64 and deny_pi == 71,
          "允许/拒绝动作是 Broadcast PendingIntent（不是需要用户点击界面的 getActivity）",
          "Notifier.java:64,71")
    check(ln_of(notif, 'allow.setAction("top.lzj2012.toolbox.ALLOW");') == 61,
          "广播 action 是可预测的字符串常量", "Notifier.java:61")
    check("FLAG_IMMUTABLE" in "\n".join(notif),
          "已使用 FLAG_IMMUTABLE（只能防填充/篡改，不防 send()）", "Notifier.java:41,58,65,72")
    check(ln_of(notif, '"允许", piAllow)') == 88,
          "通知按钮绑定该 PendingIntent", "Notifier.java:88")
    check(ln_of(ar, "if (allow) Api.approve(token, id); else Api.deny(token, id);") == 24,
          "ActionReceiver 收到广播后直接执行审批（无二次确认、无界面）", "ActionReceiver.java:24")
    check("getCallingPackage" not in "\n".join(ar) and "checkCallingPermission" not in "\n".join(ar)
          and "getSendingUid" not in "\n".join(ar),
          "接收方不校验调用来源（exported=false 也挡不住 PendingIntent 持有者 send()）",
          "ActionReceiver.java:10-31")
    check(ln_of(man, 'android:name=".ActionReceiver" android:exported="false"') == 56,
          "ActionReceiver 虽 exported=false，但通知监听应用通过 PendingIntent 触发不受此限制",
          "AndroidManifest.xml:56")

    out.append("攻击路径（R2 静态证明，运行时需真机 R3）：")
    out.append("  1. 受害机安装并授予“通知使用权”的任意应用（助手/清理/自动化类）")
    out.append("  2. 该应用在 NotificationListenerService.onNotificationPosted 中取")
    out.append("     sbn.getNotification().actions[i].actionIntent → PendingIntent")
    out.append("  3. 直接调用 actionIntent.send() → 系统投递 ALLOW 广播给 ActionReceiver")
    out.append("  4. ActionReceiver 用本地设备令牌调用 mc_approve → 进服请求被批准，用户零感知")

    status = "复现通过" if ok else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R2（静态可证）；运行时复现需真机 + 通知监听应用（见 README，本机未执行）",
        "环境: Windows + Python 3.12；无 Android SDK/模拟器，未安装 APK",
        "检查对象: %s, %s, %s" % (NOT, AR, MAN),
    ] + out + ["结论: %s" % status,
               "说明: FLAG_IMMUTABLE 修复的是“恶意填充 extras”，不是“未经用户手势调用”。"])
    return {"id": ID, "title": TITLE, "status": status, "ok": ok, "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
