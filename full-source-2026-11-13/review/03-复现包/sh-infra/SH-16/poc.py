#!/usr/bin/env python3
# SH-16 等价模型：cf-set-a.sh 的健壮性缺陷
#   (1) 缺参数时：`set -u` + `H="$1"` 先于 usage 检查 -> bash 直接报 unbound variable 退出，
#       第6行的 usage 分支不可达（R2：需 bash；本机用静态证据说明）。
#   (2) 生成的 curl 配置把 token 文件**原样**塞进双引号字符串；若 token 文件以换行结尾
#       （`echo >` 写的文件几乎必然如此），curl 会报 config 解析错误，所有 CF 调用失败。
#       —— 本条用本机 curl 8.21 真实复现（只连 127.0.0.1:1，不访问任何真实主机）。
#   (3) WANT 无 IP 格式校验；只更新一条 A 记录（result[0]）；无 --retry。
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
CFSET = os.path.join(SRC, "cloud", "usr", "local", "sbin", "cf-set-a.sh")


def lines(p):
    with open(p, encoding="utf-8") as f:
        return f.read().splitlines()


def write_cfg(path, token_bytes):
    """照抄 cf-set-a.sh:10 的写法：printf 'header = "Authorization: Bearer ' + cat token + '"\\n'"""
    with open(path, "wb") as f:
        f.write(b'header = "Authorization: Bearer ')
        f.write(token_bytes)
        f.write(b'"\n')


def curl_probe(cfg, outfile):
    """本机 curl 只连 127.0.0.1:1（不可达），用于判定配置文件是否能被解析。"""
    with open(outfile, "wb") as out:
        p = subprocess.run([CURL, "-K", cfg, "-sS", "-o", os.devnull, "--max-time", "3",
                            "http://127.0.0.1:1/"], stdout=out, stderr=subprocess.STDOUT)
    return p.returncode


def main():
    c = lines(CFSET)
    ok = True
    print("== 0. 源码事实（work/src 行号）==")
    for n in (4, 5, 6, 7, 9, 10, 11, 12, 14, 16, 17, 20, 21, 22, 23, 24):
        print("cf-set-a.sh:%d: %s" % (n, c[n - 1].rstrip()))
    print()

    print("== 1. 缺参数时 usage 分支不可达（静态/R2）==")
    print("   第5行在 set -u（第4行）之后直接 `H=\"$1\"`, `WANT=\"$2\"`：")
    print("   少传参数时 bash 报 '<arg>: unbound variable' 并以非零退出，")
    print("   第6行的 `[ -n \"$H\" ] && [ -n \"$WANT\" ] || { usage; exit 2; }` 永远执行不到。")
    first = c[4].strip()
    usage = c[5].strip()
    unreachable = first.startswith('H="$1"') and "usage" in usage
    print("   cf-set-a.sh:5 = %r；cf-set-a.sh:6 = %r" % (first, usage[:60]))
    print("   => usage 分支不可达: %s（结论需在装有 bash 的测试机复核）" % ("是" if unreachable else "否"))
    ok = ok and unreachable
    print()

    print("== 2. token 文件尾随换行 -> curl 配置解析失败（本机真实执行 curl）==")
    print("   curl 版本: %s" % subprocess.run([CURL, "--version"], capture_output=True, text=True)
          .stdout.splitlines()[0])
    tmp = os.path.join(HERE, ".tmp_sh16")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    try:
        # 覆盖名后的 token 文件（cat 原样读出）
        tok_nl = b"SECRET_TOKEN_ABC\n"
        tok_ok = b"SECRET_TOKEN_ABC"
        cfg_nl = os.path.join(tmp, "cfg_nl")
        cfg_ok = os.path.join(tmp, "cfg_ok")
        write_cfg(cfg_nl, tok_nl)
        write_cfg(cfg_ok, tok_ok)
        with open(cfg_nl, "rb") as f:
            print("   配置内容(带换行): %r" % f.read())
        with open(cfg_ok, "rb") as f:
            print("   配置内容(无换行): %r" % f.read())
        rc_nl = curl_probe(cfg_nl, os.path.join(tmp, "out_nl.txt"))
        rc_ok = curl_probe(cfg_ok, os.path.join(tmp, "out_ok.txt"))
        print("   curl -K <带换行配置> 退出码 = %d" % rc_nl)
        print("   curl -K <无换行配置> 退出码 = %d" % rc_ok)
        with open(os.path.join(tmp, "out_nl.txt"), encoding="utf-8", errors="replace") as f:
            print("   带换行时的 curl 输出: %r" % f.read()[:160])
        # curl: 2 = 配置文件解析失败；7 = 连接失败（说明配置本身 OK）
        bad = (rc_nl == 2) and (rc_ok != 2)
        print("   => 尾随换行导致配置解析失败: %s" % ("是（缺陷成立）" if bad else "否"))
        ok = ok and bad
        print()
        print("   影响：failover.sh 的 set_record 全部失败（cf-set-a.sh exit 1）；")
        print("   叠加 SH-05（失败仍推进 last_reported）=> DNS 永久不更新，且不再重试。")
        print()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("== 3. 其它健壮性（静态核对）==")
    txt = "\n".join(c)
    checks = [
        ("WANT 无 IP 格式校验", not any(k in txt for k in ("[[ $WANT =~", "grep -E", "case \"$WANT\""))),
        ("无 --retry/--retry-delay", "--retry" not in txt),
        ("只更新单条 A 记录(result[0])", ".result[0]" in txt and "result[]" not in txt),
        ("失败信息含 CF 错误体", "jq -c '.errors'" in txt),
    ]
    for name, cond in checks:
        print("   %-34s %s" % (name, "成立" if cond else "不成立"))
        ok = ok and cond
    print()
    print("VERDICT: %s" % ("REPRODUCED" if ok else "FAIL"))
    return 0 if ok else 1


CURL = shutil.which("curl") or "curl.exe"

if __name__ == "__main__":
    sys.exit(main())
