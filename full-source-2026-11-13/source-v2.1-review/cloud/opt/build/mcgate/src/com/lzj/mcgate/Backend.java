package com.lzj.mcgate;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.bukkit.plugin.java.JavaPlugin;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

/** 与聊天室后端的 HTTP 通信 (只用 JDK 自带 HttpClient + 服务端自带 Gson) */
public class Backend {

    private final JavaPlugin plugin;
    private final HttpClient http;

    public Backend(JavaPlugin plugin) {
        this.plugin = plugin;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(8000)).build();
    }

    private String baseUrl() { return plugin.getConfig().getString("backend.base-url", ""); }
    private String secret() { return plugin.getConfig().getString("backend.secret", ""); }
    private int timeout() { return plugin.getConfig().getInt("backend.timeout-ms", 8000); }
    public boolean failOpen() { return plugin.getConfig().getBoolean("backend.fail-open", true); }

    private JsonObject call(String action, JsonObject body) throws Exception {
        String url = baseUrl() + "?action=" + action;
        HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofMillis(timeout()))
                .header("X-MC-Secret", secret())
                .header("User-Agent", "McGate/0.2");
        if (body == null) {
            b.GET();
        } else {
            b.header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(body.toString()));
        }
        HttpResponse<String> resp = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
        if (resp.statusCode() != 200) throw new RuntimeException("HTTP " + resp.statusCode());
        JsonElement el = JsonParser.parseString(resp.body());
        if (!el.isJsonObject()) throw new RuntimeException("bad json");
        return el.getAsJsonObject();
    }

    /** 询问后端: 这个玩家需要验证吗? 需要则返回验证码 */
    public CheckResult check(String name) {
        try {
            JsonObject body = new JsonObject();
            body.addProperty("name", name);
            JsonObject r = call("check", body);
            CheckResult cr = new CheckResult();
            cr.needVerify = r.has("verify") && r.get("verify").getAsBoolean();
            cr.needTos = r.has("need_tos") && r.get("need_tos").getAsBoolean();
            if (r.has("code") && !r.get("code").isJsonNull()) cr.code = r.get("code").getAsString();
            if (r.has("link") && !r.get("link").isJsonNull()) cr.link = r.get("link").getAsString();
            if (r.has("expires_in")) cr.expiresIn = r.get("expires_in").getAsInt();
            cr.ok = true;
            return cr;
        } catch (Exception e) {
            plugin.getLogger().warning("后端 check 失败: " + e);
            CheckResult cr = new CheckResult();
            cr.ok = false;
            cr.needVerify = !failOpen();
            return cr;
        }
    }

    /** 询问后端: 这些已绑定的玩家里, 哪些已经同意了用户协议 */
    public List<String> tosCheck(List<String> names) {
        List<String> out = new ArrayList<>();
        if (names == null || names.isEmpty()) return out;
        try {
            JsonObject body = new JsonObject();
            JsonArray arr = new JsonArray();
            for (String n : names) arr.add(n);
            body.add("names", arr);
            JsonObject r = call("tos_check", body);
            if (r.has("agreed") && r.get("agreed").isJsonArray()) {
                for (JsonElement e : r.getAsJsonArray("agreed")) {
                    if (e.isJsonPrimitive()) out.add(e.getAsString());
                }
            }
        } catch (Exception e) {
            plugin.getLogger().warning("后端 tos_check 失败: " + e);
        }
        return out;
    }

    /** 取回"已通过验证、等待解锁"的名字 */
    public List<String> pending() {
        List<String> out = new ArrayList<>();
        try {
            JsonObject r = call("pending", null);
            if (r.has("unlocks") && r.get("unlocks").isJsonArray()) {
                JsonArray arr = r.getAsJsonArray("unlocks");
                for (JsonElement e : arr) {
                    if (e.isJsonObject() && e.getAsJsonObject().has("name")) {
                        out.add(e.getAsJsonObject().get("name").getAsString());
                    }
                }
            }
        } catch (Exception e) {
            plugin.getLogger().warning("后端 pending 失败: " + e);
        }
        return out;
    }

    /** 告诉后端: 这些名字已经解锁完毕 */
    public void ack(List<String> names) {
        try {
            JsonObject body = new JsonObject();
            JsonArray arr = new JsonArray();
            for (String n : names) arr.add(n);
            body.add("names", arr);
            call("ack", body);
        } catch (Exception e) {
            plugin.getLogger().warning("后端 ack 失败: " + e);
        }
    }

    public static class CheckResult {
        public boolean ok;
        public boolean needVerify;
        public boolean needTos;
        public String code;
        public String link;
        public int expiresIn = 300;
    }
}
