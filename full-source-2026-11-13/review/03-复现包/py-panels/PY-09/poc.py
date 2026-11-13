#!/usr/bin/env python3
"""PY-09 [P1][高危·无法复现] 管理凭据文件放在 Web 目录下：
AUTH_FILE = "/var/www/panel/panel-auth.json"（app.py:13）。若 nginx 把
/var/www/panel 作为 panel.* 站点的静态根（该子域在 ddospanel.py:33 的 DOMAINS 里存在），
则 https://panel.<域>/panel-auth.json 会直接返回该 JSON：salt、hash 与 **HMAC secret**。
拿到 secret 即可离线伪造会话令牌，**不需要口令**；拿到 hash 可离线爆破口令。

本脚本分两部分：
  [A] R1（本机可跑）：证明“拿着 secret 就能免密伪造会话”——用原始 app.make_token()
      生成令牌，塞进 cookie 直接访问管理页，全程不提交任何口令。
  [B] R3（需真实环境）：静态文件是否可被公网取到，取决于未交付的 nginx 配置，
      本机无法验证，只输出给运维方在自有环境执行的核对命令（本脚本不会发出任何网络请求）。

退出码 3 = NEED_REAL_ENV（暴露面需真实 nginx 配置确认）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as C  # noqa: E402

APP = "cloud/var/www/logview/app.py"


def part_a_offline_forgery():
    C.hr("PY-09-A  secret 泄露 -> 免密伪造会话（R1，离线）")
    app_mod, ddp = C.import_app()
    tmp = C.tmpdir("PY-09A")
    auth_path, auth = C.patch_paths(app_mod, ddp, tmp)
    print("\n[1] 被审代码（原样）：")
    print(C.src_lines(APP, 13, 14))
    print(C.src_lines(APP, 31, 34))
    print("\n[2] 假设 /var/www/panel/panel-auth.json 被 HTTP 取走（内容形态，值随机生成）：")
    print("    {salt: %s..., hash: %s..., secret: %s...}"
          % (auth["salt"][:8], auth["hash"][:8], auth["secret"][:8]))

    forged = app_mod.make_token(auth)   # 只用 secret，不需要口令
    print("\n[3] 用泄露的 secret 直接算出会话令牌: %s" % forged)
    print("    校验结果 app.token_ok(...) = %s" % app_mod.token_ok(auth, forged))

    client = app_mod.app.test_client()
    client.cookies[app_mod.COOKIE] = forged
    r = client.get("/", headers={"Host": "logs.lzj2012.top"})
    ok = (r.status_code == 200) and ("系统日志" in r.text)
    print("    带着伪造 cookie 访问 / : HTTP %s，看到管理页=%s（全程未提交口令）"
          % (r.status_code, "系统日志" in r.text))
    print("\n[4] 同时泄露的 hash 可离线爆破口令（PBKDF2 200000 轮，攻击者本地算）。")
    return ok


def part_b_r3_checks():
    C.hr("PY-09-B  静态可达性核对（R3，需真实环境；本脚本不联网）")
    print("""
无法在本机复现的具体技术原因：
  1. 缺失运行环境：交付包（46 文件）没有包含任何 nginx 站点配置，
     而简报/合并包“审查重点”第 6 条点名的 etc/nginx/sites-enabled/ddos 也未随包交付；
     `cloud/var/www/panel/` 的部署方式（静态根 or 反代）无从得知。
  2. 需要线上配置/文件状态：需要 panel.* 站点的 server 块 root 指向 /var/www/panel，
     或存在 `location ~ \\.json$ { root /var/www; }` 之类的静态兜底；
     此外 panel-auth.json 由未交付的 panel.service 生成，其真实权限位未知。
  3. 需要真实主机交互：确认方式必须向被审域名发请求，本项目红线禁止（也不应在生产验证）。
  4. 无需多要素时序；也无需真机。

正确部署下（本文件不应可达）的核对步骤（由运维方在自有测试环境执行）：
  a) nginx -T | grep -nE 'server_name|root |proxy_pass' | grep -n -A3 -B3 panel
     确认 panel.* 的 root 是否为 /var/www/panel 或 /var/www。
  b) 在**测试域名**上：
       curl -sS -o /tmp/pa.json -w '%{http_code}\\n' https://panel.<测试域>/panel-auth.json
     期望 403/404；若 200 且内容含 "salt"/"hash"/"secret"，即为 P0 级凭据泄露（本报告按 P1 保守定级）。
  c) 同样检查（同目录/同根）：
       /panel-auth.json  /../panel-auth.json  /%2e%2e/panel/panel-auth.json
       https://logs.<测试域>/sources.json   https://logs.<测试域>/status.json
  d) 若可达：立即把凭据文件移出 Web 根（如 /etc/logview/panel-auth.json，chmod 600，
     属主与 Flask 运行用户一致），轮换 secret（所有现有会话失效）并改口令。

判定标准：
  - 200 且 JSON 含 secret  -> 高危确认（P0），按本报告 PY-09 修复建议执行；
  - 403/404 且 nginx root 不含 /var/www/panel -> 不可达，降级为 P3 加固（仍建议移出 Web 根）。
""")


def main():
    C.hr("PY-09  管理凭据文件位于 /var/www/panel 下的暴露面（R1 影响链 + R3 暴露面）")
    a = part_a_offline_forgery()
    part_b_r3_checks()
    print()
    print("  [OK]   A（R1）：已知 secret 可免密伪造会话并访问管理页")
    print("  [R3]   B：panel-auth.json 是否可被公网读取 -> 需真实 nginx 配置，本机无法验证")
    C.result_need_real_env("PY-09：影响链已 R1 证实，暴露面需真实环境确认")


if __name__ == "__main__":
    main()
