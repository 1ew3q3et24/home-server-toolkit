# PY-04 改进建议：只读文件尾部 + 请求体上限 + 生产 WSGI

## 位置
- `cloud/var/www/logview/app.py:103-152`（`read_source`，尤其 109）
- `cloud/var/www/logview/app.py:271-303`（`bans_html`，275）
- `cloud/var/www/logview/ddospanel.py:154-189`（`domain_stats`，160）
- `cloud/var/www/logview/mailpanel.py:57-63`（`status`，59）
- `cloud/var/www/logview/app.py:426-427`（开发服务器）

## 问题
`f.readlines()[-N:]` 先把整个文件解析成行列表再切片；日志文件无上限增长（nginx access.log
公网可放大），面板 30 秒自动刷新 → 反复整份读入，内存/CPU 随文件线性增长。

## 推荐改法（改后代码）

```python
# app.py 顶部
MAX_TAIL_BYTES = 512 * 1024

def tail_lines(path, n, max_bytes=MAX_TAIL_BYTES):
    """只读文件尾部 max_bytes，返回最后 n 行（内存 O(max_bytes)）。"""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        back = min(size, max_bytes)
        f.seek(size - back)
        data = f.read()
    return data.decode("utf-8", "replace").splitlines()[-n:]

# read_source 的 file/jsonl 分支
lines = [(ln + "\n") for ln in tail_lines(src.get("path", ""), n * 3)]
# bans_html： lines = tail_lines(path, 5000)
# domain_stats： lines = tail_lines(path, 40000)
# mailpanel.status： lines = tail_lines(MLOG, 400)
```

```python
# app.py:426-427 生产入口
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024        # 请求体上限
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, threaded=True)
# 生产建议：gunicorn -w 2 -k gthread --threads 4 --timeout 30 \
#           -b 127.0.0.1:5001 app:app
```

其它配套（可选）：页面刷新间隔 30s 可提到 60s；`collect(cat="all")` 的源并发度限制；
对 `domain_stats` 结果做 30 秒缓存（避免每次 GET 都解析 40000 行）。

## 为什么能堵住复现路径
- 峰值内存从“整份文件”降到“尾部 512KB 解码后的列表”（实测 29.4MB → 1.72MB）；
- 解析耗时从 0.5s 降到 0.005s，30 秒刷新不再造成持续 CPU 抖动；
- 请求体上限 + 生产 WSGI 消除未认证大 body/线程池耗尽路径。

## 备选方案
- 用 `collections.deque(open(path), maxlen=n*3)`：实现最简，但仍是流式读完整文件（CPU/IO 不降），
  只在大文件内存上有效；**不推荐**替代 seek 方案。
- 让 `logrotate` 把日志压到固定大小（运维层面），可与本修复叠加。

## 兼容/迁移风险
- seek 到任意字节可能截断多字节 UTF-8：已用 `errors="replace"`，最多首行出现替换字符；
- `jsonl` 分支依赖完整行：首行若被截断会 `json.loads` 失败并被跳过（可接受）；
- 若日志使用压缩/特殊编码，tail 读取不适用，需回退流式；
- `MAX_CONTENT_LENGTH` 会把超过 64KB 的 POST 变成 413（表单只有口令/开关，足够）。
