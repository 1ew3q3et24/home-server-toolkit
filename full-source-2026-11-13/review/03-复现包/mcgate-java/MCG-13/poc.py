# -*- coding: utf-8 -*-
"""MCG-13 复现: v2.1 "AI 审批令牌增加 jti 并一次性使用" 声明核对 —— 已实现, 但有 3 处缺陷.

REPRO_LEVEL: R2 (静态可证)

等价性前提
----------
逐行核对:
  ai-common.php:96-101  ai_sign_action: payload{uid,action,params,exp=+120,jti=24hex} + HMAC-SHA256
  ai-common.php:103-122 ai_verify_action: 签名 hash_equals 常量时间比较 -> exp -> jti 格式 ->
                        fopen(dir/hash(jti), 'x') 原子占位, 已存在则拒绝
  ai-bot-action.php:22 先 ai_verify_action(消费 jti)
  ai-bot-action.php:24 再校验 uid 归属; :29 再校验 action 白名单与 cfg.permissions
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
WWW = os.path.join(ROOT, "src", "cloud", "var", "www")


def rd(*p):
    return io.open(os.path.join(WWW, *p), "r", encoding="utf-8", errors="replace").read().splitlines()


def main():
    ai = rd("chat-lib", "ai-common.php")
    act = rd("chat", "ai-bot-action.php")
    bot = rd("chat", "ai-bot.php")
    print("FINDING: MCG-13 AI 审批令牌 jti 一次性实现核对(声明=符合, 但有缺陷)")
    print("REPRO_LEVEL: R2")
    print("")
    print("== 声明: 'AI: 审批令牌增加 jti 并一次性使用, 实测第二次被拒' ==")
    print("== 核对的实现 ==")
    for ln in (96, 97, 98, 99, 100):
        print("  ai-common.php:%-4d %s" % (ln, ai[ln - 1].strip()))
    print("  ...")
    for ln in (103, 104, 105, 106, 107, 108, 113, 114, 115, 116, 117, 118, 119, 120):
        print("  ai-common.php:%-4d %s" % (ln, ai[ln - 1].strip()))
    print("")
    for ln in (15, 22, 23, 24, 26, 28, 29, 30):
        print("  ai-bot-action.php:%-4d %s" % (ln, act[ln - 1].strip()))

    print("")
    print("== 判定 ==")
    print("  [符合] jti = 12 字节随机(96 bit), 在 HMAC 覆盖的 payload 内, exp=120s;")
    print("         fopen(...,'x') 是 O_EXCL 原子创建 => 同一令牌第二次使用必然失败;")
    print("         签名比较用 hash_equals(常量时间), 实现方式正确。")
    print("         (注: 该声明针对 approve.php 短链审批的是另一套 token, 别混淆)")
    print("  [缺陷1] 先烧令牌后鉴权: 第 22 行消费 jti, 第 24/29/30 行才校验 uid 归属、动作白名单、")
    print("          cfg.permissions。任何持有他人令牌的人(令牌泄露/被日志带出)都能让该审批")
    print("          永远失败 —— 单 token 的 DoS, 而且受害者重试时得到的是'批准已过期或无效'。")
    print("  [缺陷2] /var/lib/chat-ai/used/ 只写不删(116-120 行无清理逻辑), 每批准一次一个文件,")
    print("          永久累积(单目录 inode 增长); 目录不可写时 fopen 失败 -> 所有审批一律 403,")
    print("          且 @ 抑制了错误原因, 运维难排查。")
    print("  [缺陷3] 令牌未与调用方绑定(无 IP/会话指纹), 只靠 uid 字段; 群主账号会话被盗即可")
    print("          重放未消费的 token(窗口 120s)。这属于既有权限模型, 但一次性只有 120s 强度。")
    print("")
    print("== 建议 ==")
    print("  1) 把 uid/动作鉴权前移到 ai_verify_action 之前(先验身份再烧 jti):")
    print("     先解析 payload(不落盘)校验 uid==me.id 与动作许可, 最后再 fopen 'x' 占位;")
    print("  2) used 文件按日期分目录 + cron 清理(>7 天), 或用 DB 唯一键替代文件;")
    print("  3) 目录不可写时返回 500 并记日志, 不要伪装成'令牌过期'。")
    print("")
    print("== 判定标准 ==")
    print("  一次性语义成立(声明符合) => 本项不计为'文档声言不符'; 上述 3 处为 P3 加固项。")
    print("")
    print("RESULT: CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
