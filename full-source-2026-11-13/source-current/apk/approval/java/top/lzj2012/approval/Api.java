package top.lzj2012.approval;

import android.os.Build;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;

public class Api {
    static final String API = "https://chat.lzj2012.top/app-api.php?action=";
    static final String WAIT = "https://chat.lzj2012.top/app-wait.php";

    public static class Pending {
        public int id;
        public String name;
        public String code;
        public int ttl;
    }

    public static class ApiException extends Exception {
        public ApiException(String m) { super(m); }
    }

    static JSONObject req(String url, String method, String body, String token, int timeoutMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(timeoutMs);
        c.setRequestMethod(method);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestProperty("User-Agent", "LZJApproval/1.11.2 (Android " + Build.VERSION.SDK_INT + ")");
        if (token != null && !token.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + token);
        if (body != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=utf-8");
            OutputStream os = c.getOutputStream();
            os.write(body.getBytes("UTF-8"));
            os.close();
        }
        int code = c.getResponseCode();
        InputStream is = (code >= 200 && code < 300) ? c.getInputStream() : c.getErrorStream();
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        if (is != null) {
            byte[] b = new byte[4096];
            int n;
            while ((n = is.read(b)) > 0) bo.write(b, 0, n);
            is.close();
        }
        c.disconnect();
        String s = bo.toString("UTF-8");
        JSONObject j;
        try { j = new JSONObject(s); } catch (Exception e) { throw new ApiException("服务器返回异常"); }
        if (!j.optBoolean("ok", false)) throw new ApiException(j.optString("error", "请求失败"));
        return j;
    }

    static String enc(String s) {
        try { return URLEncoder.encode(s == null ? "" : s, "UTF-8"); } catch (Exception e) { return ""; }
    }

    public static JSONObject login(String email, String pass, String label) throws Exception {
        String body = "email=" + enc(email) + "&password=" + enc(pass) + "&label=" + enc(label);
        return req(API + "app_login", "POST", body, "", 12000);
    }

    public static List<Pending> pending(String token) throws Exception {
        JSONObject j = req(API + "mc_pending", "GET", null, token, 12000);
        JSONArray a = j.optJSONArray("pending");
        List<Pending> out = new ArrayList<>();
        if (a != null) for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.getJSONObject(i);
            Pending p = new Pending();
            p.id = o.optInt("id");
            p.name = o.optString("mc_name");
            p.code = o.optString("code");
            p.ttl = o.optInt("ttl");
            out.add(p);
        }
        return out;
    }

    public static void approve(String token, int id) throws Exception {
        req(API + "mc_approve", "POST", "id=" + id, token, 12000);
    }

    public static void deny(String token, int id) throws Exception {
        req(API + "mc_deny", "POST", "id=" + id, token, 12000);
    }

    public static JSONObject waitPoll(String token, String last, int timeoutSec) throws Exception {
        return req(WAIT + "?mode=longpoll&last=" + enc(last), "GET", null, token, (timeoutSec + 8) * 1000);
    }

    public static JSONObject waitSse(String token, String last) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(WAIT + "?mode=sse&last=" + enc(last)).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(60000);
        c.setRequestProperty("Accept", "text/event-stream");
        c.setRequestProperty("Authorization", "Bearer " + token);
        int code = c.getResponseCode();
        if (code != 200) { c.disconnect(); throw new ApiException("SSE " + code); }
        java.io.BufferedReader r = new java.io.BufferedReader(
                new java.io.InputStreamReader(c.getInputStream(), "UTF-8"));
        try {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.startsWith("data: ")) {
                    JSONObject j = new JSONObject(line.substring(6));
                    c.disconnect();
                    return j;
                }
            }
        } finally {
            try { r.close(); } catch (Exception ignored) {}
        }
        c.disconnect();
        throw new ApiException("SSE closed");
    }

    public static List<Pending> parse(JSONObject j) {
        List<Pending> out = new ArrayList<>();
        JSONArray a = j.optJSONArray("pending");
        if (a == null) return out;
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o == null) continue;
            Pending p = new Pending();
            p.id = o.optInt("id");
            p.name = o.optString("mc_name");
            p.code = o.optString("code");
            p.ttl = o.optInt("ttl");
            out.add(p);
        }
        return out;
    }
}
