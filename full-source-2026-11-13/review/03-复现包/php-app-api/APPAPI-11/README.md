# APPAPI-11 [P3] mc-api 概率闸门使用 mt_rand()（非密码学 PRNG），且默认 15% 使 85% 进服免验证

- 级别：P3 低
- 类别：加密误用 / 逻辑缺陷（反滥用强度不足）
- 可信度：确认（源码事实）；可预测性的实际利用强度待真实环境评估
- 复现级别：R2（源码与概率静态证明；poc.py 输出核对结果与概率）

## 环境要求

- 本机：Windows + Python 3.12（BRIEF 指定解释器）。
- 无需 PHP：脚本读取 mc-api.php 做核对并计算概率。
- 端到端（R3）需要：测试部署 + 多次进服观察抽样结果。

## 运行命令

在本机（Windows）执行：

```
cd D:\Desktop\新建文件夹
python work\repro\php-app-api\APPAPI-11\poc.py
```

本机解释器路径（BRIEF 指定）：

```
C:\Users\18012\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe work\repro\php-app-api\APPAPI-11\poc.py
```

无需 PHP / MySQL / nginx；脚本只用 Python 标准库。若 `work/src` 不存在，脚本会自动跳过"源码核对"部分。

## 期望输出（关键行）

```
== 1) 源码核对
   mc_rate 默认值 0.15: True
   check 使用 mt_rand(): True
   check 使用 random_int()/random_bytes(): False
== 2) 概率与可预测性
   mc_check_rate = 0.15 -> 每次进服有 15% 概率被要求重新验证，
   85% 概率直接 verify=false 放行（对已绑定账号）。
...
RESULT: PASS
```

## 判定标准

退出码 **0** 且输出中 `check 使用 mt_rand(): True`、`check 使用 random_int()/random_bytes(): False`，并给出 85% 放行概率。

## 实际输出

见同目录 `actual-output.txt`（本机真实运行结果，命令即上文）。

## 完整端到端（真实环境 / R3，未在本机执行）

在**自有测试环境**（不要对生产执行）：

1. 绑定一个测试 MC 名，连续 100 次让插件调用 `check`（脚本或反复进服），统计返回 `verify:false` 的比例，
   期望约 85%（默认 mc_check_rate=0.15）。
2. 把 `mc_check_rate` 设为 1.0（全量验证）后再测，期望每次都被冻结 —— 说明闸门强度由该配置决定。
3. 修复后改用 `random_int(0, 1000000)/1000000`，统计行为不变但随机源改为 CSPRNG。
