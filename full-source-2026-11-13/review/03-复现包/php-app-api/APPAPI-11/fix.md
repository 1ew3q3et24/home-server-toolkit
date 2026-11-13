# APPAPI-11 改进建议（fix）

**适用文件/行号**：`cloud/var/www/chat/mc-api.php:53`（`case 'check'`）；可选 `:25-29`（mc_rate）

## 建议改法

```php
--- a/cloud/var/www/chat/mc-api.php
+++ b/cloud/var/www/chat/mc-api.php
-    if ($isBound && (mt_rand() / mt_getrandmax()) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
+    // 用 CSPRNG 做抽样：random_int(0, 1000000) / 1000000 与 mt_rand 语义等价，但不可预测
+    if ($isBound && (random_int(0, 1000000) / 1000000) > mc_rate()) jout(["ok"=>true,"verify"=>false]);
```

同时建议把默认值从"15% 才验证"改成运营可解释的策略（示例：默认 0.35，并在后台标注
"每次进服重新验证的概率"），并允许 `mc_check_rate=1.0` 表示每次都验证。

## 为什么能堵住复现路径

复现路径是"脚本化进服 -> 观察是否被冻结 -> 重试直到命中 85% 免验证分支"。
换成 CSPRNG 后抽样不可预测；再把默认值调到有实际意义的水平（例如 35%），
脚本化规避的期望尝试次数从 1.2 次升到 ~3 次，配合进服频率限制才具备反滥用价值。

## 取舍说明

- 方案 A（推荐）：`random_int` 替换 `mt_rand`。1 行改动、零兼容风险，修掉"错误随机源"这一确定性问题。
- 方案 B：保持 mt_rand，仅调高 rate。随机源问题仍在（可预测），只提高成本。
- 方案 C：改为"每 N 次进服强制验证一次"的确定性策略（基于 DB 计数）。可解释性最好，但需要新增计数列/表，改动大。

## 兼容性 / 迁移风险

- `random_int` 是 PHP 7+ 内建，性能略低于 mt_rand（每请求一次，可忽略）。
- 修改 mc_check_rate 默认值会影响玩家体验（更多验证），属于产品决策，需要公告。
- 无 schema 变更。
