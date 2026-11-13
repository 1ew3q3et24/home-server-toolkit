# WEB-08 复现物 — mcverify 用 innerHTML 拼接未转义的 mc_name（DOM XSS 汇聚点，P3）

## 环境要求
- Windows 本机 Python 3.12（标准库 `html.parser`）；不需要 PHP/浏览器/网络
- 只读 `mcverify/index.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-08
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. 打印 `mcverify/index.php:465-469`：`box.innerHTML = j.items.map(...)`，`it.mc_name` 直接拼入；
2. 同文件无 `escapeHtml`/`DOMPurify`；同页另一处昵称使用 `htmlspecialchars`（line 381）——证明不是全局约定；
3. 渲染字符串中出现 `</div><img src=x onerror=alert(document.domain)>`；
4. `html.parser` 解析后生成 `<img src="x" onerror="alert(document.domain)">`（`是否生成带 onerror 的 <img> = True`）；
5. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且解析结果中存在 `img` + `onerror` 属性。
触发前提（报告中已注明）：`mc_codes.mc_name` 含 HTML 字符，即游戏服务端/代理允许 `[A-Za-z0-9_]` 之外的角色名（`mc-api.php:45` 只校验 `strlen<=32`），且该行的 `user_id` 属于当前浏览者。
