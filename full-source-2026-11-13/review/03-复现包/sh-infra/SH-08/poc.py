#!/usr/bin/env python3
# SH-08 交付完整性盘点：运维脚本引用/依赖、但**没有**包含在交付包里的关键配置与状态。
#
# 做法：把“引用位置”逐条回到 work/src 源码里核对（行号+token 必须命中），
# 再判断该路径是否能在交付包中找到对应文件。只统计“影响本轮审查结论”的项，
# 凭据类（token/key/env）单独标注为“合理不交付”，不计入缺失缺陷。
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
WORK = os.path.normpath(os.path.join(SRC, ".."))


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


# (路径, 引用文件(相对 src), 行号, 该行应包含的 token, 是否已交付, 类别, 影响)
REFS = [
    ("/etc/nginx/sites-enabled/ddos", None, None, None, False, "配置",
     "合并包“审查重点 6”与“测试结果 nginx -t（含 ddos-mode 前置 server）”所指文件；缺失导致 503 前置 server / 排除项 / include 顺序完全无法审查（SH-07）"),
    ("/etc/nginx/ddos-mode.conf", "cloud/usr/local/sbin/ddos-mode.sh", 3, "CONF=", False, "生成物",
     "由脚本生成，本身可接受；但 nginx.conf 是否 `include` 它、是否位于 sites-enabled 之前（“前置”）未交付，无法核对"),
    ("/etc/nginx/sites-enabled/*", "cloud/usr/local/sbin/ddos-mode.sh", 10, "sites-enabled", False, "配置",
     "第10行 grep 的唯一输入；站点名集合不可知，NAMES 生成后果（哪些站点 503）无法确定"),
    ("/var/www/ddos/ddos.html", "cloud/usr/local/sbin/ddos-mode.sh", 18, "ddos.html", False, "资源",
     "error_page 在 :17/:28，location = /ddos.html 在 :18/:29；文件缺失时 503 页可能变成错误页/500，体验与信息泄露都不确定"),
    ("/etc/msmtprc（msmtp -a exmail）", "cloud/usr/local/sbin/send-mail.py", 116, "msmtp", False, "配置/凭据",
     "SMTP 备通道全部参数（host/port/tls/tls_trust_file/口令）都在此文件；缺失导致“证书校验是否开启”“口令是否明文”无法审查（SH-15）"),
    ("/root/.config/resend/key", "cloud/usr/local/sbin/send-mail.py", 9, "resend", False, "凭据",
     "合理不交付；但脚本未校验该文件权限，若为 0644 则本机任意用户可读（建议部署检查，见 SH-15）"),
    ("/root/.config/cloudflare/token", "cloud/usr/local/sbin/cf-set-a.sh", 10, "cloudflare", False, "凭据",
     "合理不交付；cf-set-a.sh 只在 mktemp(600) 的 curl 配置里使用（符合其声明），但 ddos-monitor.py:29 直接 open().read()，无权限校验"),
    ("/root/.config/rainyun/rainyun.env", "cloud/usr/local/sbin/failover.sh", 6, "rainyun", False, "配置/凭据",
     "failover 的 MC_FQDN/HOME_FQDN/CLOUD_IP 全部来自此文件（第74-76行）；文件缺失即 die。路径仍叫 rainyun，与 v2 声明“移除无用的 Rainyun Key 依赖”需人工确认"),
    ("/var/www/logview/services.json", "cloud/usr/local/sbin/logview-health.py", 6, "services.json", False, "配置",
     "健康检查的“服务/定时器/容器清单”全靠它；缺失则 items=[]，status.json 的 items 为空，页面上看不出任何异常（SH-14）"),
    ("/var/www/logview/status.json", "cloud/usr/local/sbin/ddos-monitor.py", 4, "status.json", False, "生成物",
     "ddos-monitor 的带宽输入；由 logview-health.py 生成，缺失时 ddos-monitor 直接 return（静默停摆，SH-12）"),
    ("/data/mcserver/world", "cloud/usr/local/sbin/failover.sh", 101, "mcserver", False, "数据",
     "切回前归档的对象（第99-103行）；目录布局/大小/是否有 session.lock 未交付，归档一致性无法评估（SH-10）"),
    ("/data/backups", "cloud/usr/local/sbin/failover.sh", 21, "backups", False, "数据",
     "第21行 mkdir；第101行写 tar。无保留策略，磁盘水位不可知（SH-10）"),
    ("sudoers: NOPASSWD /usr/local/sbin/send-mail.py", "cloud/var/www/chat-lib/lib.php", 332, "sudo -n", False, "配置",
     "`sudo -n` 授权粒度决定“谁能调用发信脚本、能否传任意收件人/主题”；缺失则 send-mail 的滥用面无法定论（SH-15）"),
    ("systemd unit: mc.service", "cloud/usr/local/sbin/failover.sh", 146, "systemctl start mc", False, "配置",
     "Restart/User/ExecStartPre/成功判据都不可见；watchdog 与 systemd 双重看护是否冲突无法核对（SH-03/SH-17）"),
    ("家庭侧心跳写入脚本", "cloud/usr/local/sbin/failover.sh", 12, "HB_FILE", False, "脚本",
     "写 /root/failover/heartbeat 的一方不在交付包内；SH-01 的注入可达性因此只能判“高可能”"),
]


def main():
    ok = True
    print("== 0. 引用核对（每条都必须能在 work/src 的行里命中）==")
    verified = 0
    for path, ref, ln, tok, delivered, cat, _impact in REFS:
        if ref is None:
            print("   %-42s 引用=合并包文字（无源码行）" % path)
            continue
        src = os.path.join(SRC, ref.replace("/", os.sep))
        body = lines(src)
        line = body[ln - 1] if 0 < ln <= len(body) else ""
        hit = tok is not None and tok in line
        print("   %-42s %s:%d 命中=%s" % (path, ref, ln, "是" if hit else "否"))
        if hit:
            verified += 1
        else:
            ok = False
    print("   核对通过 %d 条" % verified)
    print()

    print("== 1. 缺失清单（影响审查结论的配置/脚本）==")
    print("   %-44s %-8s %s" % ("路径", "类别", "影响"))
    missing = 0
    for path, ref, ln, tok, delivered, cat, impact in REFS:
        if delivered:
            continue
        if cat == "凭据":
            print("   %-44s %-8s %s" % (path, cat, "（合理不交付，仅提示权限风险）"))
            continue
        missing += 1
        print("   %-44s %-8s %s" % (path, cat, impact))
    print()
    print("   缺失项合计: %d（不含纯凭据）" % missing)
    print()

    print("== 2. 与合并包“二、测试结果”的对照 ==")
    print("   - “nginx: nginx -t 通过（含 ddos-mode 前置 server）”：无法复核——")
    print("     nginx.conf / sites-enabled/ddos / ddos-mode.conf 的 include 关系均未交付。")
    print("   - “Bash: 6 个文件 bash -n 全部通过”：本机无 bash，无法复核（不构成缺陷，仅说明）。")
    print("   - “未包含任何密钥/Token/密码”：与源码一致（凭据全部来自 /root/.config/*），")
    print("     但这些凭据文件的**权限**未交付、脚本也未检查（cf-set-a 用 mktemp 600 尚可，")
    print("     ddos-monitor.py:29 直接 open 读取更宽松）。")
    print()

    print("== 3. 结论 ==")
    print("   “503 前置 server 与排除项”是本域最关键的审查对象，但它的实现文件不在包里；")
    print("   因此本报告只能证明 ddos-mode.sh 生成的规则本身没有排除项（SH-07），")
    print("   无法证明线上实际生效的配置与脚本一致 —— 这是明确标注的审查盲区，不是“已审查无问题”。")
    print()
    if missing < 8:
        ok = False
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
