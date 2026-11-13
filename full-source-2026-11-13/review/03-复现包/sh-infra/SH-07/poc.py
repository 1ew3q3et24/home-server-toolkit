#!/usr/bin/env python3
# SH-07 等价模型：503 前置 server 打开后，管理面是否会被自己的规则挡在门外？
#
# 结论链：
#   1) ddos-mode.sh 生成的 503 server 只认 4 个 location，**没有任何 IP allow/deny、
#      没有健康检查/面板域名的显式放行**；
#   2) 唯一的“排除项”来自第 10 行的 `grep -v '^ddos\.'` —— 即“server_name 以 ddos.
#      开头的站点不进入 503 名单”，这是一条**命名约定**，不是配置；
#   3) 面板域名若不叫 ddos.*（或控制台 vhost 不在 sites-enabled 里），就会被写进
#      NAMES 并被 503，管理员无法通过面板关闭模式；只能 SSH 进去跑 ddos-mode.sh off，
#      或等 ddos-monitor 的 10 分钟自动退出；
#   4) 真正的“排除项”实现位于**未交付**的 etc/nginx/sites-enabled/ddos，无法审查（见 SH-08）。
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
DDOS = os.path.join(SRC, "cloud", "usr", "local", "sbin", "ddos-mode.sh")
PANEL = os.path.join(SRC, "cloud", "var", "www", "logview", "ddospanel.py")
ALLOW = os.path.join(SRC, "cloud", "etc", "ddos-allowlist.json")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def build_names(vhosts):
    """ddos-mode.sh:10 的名字过滤（简化到“已解析出的 server_name 列表”这一步）。"""
    keep = []
    for n in vhosts:
        if n in ("", "_", "localhost"):
            continue
        if n.startswith("ddos."):
            continue
        keep.append(n)
    return sorted(set(keep))


def main():
    d = lines(DDOS)
    panel = lines(PANEL)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in range(9, 32):
        print("ddos-mode.sh:%d: %s" % (n, d[n - 1]))
    print("--- ddos-monitor 的 10 分钟自动退出（本域外但决定自锁时长）---")
    mon = lines(os.path.join(SRC, "cloud", "usr", "local", "sbin", "ddos-monitor.py"))
    for n in (13, 141, 142, 146):
        print("ddos-monitor.py:%d: %s" % (n, mon[n - 1].strip()))
    print("--- ddospanel.py 对“排除项”的文档承诺 ---")
    for n in (262, 289, 294):
        print("ddospanel.py:%d: %s" % (n, panel[n - 1].strip()[:150]))
    print()

    generated = "\n".join(d[10:31])
    print("== 1. 生成的 503 server 里有那些放行/排除指令？==")
    for kw in ("allow ", "deny ", "geo ", "map ", "satisfy", "auth_request"):
        hit = kw in generated
        print("   %-12s %s" % (kw.strip(), "存在" if hit else "不存在"))
        if hit:
            ok = False
    acme = generated.count("acme-challenge")
    print("   ACME 例外   %d 处（仅 /.well-known/acme-challenge/ 放行）" % acme)
    print()
    print("[+] 结论：503 规则对**所有** $NAMES 的站点都是 return 503，")
    print("    除了 ACME 挑战路径，没有任何 HTTP 层的放行（无管理 IP、无健康检查路径、无面板域名例外）。")
    print()

    print("== 2. 唯一的“排除项”：命名约定 ddos.* ==")
    filt_line = d[9]
    assert "grep -v '^ddos\\.'" in filt_line or "grep -v '^ddos.'" in filt_line, filt_line
    print("   ddos-mode.sh:10 片段: ... %s ..." % [x for x in filt_line.split("|") if "ddos" in x][0].strip())
    print("   => 只要 server_name 以 'ddos.' 开头就被排除，与“是不是管理面板”无关；")
    print("      反之，管理面板叫别的名字就不会被排除。")
    print()

    print("== 3. 用一组常见 vhost 名做推演：谁会 503、谁被排除 ==")
    cases = [
        ("控制台域名就是 ddos.lzj2012.top", ["chat.lzj2012.top", "lzj2012.top",
                                            "mc.lzj2012.top", "ddos.lzj2012.top"]),
        ("控制台叫 panel.lzj2012.top（不是 ddos.*）", ["chat.lzj2012.top", "lzj2012.top",
                                                   "mc.lzj2012.top", "panel.lzj2012.top"]),
        ("控制台叫 logview.lzj2012.top", ["chat.lzj2012.top", "logview.lzj2012.top"]),
    ]
    for label, vhosts in cases:
        names = build_names(vhosts)
        blocked = [n for n in names if n in vhosts]
        excluded = [n for n in vhosts if n not in names]
        print("   - %s" % label)
        print("     进入 503 名单: %s" % (" ".join(blocked) or "（空）"))
        print("     被排除:       %s" % (" ".join(excluded) or "（无）"))
        danger = any(v in names for v in vhosts if v.startswith(("panel.", "logview.")))
        if danger:
            print("     <== 管理面 503：面板无法访问 -> 只能 SSH 或等 10 分钟自动退出")
    print()
    print("   注：真实站点集合无法确认（`etc/nginx/sites-enabled/ddos` 未交付），")
    print("       因此“到底哪个域名被排除”属于审查盲区。")
    print()

    print("== 4. ddos-allowlist.json 是不是 HTTP 排除项？==")
    allow = json.load(open(ALLOW, encoding="utf-8"))
    print("   文件内容: %s" % json.dumps(allow, ensure_ascii=False))
    names = allow.get("allow", [])
    print("   条目数=%d；含 IP 字面量=%s；含域名=%s"
          % (len(names),
             any(re.match(r"^[0-9.]+$", x) for x in names),
             any("." in x and not re.match(r"^[0-9.]+$", x) for x in names)))
    print("   => 该文件只被 ddos-monitor.py:16 用作 nethogs 进程名白名单，")
    print("      与 nginx 的 503 前置 server 没有任何关系，不能当 HTTP 排除项用。")
    print("      （它的缺陷见 SH-09）")
    print()

    print("== 5. 自锁评估 ==")
    print("   可恢复路径 1：SSH 登录后 `/usr/local/sbin/ddos-mode.sh off`（需要 root 权限）。")
    print("   可恢复路径 2：ddos-monitor 判定带宽回落并连续 10 分钟正常 -> 自动 mode_off。")
    print("                 该路径依赖 status.json 持续写入且 nginx -t 能通过（见 SH-02/SH-12）。")
    print("   不可恢复情形：sshd 之外的运维入口（面板/API）全部 503，且自动退出被 SH-02 的")
    print("                 标志/回滚缺陷卡死 -> 只能 SSH。")
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
