# SH-15 修复建议：用标准库构造邮件、拒绝 CR/LF、净化日志、加锁计数

## 位置

- `cloud/usr/local/sbin/send-mail.py:107-122`（via_smtp）、`:124-130`（日志）、`:51-73`（配额）、`:145-151`（参数解析）
- 调用方 `cloud/var/www/chat-lib/lib.php:331-340`

## 改法（推荐）

### 1) 用 `EmailMessage` 构造，彻底消除头注入；入口处显式拒绝 CR/LF

```diff
-import sys, os, json, time, subprocess, urllib.request, urllib.error
-from email.header import Header
+import sys, os, json, time, subprocess, urllib.request, urllib.error
+from email.message import EmailMessage
+from email.headerregistry import Address
@@
 def via_smtp(to, subj, text):
-    try:
-        subj_enc = Header(subj, 'utf-8').encode()
-    except Exception:
-        subj_enc = subj
-    parts = ['From: ' + FROM, 'To: ' + to, 'Subject: ' + subj_enc,
-             'MIME-Version: 1.0', 'Content-Type: text/plain; charset=UTF-8',
-             'Content-Transfer-Encoding: 8bit', '', text]
+    if any(c in to for c in ("\r", "\n")) or any(c in subj for c in ("\r", "\n")):
+        return False, '非法头字段(CR/LF)'
+    msg = EmailMessage()
+    msg['From'] = FROM
+    msg['To'] = to                       # EmailMessage 会做头编码/折叠
+    msg['Subject'] = subj
+    msg.set_content(text, subtype='plain', charset='utf-8')
+    raw = msg.as_bytes()
     try:
-        p = subprocess.run(['msmtp', '-a', 'exmail', to], input=NL.join(parts).encode('utf-8'),
-                           timeout=40, capture_output=True)
+        p = subprocess.run(['msmtp', '-a', 'exmail', to], input=raw,
+                           timeout=40, capture_output=True)
```
注意：`EmailMessage` 的 `To` 若非法会抛异常，必须 `try/except` 转成“失败返回”，不能崩。

### 2) 参数入口统一校验（脚本可被 sudo/ops 直接调用）

```diff
     if len(args) >= 3:
         to, subj, text = args[0], args[1], args[2]
@@
-    if via == 'resend':
+    # 只允许单个、无控制字符、符合 RFC 5322 的地址
+    if not to or any(c in to for c in "\r\n") or to.count('@') != 1:
+        print('非法收件人'); return 2
+    if via == 'resend':
```

### 3) 日志净化 + 配额加锁

```diff
 def log(m):
     try:
+        m = m.replace('\r', ' ').replace('\n', ' ')
         with open(LOG, 'a') as f:
@@
 def qtencent_bump():
-    q = qload()
-    q['tencent_used'] = int(q.get('tencent_used', 0)) + 1
-    savej(QUOTA_FILE, q)
+    import fcntl
+    os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
+    with open(QUOTA_FILE + '.lock', 'w') as lk:
+        fcntl.flock(lk, fcntl.LOCK_EX)
+        q = qload()
+        q['tencent_used'] = int(q.get('tencent_used', 0)) + 1
+        savej(QUOTA_FILE, q)
```
（`qload/qtencent_raise` 同理；或用 `fcntl.flock` 包住整个 `send_smtp` 的计数段。）

### 4) 明确 SMTP 证书校验（msmtprc 未交付，需要部署侧确认）

```text
# /etc/msmtprc（追加/确认）
tls on
tls_starttls on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
# 禁止：tls_certcheck off
```

## 为什么能堵住这条复现路径

- `EmailMessage` + 显式 CR/LF 拒绝：`To`/`Subject` 里不可能再出现裸换行，注入的头字段会被编码/折叠或直接报错拒绝；
- 入口校验：即使将来新增调用方（面板/API）没做 `FILTER_VALIDATE_EMAIL`，脚本层也拒绝非法地址；
- 日志净化：伪造日志行失效；
- flock：并发发信不再丢计数，`tencent_limit` 提额逻辑不会因竞态膨胀。

## 取舍

- `EmailMessage` 会改变主题编码形式（可能从 quoted-printable 变 base64），收件端显示一致，但若有下游按裸头解析需回归测试。
- 入口只允许单地址：若将来需要一次发多人，应传 `--to-list` 并显式校验每个地址，不要放开单参数。

## 上线风险与回滚

- 风险：邮件是登录验证码通道，改坏会导致用户无法注册/登录。必须先在测试环境用本地 smtp sink 验证 3 类邮件（验证码、通知、--via smtp）都能收到且头正确。
- 回滚：备份 send-mail.py、msmtprc；异常时还原脚本（无需重启服务；PHP 每次 exec 调新进程）。
- 验证：`sudo -u www-data /usr/local/sbin/send-mail.py --via smtp 你的邮箱 "测试" "正文"`；检查日志无换行、配额文件正常递增。
