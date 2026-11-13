# MCG-03 修复建议

**P1 · MCG-03** — 后端响应无签名/无 nonce, 共享密钥单向明文 => 可伪造解锁

## 修改点
### 1) `Backend.java:33-49` —— 请求签名 + 响应签名 + 防重放
```java
private static final SecureRandom RND = new SecureRandom();

private static String hex(byte[] b) { StringBuilder s = new StringBuilder(); for (byte x : b) s.append(String.format("%02x", x)); return s.toString(); }

private static byte[] hmac(String key, String msg) throws Exception {
    Mac mac = Mac.getInstance("HmacSHA256");
    mac.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
    return mac.doFinal(msg.getBytes(StandardCharsets.UTF_8));
}

/** Java 里等价于 PHP hash_equals 的常量时间比较; String.equals 会在首个不同字节短路。 */
private static boolean constEq(byte[] a, byte[] b) { return MessageDigest.isEqual(a, b); }

private JsonObject call(String action, JsonObject body) throws Exception {
    String url = baseUrl() + "?action=" + action;
    String ts = Long.toString(System.currentTimeMillis() / 1000);
    byte[] nonceB = new byte[16]; RND.nextBytes(nonceB);
    String nonce = hex(nonceB);
    String payload = body == null ? "" : body.toString();
    String canon = "v1\n" + action + "\n" + ts + "\n" + nonce + "\n" + hex(sha256(payload));
    String sig = hex(hmac(secret(), canon));
    HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
            .timeout(Duration.ofMillis(timeout()))
            .header("X-MC-Ts", ts)
            .header("X-MC-Nonce", nonce)
            .header("X-MC-Sig", sig)
            .header("User-Agent", "McGate/0.3");
    ...
    HttpResponse<String> resp = http.send(...);
    if (resp.statusCode() != 200) throw new RuntimeException("HTTP " + resp.statusCode());
    // 响应签名: HMAC(secret, ts + "\n" + nonce + "\n" + sha256(responseBody))
    String want = hex(hmac(secret(),
            "v1\n" + ts + "\n" + nonce + "\n" + hex(sha256(resp.body()))));
    String got = resp.headers().firstValue("X-MC-Resp-Sig").orElse("");
    if (!constEq(want.getBytes(UTF_8), got.getBytes(UTF_8))) throw new IOException("响应签名不合法");
    if (Math.abs(System.currentTimeMillis() / 1000 - Long.parseLong(ts)) > 60) throw new IOException("响应过期");
    ...
}
```

### 2) `Backend.java:28` + `config.yml:4` —— 强制 HTTPS 与主机白名单
```java
private String baseUrl() {
    String u = plugin.getConfig().getString("backend.base-url", "");
    if (u == null || !u.startsWith("https://")) {
        throw new IllegalStateException("backend.base-url 必须以 https:// 开头");
    }
    return u;
}
```
可选: `HttpClient.newBuilder().sslContext(...)` 做证书/公钥固定(注意 CA 轮换运维成本),
或至少在 config.yml 注释里写明"该域名必须走 Cloudflare 全严格模式 + 不得改为 http"。

### 3) `config.yml:6` + 部署
```yaml
backend:
  secret: "<REDACTED>"   # 部署时写入; 通过环境变量/受限权限文件注入, 不要留在可读配置里
```
建议启动时校验 `secret` 非空且 != "<REDACTED>", 否则拒绝启用并告警(fail-close)。

## 为什么能堵住
修复后, 响应必须携带用共享密钥对 (action, ts, nonce, 响应体) 计算的 HMAC; 中间人/CDN/
被改的后端无法伪造, 旧响应因 nonce 不匹配也无法重放。同时 https 强制 + 常量时间比较消除
明文传输与时序侧信道。

## 兼容 / 迁移风险
* 需要后端 mc-api.php 同步实现同样的签名算法, 属跨端协议升级: 建议先用 `X-MC-Sig`
  可选(缺失时告警)灰度, 再强制; 或提供 `backend.require-signature: true/false` 开关。
* 若在 Cloudflare 后面, 自定义请求头可透传; 但要关闭可能改写响应头的规则。
* 签名/校验失败必须 fail-close(配合 MCG-01 的修复), 不能"校验失败就放行"。

## 修复后验证
- 复跑本目录 `poc.py`: 期望不再输出 `RESULT: VULNERABLE`(或输出中漏洞场景数下降);
- 真机/真库回归: 按 README 的判定标准重跑对应场景。
