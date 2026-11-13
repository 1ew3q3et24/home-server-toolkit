# APK-02 复现说明：401 处理分支不可达（令牌吊销后无限轮询）

- **finding**：`APK-02`（P2，逻辑缺陷）
- **复现级别**：R1（本地可执行的语义等价模型）
- **关联位置**：`apk/src/java/top/lzj2012/toolbox/WatchService.java:41-58`；
  `apk/src/java/top/lzj2012/toolbox/Api.java:27-31,102-125`

## 环境要求

- 仅需 Python 3.8+（本机 3.12），无需 Android SDK/模拟器/网络。
- 模型是 WatchService 循环与 Api 异常传播的逐行等价翻译，桩函数模拟服务端在令牌吊销后返回
  `app-wait.php:19,24` 的 `HTTP 401`（真实服务器行为，见源码，不需要实际请求）。

## 一条可复制命令

```bash
"C:/Users/18012/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe" \
  "D:/Desktop/新建文件夹/work/repro/apk-android/APK-02-401-loop-never-logout/check.py"
```

## 期望输出（关键行）

```
PASS | waitPoll 的异常被内层 catch 吞掉并直接转 SSE（WatchService.java:42-46）  [WatchService.java:43,45]
PASS | 外层只有看到 status==401 才会登出/退出  [WatchService.java:51]
PASS | waitSse 抛 ApiException 时未传 HTTP 状态码 → status 恒为 0  [Api.java:109]
PASS | 5 轮模拟内 401 分支从未触发（令牌吊销不会被感知）
PASS | 同一时间窗仍继续发出无效请求  [5 轮共 15 次请求]
结论: 复现通过
```

判定标准：
1. 4 条代码结构断言全部 PASS（证明模型与服务端行为等价）；
2. 5 轮模拟中 `broke is False` 且请求次数 ≥ 15 → “401 分支不可达”成立。

## 为什么必然不可达（数据流）

```
waitPoll()  ──401──► 内层 catch(Exception e1) 吞掉 ──► waitSse()
waitSse()   ──401──► throw ApiException("SSE 401")     // status 默认 0
外层 catch  ──status==401? ──► 否 ──► handle(Api.pending()) 也 401 被 ignore ──► sleep(5000) ──► 继续
```

即：**能进入外层 catch 的 401 只可能来自 waitPoll，而 waitPoll 的异常已被内层吞掉**；
waitSse 的 401 又丢失了状态码。两条路径都不满足 `status == 401`，故死代码。

## 真机验证（R3，**未在本机执行**）

```bash
# 前置：APP 已登录；在网页端“设备管理”吊销该设备（或管理员 reset 改密）
# 观察：APP 仍每 5~60 秒打一次 app-wait.php，永不回到登录页，通知栏常驻
adb logcat -s LZJ:* | grep -i wait        # （现版本无日志，可用抓包/代理观察请求）
adb shell dumpsys activity services top.lzj2012.toolbox | grep -i watch
```

判定标准：吊销后 10 分钟仍未出现“登录已过期”通知、且服务未停止 → 复现成功。

## 未执行说明

本机 Windows 桌面，无 Android SDK/模拟器/adb，不能安装运行 APK；因此只执行了
R1 等价模型（断言全部通过，见 `actual-output.txt`）。R3 需真机 + 网页端吊销操作。
按红线要求未向任何真实主机发起请求。
