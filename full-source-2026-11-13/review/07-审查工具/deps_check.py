import re, pathlib, json, sys

SRC = pathlib.Path(r"D:\Desktop\新建文件夹\work\src")
files = {str(p.relative_to(SRC)).replace("\\", "/"): p for p in SRC.rglob("*") if p.is_file()}
byname = {}
for rel, p in files.items():
    byname.setdefault(p.name, []).append(rel)

texts = {}
for rel, p in files.items():
    try:
        texts[rel] = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        texts[rel] = ""

# 1) PHP require/include 的绝对路径
refs = {}
for rel, t in texts.items():
    if not rel.endswith(".php"):
        continue
    for m in re.finditer(r"(?:require|include)(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", t):
        refs.setdefault(m.group(1), set()).add(rel)

# 2) 页面内引用的同站相对资源
assets = {}
for rel, t in texts.items():
    if not rel.endswith((".php", ".js", ".html")):
        continue
    for m in re.finditer(r'(?:src|href)\s*=\s*["\'](/[^"\'?#]+)', t):
        u = m.group(1)
        if u.startswith("//"):
            continue
        assets.setdefault(u, set()).add(rel)
    for m in re.finditer(r"fetch\(['\"](/[^'\"]*)['\"]", t):
        assets.setdefault(m.group(1), set()).add(rel)

# 3) 前端脚本里引用的 .js 文件名
jsrefs = {}
for rel, t in texts.items():
    for m in re.finditer(r"['\"]([A-Za-z0-9_\-]+\.js)(?:\?v=\d+)?['\"]", t):
        jsrefs.setdefault(m.group(1), set()).add(rel)

missing_php, present_php = [], []
for path, who in sorted(refs.items()):
    if not path.startswith("/"):
        continue
    rel = path.lstrip("/")
    # 映射 /var/www/chat-lib/x.php -> cloud/var/www/chat-lib/x.php
    cand = "cloud" + path
    if cand.lstrip("cloud") and (SRC / cand.lstrip("/")).exists():
        present_php.append((path, sorted(who)))
    else:
        missing_php.append((path, sorted(who)))

missing_assets = []
for u, who in sorted(assets.items()):
    name = u.strip("/").split("/")[-1]
    if name and name not in byname:
        missing_assets.append((u, sorted(who)))
    elif name in byname and byname[name][0].split("/")[-2:] != u.strip("/").split("/")[-2:]:
        missing_assets.append((u + "  (名称存在但路径不一致: " + ",".join(byname[name]) + ")", sorted(who)))

missing_js = [(j, sorted(who)) for j, who in sorted(jsrefs.items()) if j not in byname or not any(r.endswith(j) for r in byname.get(j, []))]

print("== 被 require/include 但包内缺失的 PHP 绝对路径 ==")
for p, who in missing_php:
    print(" ", p, "<-", ", ".join(who))
print("\n== 页面引用但包内缺失的同站资源 ==")
for p, who in missing_assets:
    print(" ", p, "<-", ", ".join(who))
print("\n== 引用但缺失的 JS 文件名 ==")
for p, who in missing_js:
    print(" ", p, "<-", ", ".join(who))
print("\n== 包内存在的 PHP lib 引用（已核对） ==")
for p, who in present_php:
    print(" ", p, "<-", ", ".join(who))
