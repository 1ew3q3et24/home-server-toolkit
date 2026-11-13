# WEB-07 复现物 — mcverify 绑定"先查后改"无事务/无行锁：同一 code 并发可被两个账号使用（P2）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/MySQL/网络
- 只读 `mcverify/index.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-07
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. 打印 `mcverify/index.php:208-224`：SELECT → SELECT owner → INSERT → UPDATE，无 `BEGIN/COMMIT`、无 `FOR UPDATE`、UPDATE 无 `WHERE submitted_at IS NULL`；
2. 三个交错点（读码 / 查归属 / 写入前）用 `threading.Barrier` 强制两请求同时通过；
3. 一次运行内出现 `账号A=ok, 账号B=ok, mc_bindings=[(2,'Notch'),(1,'Notch')]`；
4. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且 `mc_bindings` 出现两条同名记录。
注意：真实环境成败取决于 `mc_bindings.mc_name` 是否有 UNIQUE 索引（bundle 未附 schema）——因此"高可能"而非"确认"；若有 UNIQUE，则表现为第二个请求 500（仍是错误处理缺陷）。
