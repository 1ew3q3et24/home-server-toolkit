#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APPAPI-12 [P3] mc-api 把验证码前 4 位写进审计日志；审批接口又没有任何速率限制
                 -> 能读日志的人 + 无速率限制的 submit = 10^4 量级枚举
                 （依赖日志读取权限，故只评 P3；单独看两项都是纵深防御缺失）

等价性前提（源码事实）：
  - mc-api.php:69 `chat_log('[MC闸门]', 'issue name=... code=' . substr($code, 0, 4) . '****')`
  - mc-api.php:107-132 submit / :145-160 approve_link 内没有任何 ip_bump/频次检查。
  - chat.log 由 logview 面板（另一域 `cloud/var/www/logview/*.py`）读取展示。

运行: python poc.py   退出码 0 = 复现成功。
"""
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parents[3]
WWW = WORK / "src" / "cloud" / "var" / "www"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


mc = read(WWW / "chat" / "mc-api.php")

print("== 1) 源码核对：日志泄露验证码前缀")
print(f"   chat_log 中出现 substr($code, 0, 4): {'substr($code, 0, 4)' in mc}")
print("   日志行形如: [MC闸门] issue name=Steve bound=0 code=1234****")
print("   -> 完整验证码是 4+4 位（mc_new_code 只生成 [0-9]{4}-[0-9]{4}），日志泄露一半。")

print()
print("== 2) 源码核对：审批接口无速率限制")
for name, start, end in (("submit", "case 'submit'", "case 'link_status'"),
                         ("approve_link", "case 'approve_link'", "case 'status'")):
    i, j = mc.find(start), mc.find(end)
    blk = mc[i:j] if (i >= 0 and j > i) else ""
    print(f"   {name:<12} 含 ip_bump: {'ip_bump(' in blk}；含 login_fail_ok: {'login_fail_ok(' in blk}")

print()
print("== 3) 组合后的枚举成本（仅用于说明纵深缺失，不是主漏洞）")
space = 10 ** 4
print(f"   已知 game_name（日志里也有）与验证码前 4 位时，剩余空间 = {space} 种。")
for rps in (10, 100, 1000):
    print(f"   若服务端无速率限制，{rps:>4} 请求/秒 -> 穷尽约 {space/rps/60:.1f} 分钟；")
print("   但实际上验证码 TTL=300 秒，且同一游戏名的 code 会被 check 续期，")
print("   真正的门槛是「能否读日志」（chat.log 属 www-data/root，logview 面板有鉴权）。")

print()
print("== 4) 还有一个纯卫生问题：mc_new_code() 是死代码")
print(f"   mc_new_code 定义: {'function mc_new_code' in mc}；调用点: {mc.count('mc_new_code(') - 1}")
print("   当前发码走的是链接（code 字段存 https URL），8 位数字码仅剩兼容旧数据；")
print("   日志仍按 8 位码格式截取，属于历史遗留逻辑，建议一并收敛。")

ok = ("substr($code, 0, 4)" in mc) and ("ip_bump(" not in mc)
print()
print("RESULT: PASS" if ok else "RESULT: FAIL")
sys.exit(0 if ok else 1)
