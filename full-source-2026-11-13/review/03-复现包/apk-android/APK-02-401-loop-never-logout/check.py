# -*- coding: utf-8 -*-
"""APK-02 复现检查：WatchService 的 401 处理分支不可达。

语义等价模型：逐行翻译 WatchService.loop()（41-58）与 Api.req()/waitSse()（33-63、102-125）
的异常传播路径，用“服务端返回 401”的桩替代真实 HTTP。
等价性前提：Api.req 对 401 且 JSON ok=false 抛 ApiException(error, 401)；
waitSse 对 HTTP!=200 抛 ApiException("SSE "+code)（不带 status）。
本机无 Android 运行时，未执行任何网络请求。
"""
import pathlib
import sys

ID = "APK-02"
TITLE = "401 处理失效：令牌吊销后永不登出，陷入无限轮询"
WS = "apk/src/java/top/lzj2012/toolbox/WatchService.java"
API = "apk/src/java/top/lzj2012/toolbox/Api.java"


def read(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


def ln_of(lines, needle):
    for i, s in enumerate(lines, 1):
        if needle in s:
            return i
    return None


class ApiException(Exception):
    def __init__(self, msg, status=0):
        super().__init__(msg)
        self.status = status


# ---- 服务端桩（与 app-wait.php/app-api.php 实测格式一致）----
def server_wait_poll():          # 20s 长轮询：token 已吊销 => HTTP 401 + {"ok":false,...}
    raise ApiException("登录已失效，请重新登录", 401)


def server_wait_sse():           # SSE：HTTP 401，被 Api.waitSse 转成 "SSE 401"
    raise ApiException("SSE 401", 0)


def server_pending():            # mc_pending：HTTP 401
    raise ApiException("未登录", 401)


# ---- WatchService.loop() 的等价翻译（WatchService.java:41-58）----
def watch_loop(max_iters=5):
    log = []
    requests = 0
    broke = False
    for i in range(max_iters):
        try:
            try:
                requests += 1
                server_wait_poll()          # j = Api.waitPoll(token, lastSig, 20);
            except Exception:               # catch (Exception e1) { j = Api.waitSse(...) }
                requests += 1
                server_wait_sse()           # 401 在这里被“吞掉”并降级为 SSE
        except ApiException as e:           # 外层 catch (Exception e)
            log.append("iter%d: 外层捕获 status=%d msg=%s" % (i, e.status, e))
            if e.status == 401:             # ← 永远不成立
                log.append("iter%d: status==401 → Prefs.clear + showLoginExpired + break" % i)
                broke = True
                break
            try:
                requests += 1
                server_pending()            # handle(Api.pending(token))
            except Exception:
                pass
            log.append("iter%d: 未识别 401 → sleep(5000) 后继续" % i)
    return broke, requests, log


def run(src=None):
    if src is None:
        src = pathlib.Path(__file__).resolve().parents[2] / "src"
    src = pathlib.Path(src)
    ws = read(src / WS)
    api = read(src / API)
    out = []
    ok = True

    def check(cond, desc, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        out.append("%s | %s%s" % ("PASS" if cond else "FAIL", desc,
                                  ("  [" + detail + "]") if detail else ""))

    # 代码结构断言：证明翻译忠实
    poll = ln_of(ws, "j = Api.waitPoll(token, lastSig, 20);")
    sse = ln_of(ws, "j = Api.waitSse(token, lastSig);")
    check(poll == 43 and sse == 45,
          "waitPoll 的异常被内层 catch 吞掉并直接转 SSE（WatchService.java:42-46）",
          "WatchService.java:43,45")
    check(ln_of(ws, "((Api.ApiException) e).status == 401") == 51,
          "外层只有看到 status==401 才会登出/退出", "WatchService.java:51")
    check(ln_of(api, 'throw new ApiException("SSE " + code);') == 109,
          "waitSse 抛 ApiException 时未传 HTTP 状态码 → status 恒为 0", "Api.java:109")
    check(ln_of(api, "public ApiException(String m, int s) { super(m); status = s; }") == 30,
          "ApiException 只有带 int 的构造才写 status（默认 0）", "Api.java:30")

    broke, requests, log = watch_loop(5)
    check(broke is False, "5 轮模拟内 401 分支从未触发（令牌吊销不会被感知）")
    check(requests >= 15, "同一时间窗仍继续发出无效请求", "5 轮共 %d 次请求" % requests)

    status = "复现通过" if ok and not broke else "复现失败"
    text = "\n".join([
        "[%s] %s" % (ID, TITLE),
        "复现级别: R1（本地可执行的语义等价模型；纯逻辑推演，不联网）",
        "环境: Windows + Python 3.12；无 Android SDK/模拟器",
        "模型来源: %s:41-58, %s:102-125（逐行等价翻译）" % (WS, API),
    ] + out + [
        "模拟轨迹:",
    ] + ["  " + s for s in log] + [
        "结论: %s" % status,
        "影响: 服务端 reset 改密/设备吊销后(sessions_valid_after)，APP 继续每 ~5s~60s 轮询一次，"
        "不清理 Keystore 中的死令牌、不提示“登录已过期”，常驻前台服务持续耗电/耗流量。",
    ])
    return {"id": ID, "title": TITLE, "status": status, "ok": (ok and not broke), "text": text}


if __name__ == "__main__":
    r = run()
    print(r["text"])
    sys.exit(0 if r["ok"] else 1)
