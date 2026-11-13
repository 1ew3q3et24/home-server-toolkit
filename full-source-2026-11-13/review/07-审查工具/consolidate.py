#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总 7 个审查域的 findings.jsonl：合并重复项、Lead 严重度复核、生成修复任务单。"""
import json, pathlib, io, sys, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPORTS = pathlib.Path(r"D:\Desktop\新建文件夹\work\reports")
REPRO = pathlib.Path(r"D:\Desktop\新建文件夹\work\repro")
OUT = pathlib.Path(r"D:\Desktop\新建文件夹\work\pack")
OUT.mkdir(parents=True, exist_ok=True)


def repro_dir(domain, fid):
    """返回相对 work/ 的复现目录路径；支持 <ID> 与 <ID>-<slug> 两种命名。无则返回空串。"""
    base = REPRO / domain
    if not base.is_dir():
        return ""
    exact = base / fid
    if exact.is_dir():
        return "repro/%s/%s" % (domain, fid)
    cands = sorted([x for x in base.iterdir() if x.is_dir() and re.match(re.escape(fid) + r"([-_].*)?$", x.name)])
    if cands:
        return "repro/%s/%s" % (domain, cands[0].name)
    return ""

DOMAINS = ["php-app-api", "php-main-api", "php-web", "py-panels", "sh-infra", "apk-android", "mcgate-java"]

records = []
for d in DOMAINS:
    p = REPORTS / (d + ".findings.jsonl")
    if not p.exists():
        print("MISSING:", p)
        continue
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        r = json.loads(ln)
        r["domain"] = d
        records.append(r)

# ---- 合并重复（同根因、不同域/不同入口）----
# primary -> [被并入的 ID]
MERGE = {
    "MCG-15": ["APPAPI-01"],            # 封禁账号的 MC 名仍被放行：check/pending/ack 不查 ban
    "WEB-07": ["APPAPI-05", "MCG-09"],  # 绑定/审批 check-then-act 竞态（3 个入口）
    "WEB-03": ["MCG-14"],               # tos_ok=1 客户端可伪造，TOS 闸门形同虚设
    "API-01": ["APPAPI-03"],            # CSRF：只覆盖 api.php；新入口无 Origin 校验 / fail-open
    "APPAPI-06": ["API-06"],            # app-wait 自建鉴权缺 ban_active
    "APPAPI-08": ["APK-01"],            # app_web_login 明文下发会话 Cookie + APK 非 HttpOnly 写入
}
MERGED_INTO = {}
for k, v in MERGE.items():
    for x in v:
        MERGED_INTO[x] = k

# ---- Lead 严重度复核（覆盖 teammate 评级，附理由）----
OVERRIDE = {
    "MCG-15": ("P1", "并入 APPAPI-01（原 P1）后取较高评级：MC 闸门 check 不查 bans，导致被封禁账号绑定的 MC 名仍可进服，封禁对 MC 服务器失效。"),
    "WEB-05": ("P1", "无鉴权即可耗尽全站当日验证码/注册配额（mcverify 以服务器 IP 代发上游请求 → 限流键聚合成一个桶），导致全站无法注册与找回密码；属单人可完成的可用性攻击，从 P2 上调。"),
    "API-01": ("P2", "维持 P2：现代浏览器跨站 POST 必带 Origin，且会话 Cookie 为 SameSite=Lax；但校验是 fail-open 且无 CSRF token 兜底，一旦同源 XSS/浏览器策略变化即失效，且 v2.1 声明“对 POST 校验 Origin”未覆盖新入口。"),
    "APPAPI-04": ("P2", "维持 P2 但标注“登录 CSRF”链路：qr_poll 无鉴权且直接 set_session，/qr 页面缺失无法闭环验证是否存在一键登录劫持。"),
}

by_id = {}
for r in records:
    by_id[r["id"]] = r

merged, merged_detail = [], []
for r in records:
    if r["id"] in MERGED_INTO:
        merged_detail.append((r["id"], MERGED_INTO[r["id"]]))
        continue
    r = dict(r)
    r["also_seen_in"] = MERGE.get(r["id"], [])
    r["xs"] = {}
    for x in MERGE.get(r["id"], []):
        src = by_id.get(x)
        if src:
            r["xs"][x] = {"file": src.get("file"), "line": src.get("line"), "title": src.get("title")}
    if r["id"] in OVERRIDE:
        sev, why = OVERRIDE[r["id"]]
        r["severity_original"] = r["severity"]
        r["severity"] = sev
        r["severity_reason"] = why
    merged.append(r)

ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
merged.sort(key=lambda x: (ORDER.get(x["severity"], 9), x["domain"], x["id"]))

with open(OUT / "01-发现总表.jsonl", "w", encoding="utf-8", newline="\n") as f:
    for r in merged:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

counts = {}
for r in merged:
    counts[r["severity"]] = counts.get(r["severity"], 0) + 1

# ---- 修复任务单 ----
lines = []
lines.append("# 05 · 修复任务单（按 P0 → P3 排序）\n")
lines.append("> 本单由 7 个域的 findings 合并去重后自动生成，并用 Lead 复核意见覆盖了个别严重度。")
lines.append("> 每条格式：`[级别] ID 标题` → 位置 / 复现物 / 改进建议 / 验收标准。")
lines.append("> 修完一条就把 `[ ]` 改成 `[x]`，并按“验收标准”跑 `03-复现包/<域>/run_all.py` 确认该条复现从“通过”变为“不通过”。\n")
lines.append("## 统计\n")
lines.append("| 级别 | 条数 |\n|---|---:|")
for s in ["P0", "P1", "P2", "P3"]:
    lines.append("| %s | %d |" % (s, counts.get(s, 0)))
lines.append("\n合计 %d 条（合并 %d 条重复项）。\n" % (len(merged), len(merged_detail)))
lines.append("## 合并/去重对照\n")
lines.append("| 并入 | 主条目 |\n|---|---|")
for a, b in sorted(merged_detail):
    lines.append("| %s | %s |" % (a, b))
lines.append("")

SEV_NAME = {"P0": "严重", "P1": "高", "P2": "中", "P3": "低"}
for r in merged:
    lines.append("---\n")
    lines.append("## [ ] [%s/%s] %s · %s\n" % (r["severity"], SEV_NAME[r["severity"]], r["id"], r["title"]))
    lines.append("- **位置**：`%s:%s`" % (r.get("file"), r.get("line")))
    lines.append("- **类别**：%s　**可信度**：%s　**复现级别**：%s" % (r.get("category"), r.get("confidence"), r.get("repro_level")))
    lines.append("- **所属域**：%s" % r["domain"])
    if r.get("doc_claim_mismatch"):
        lines.append("- **⚠ 文档声言不符**：v2.1 修复声明与实际实现不一致")
    if r.get("severity_reason"):
        lines.append("- **Lead 复核**：%s（原评级 %s）" % (r["severity_reason"], r.get("severity_original")))
    lines.append("- **现象**：%s" % (r.get("summary") or ""))
    if r.get("xs"):
        for k, v in r["xs"].items():
            lines.append("- **同根因另见**：`%s` %s:%s — %s" % (k, v.get("file"), v.get("line"), (v.get("title") or "")[:70]))
    rp = r.get("repro_script") or ""
    rd = repro_dir(r["domain"], r["id"])
    if rd:
        lines.append("- **复现物目录**：`03-复现包/%s/`（README / poc / actual-output / fix 四件套）" % rd.split("/", 1)[1])
        lines.append("- **复现命令**：见该目录 `README.md`（含环境要求、可复制命令、期望输出、判定标准）")
    else:
        lines.append("- **复现**：本条为 P3 加固项，未单独产出复现目录；证据与改法见 `02-发现明细/%s.md` 中 `%s` 一节。" % (r["domain"], r["id"]))
    if rd:
        lines.append("- **改进建议**：见同目录 `fix.md`（精确到 文件:行号 + 改后代码 + 迁移风险）")
    else:
        lines.append("- **改进建议**：见 `02-发现明细/%s.md` 中 `%s` 一节的“修复建议”。" % (r["domain"], r["id"]))
    lines.append("- **验收标准**：按 README 复跑一次，判定应由“复现成功”变为“复现失败/被拒绝”；并跑该域 `run_all.py` 确认无新增失败。")
    lines.append("")

(OUT / "05-修复任务单.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")

print(json.dumps({
    "domains_loaded": DOMAINS,
    "raw_records": len(records),
    "merged_into_primary": len(merged_detail),
    "final": len(merged),
    "counts": counts,
}, ensure_ascii=False, indent=1))
