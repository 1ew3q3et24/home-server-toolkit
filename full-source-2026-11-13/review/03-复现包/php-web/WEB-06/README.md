# WEB-06 复现物 — mcverify 只认 8 位数字码，而真实 code 列存 URL，绑定功能不可用（P2）

## 环境要求
- Windows 本机 Python 3.12；不需要 PHP/MySQL/网络
- 只读 `mcverify/index.php`、`chat/mc-api.php`

## 可复制命令
```powershell
cd D:\Desktop\新建文件夹\work\repro\php-web\WEB-06
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe poc.py
```

## 期望输出
1. `mcverify/index.php:203-213` 的 `$norm = preg_replace('/[^0-9]/','')` + `/^[0-9]{8}$/` + `REPLACE(code,"-","")`；
2. `mc-api.php:62-68`：新行 `$code = $link;`（即 `https://chat.lzj2012.top/v/<12hex>`）；
3. `mc_new_code()` 定义 1 次、调用 0 次（全源码出现 1 次）；
4. 粘贴链接 → `$norm='2012123456'` 长度 10，格式校验 False，直接"格式不对"；
5. 假设的 8 位旧格式 → 在真实 code 列（URL）中无命中 → "找不到验证码"；
6. 末行 `RESULT: 复现通过`。

## 判定标准
`RESULT: 复现通过` 且 `mc_new_code` 调用数为 0、`$code = $link;` 存在。
R3（未执行）真实验证：玩家首次进服拿到 `/v/<token>` 链接，在 mcverify 提交该链接应得到"格式不对"，提交 8 位数字应得到"找不到验证码"。
