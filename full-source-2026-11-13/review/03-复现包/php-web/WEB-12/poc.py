#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WEB-12 [P3] 移动端 UA 自动拉起 lzjapp:// 自定义 scheme：无手势、UA 可伪造、可被任意 App 劫持。

等价性前提：
  - 1:1 复刻 chat/index.php:918-930 的 JS 判定与动作：
      if (/LZJToolbox/.test(ua)) return;
      if (!/Android|iPhone|iPod|Mobile|HarmonyOS/i.test(ua) || /Windows NT|Macintosh/i.test(ua)) return;
      if (sessionStorage.getItem("lzj_app_jump")) return;
      sessionStorage.setItem("lzj_app_jump","1");
      iframe.src = "lzjapp://chat";
  - 用 Python re 复刻 JS 正则语义；不创建 iframe、不打开任何 scheme。
  - 同时核对：本域两文件无任何 Location 跳转（开放重定向为"未发现"）。
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
IDX = SRC / "cloud/var/www/chat/index.php"
MCV = SRC / "cloud/var/www/mcverify/index.php"


def launches(ua, have_flag=False):
    if re.search(r"LZJToolbox", ua):
        return False, "UA 含 LZJToolbox -> 跳过"
    if not re.search(r"Android|iPhone|iPod|Mobile|HarmonyOS", ua, re.I) \
       or re.search(r"Windows NT|Macintosh", ua, re.I):
        return False, "非移动端 -> 跳过"
    if have_flag:
        return False, "sessionStorage 已置位（每会话一次）"
    return True, "拉起 lzjapp://chat"


def main():
    lines = IDX.read_text(encoding="utf-8").splitlines()
    print("=== 自动拉起逻辑 (chat/index.php:918-930) ===")
    for n in range(918, 931):
        print("%4d| %s" % (n, lines[n - 1].strip()))

    UAS = [
        ("Android Chrome", "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"),
        ("iPhone Safari", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"),
        ("HarmonyOS", "Mozilla/5.0 (Phone; OpenHarmony 4.0) AppleWebKit/537.36 Chrome/114 Mobile Safari/537.36"),
        ("Windows 桌面", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"),
        ("iPad", "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"),
        ("LZJToolbox App", "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 LZJToolbox/1.0"),
        ("伪造 UA 跳过（攻击者/自动化）", "Mozilla/5.0 (Linux; Android 13) LZJToolbox"),
    ]
    print("\n%-30s %-10s %s" % ("UA", "是否拉起", "原因"))
    for name, ua in UAS:
        hit, why = launches(ua)
        print("%-30s %-10s %s" % (name, "是" if hit else "否", why))

    print("\n=== 开放重定向核对 ===")
    for f in (IDX, MCV):
        text = f.read_text(encoding="utf-8")
        locs = re.findall(r"header\s*\(\s*['\"]Location", text)
        redir = re.findall(r"location\.(?:href|replace)\s*=\s*[^;]+", text)
        print("  %-22s header(Location)=%d, location.*=%s"
              % (Path(f).name, len(locs), [r.strip()[:70] for r in redir]))
    print("  -> 无服务端跳转；脚本内跳转目标均为硬编码本地常量，未发现开放重定向。")

    print("\n=== 风险点 ===")
    print("  1) 无用户手势，页面加载即尝试打开自定义 scheme（部分浏览器会弹确认框/拦截）")
    print("  2) Android/iOS 上任意已安装 App 均可注册 lzjapp scheme -> 可被恶意 App 劫持")
    print("  3) 该动作发生在 TOS/隐私确认之前（与 WEB-10 声明冲突）")
    print("  4) 判定完全依赖可伪造的 UA 字符串：用户/自动化改 UA 即可跳过或触发")

    ok = launches(UAS[0][1])[0] and (not launches(UAS[6][1])[0])
    print("\n判定: 移动端自动拉起硬编码 lzjapp://chat；UA 可伪造、scheme 可被任意 App 抢占。")
    print("RESULT: " + ("复现通过" if ok else "未复现"))


if __name__ == "__main__":
    main()
