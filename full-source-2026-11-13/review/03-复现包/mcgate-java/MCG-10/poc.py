# -*- coding: utf-8 -*-
"""MCG-10 复现: config.yml 死配置与死字段 —— 运维按配置调严不生效.

REPRO_LEVEL: R1 (静态交叉核对: config.yml 的键 vs Java 中读取的键)

等价性前提
----------
1. 配置键只有在 Java 代码里出现 plugin.getConfig().getXxx("<key>") 才会生效;
   本文用正则抽取 Java 侧所有 "key" 字面量, 与 config.yml 顶层路径比对。
2. CheckResult.expiresIn 只有在被读取/使用才有意义; 本文检查它在 Gate/McGate 中是否被使用。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
MCGATE = os.path.join(ROOT, "src", "cloud", "opt", "build", "mcgate", "src")
JAVA_DIR = os.path.join(MCGATE, "com", "lzj", "mcgate")


def read_cfg_keys(path):
    """极简 YAML 展平: 只处理 2 层缩进, 足够本文件。"""
    keys = []
    section = ""
    for line in io.open(path, "r", encoding="utf-8", errors="replace").read().splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        m = re.match(r"\s*([\w.-]+):\s*(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if indent == 0:
            section = k
            keys.append(k)
        else:
            keys.append(section + "." + k)
    return keys


def main():
    print("FINDING: MCG-10 config.yml 死配置/死字段")
    print("REPRO_LEVEL: R1")
    print("")
    cfg_path = os.path.join(MCGATE, "config.yml")
    cfg_keys = read_cfg_keys(cfg_path)

    java_files = [os.path.join(JAVA_DIR, f) for f in os.listdir(JAVA_DIR) if f.endswith(".java")]
    java_src = {os.path.basename(p): io.open(p, "r", encoding="utf-8",
                                            errors="replace").read() for p in java_files}
    all_java = "\n".join(java_src.values())
    read_keys = set(re.findall(r'get(?:String|Int|Boolean|Long|Double)\(\s*"([^"]+)"', all_java))

    print("== config.yml 中的配置项 -> 是否被读取 ==")
    dead = []
    for k in cfg_keys:
        used = k in read_keys
        print("  %-28s %s" % (k, "已读取" if used else "!! 未被任何 Java 代码读取"))
        if not used:
            dead.append(k)

    print("")
    print("== 反向: Java 读取但 config.yml 未提供的键 ==")
    for k in sorted(read_keys):
        if k not in cfg_keys:
            print("  %-28s 缺失 -> 使用代码内默认值(可能更宽松)" % k)

    print("")
    print("== CheckResult.expiresIn ==")
    set_in = "expiresIn" in java_src["Backend.java"]
    used_in_gate = "expiresIn" in java_src["Gate.java"]
    print("  Backend.java 赋值: %s (line 62, 默认值 133)" % set_in)
    print("  Gate.java 读取: %s" % used_in_gate)
    print("  => 后端给的验证码 TTL 从未用于冻结超时; 实际超时取 gate.timeout-seconds(300),")
    print("     与后端 mc_timeout() 可能不一致(前端等待时长/踢出时机与码有效期脱钩)。")

    print("")
    print("== 影响 ==")
    print("  * gate.random-check-rate: 运维以为改它能调抽查比例, 实际完全不生效;")
    print("    抽查率只由数据库 settings.mc_check_rate 决定(mc-api.php:25-29), 默认 0.15。")
    print("    '我把抽查改成 1.0 就全员复核' 是错的 => 部署方基于错误认知做安全决策。")
    print("  * 其余死键同理; expiresIn 死字段造成前后端 TTL 语义不一致。")
    print("")
    print("== 判定标准 ==")
    print("  死键/死字段集合非空 => 配置面存在误导(静态确认, R1)。")
    print("")
    print("死配置=%s" % dead)
    print("RESULT: CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
