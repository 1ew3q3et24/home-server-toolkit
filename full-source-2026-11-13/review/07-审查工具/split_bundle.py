import re, pathlib, hashlib, json

SRC = pathlib.Path(r"E:\Downloads\combined-code-bundle (2).md")
OUT = pathlib.Path(r"D:\Desktop\新建文件夹\work\src")

raw = SRC.read_bytes()
lines = raw.split(b"\n")

declared = {}
tbl_re = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*`([0-9a-f]{64})`\s*\|")
for ln in lines:
    try:
        s = ln.decode("utf-8")
    except UnicodeDecodeError:
        continue
    m = tbl_re.match(s)
    if m:
        declared[m.group(1)] = (int(m.group(2)), m.group(3))

head_re = re.compile(r"^### `(.+?)`$")
seen = []
records = []
for idx, ln in enumerate(lines):
    try:
        s = ln.decode("utf-8")
    except UnicodeDecodeError:
        continue
    m = head_re.match(s)
    if not m:
        continue
    name = m.group(1)
    # opening fence is the next line that starts with 4 backticks
    j = idx + 1
    while j < len(lines) and not lines[j].startswith(b"````"):
        j += 1
    opener = lines[j]
    body_start = j + 1
    k = body_start
    while k < len(lines) and not lines[k].startswith(b"````"):
        k += 1
    body = b"\n".join(lines[body_start:k]) + b"\n"
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    seen.append(name)
    d = declared.get(name)
    h = hashlib.sha256(body).hexdigest()
    records.append({
        "file": name, "bytes_declared": d[0] if d else None, "bytes_extracted": len(body),
        "sha256_declared": d[1] if d else None, "sha256_extracted": h,
        "status": "OK" if d and h == d[1] else "MISMATCH",
        "opener": opener.decode("utf-8", "replace"),
    })

non_utf8 = []
for name in seen:
    b = (OUT / name).read_bytes()
    try:
        b.decode("utf-8")
    except UnicodeDecodeError as e:
        non_utf8.append(name)

print(json.dumps({
    "extracted": len(seen),
    "declared": len(declared),
    "missing_from_source": [k for k in declared if k not in seen],
    "missing_from_table": [k for k in seen if k not in declared],
    "mismatch": [r["file"] for r in records if r["status"] != "OK"],
    "non_utf8_files": non_utf8,
}, ensure_ascii=False, indent=1))
pathlib.Path(r"D:\Desktop\新建文件夹\work\manifest_check.json").write_text(
    json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
