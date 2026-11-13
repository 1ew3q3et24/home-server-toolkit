package top.lzj2012.toolbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;

/** 云端 OTA：检查 latest.json -> 下载 -> SHA-256/签名校验 -> 系统安装器 */
public class UpdateManager {
    private static final String LATEST = "https://download.lzj2012.top/apk/latest.json";
    private static volatile boolean checking = false;
    private static volatile File pendingInstall = null;
    private static volatile int notifiedCode = 0;

    public static int versionCode(Context c) {
        try {
            return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionCode;
        } catch (Exception e) {
            return 0;
        }
    }

    public static String versionName(Context c) {
        try {
            return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "?";
        }
    }

    /** 服务端通过审批推送通道下发 OTA 信息时调用 */ public static void notifyIfNew(Context c, JSONObject o) {
        if (o == null) return;
        int code = o.optInt("versionCode", 0);
        if (code <= versionCode(c) || code <= notifiedCode) return;
        notifiedCode = code;
        Notifier.showUpdate(c, o.optString("versionName", ""), o.optString("notes", ""));
    }

    static File apkFile(Context c) {
        return new File(new File(c.getCacheDir(), "ota"), "update.apk");
    }

    public static void check(final Activity act, final boolean manual) {
        if (checking) return;
        checking = true;
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    JSONObject j = fetch(act);
                    final int remoteCode = j.optInt("versionCode", 0);
                    final String remoteName = j.optString("versionName", "");
                    final String url = j.optString("url", "");
                    final String sha = j.optString("sha256", "").toLowerCase();
                    final String notes = j.optString("notes", "");
                    int cur = versionCode(act);
                    if (remoteCode <= cur) {
                        if (manual) toast(act, "已是最新版本 v" + versionName(act));
                        return;
                    }
                    if (!url.startsWith("https://")) throw new Exception("更新地址不是 HTTPS");
                    if (sha.length() != 64) throw new Exception("更新清单缺少 SHA-256");
                    act.runOnUiThread(new Runnable() {
                        @Override public void run() { prompt(act, remoteCode, remoteName, url, sha, notes); }
                    });
                } catch (Exception e) {
                    if (manual) toast(act, "检查更新失败：" + e.getMessage());
                } finally {
                    checking = false;
                }
            }
        }, "ota-check").start();
    }

    private static JSONObject fetch(Context c) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(LATEST + "?t=" + System.currentTimeMillis()).openConnection();
        conn.setConnectTimeout(8000);
        conn.setReadTimeout(10000);
        conn.setRequestProperty("User-Agent", "LZJToolbox/" + versionName(c));
        conn.setRequestProperty("Cache-Control", "no-cache");
        int code = conn.getResponseCode();
        if (code != 200) { conn.disconnect(); throw new Exception("HTTP " + code); }
        InputStream in = conn.getInputStream();
        BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) sb.append(line);
        r.close();
        conn.disconnect();
        return new JSONObject(sb.toString());
    }

    private static void prompt(final Activity act, final int code, final String name,
                               final String url, final String sha, final String notes) {
        if (act.isFinishing()) return;
        StringBuilder msg = new StringBuilder();
        msg.append("当前版本：v").append(versionName(act)).append("\n");
        msg.append("新版本：v").append(name).append(" (").append(code).append(")\n\n");
        if (notes != null && notes.length() > 0) msg.append(notes);
        new AlertDialog.Builder(act)
                .setTitle("发现新版本")
                .setMessage(msg.toString())
                .setPositiveButton("立即更新", (d, w) -> download(act, url, sha, code))
                .setNegativeButton("稍后", null)
                .show();
    }

    private static void download(final Activity act, final String url, final String sha, final int remoteCode) {
        final ProgressDialog pd = new ProgressDialog(act);
        pd.setMessage("正在下载更新…");
        pd.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);
        pd.setMax(100);
        pd.setCancelable(false);
        pd.show();
        new Thread(new Runnable() {
            @Override public void run() {
                final File out = apkFile(act);
                try {
                    File dir = out.getParentFile();
                    if (dir != null && !dir.exists()) dir.mkdirs();
                    if (out.exists() && !out.delete()) throw new Exception("无法清理旧安装包");
                    HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
                    conn.setConnectTimeout(10000);
                    conn.setReadTimeout(20000);
                    conn.setRequestProperty("User-Agent", "LZJToolbox/" + versionName(act));
                    int code = conn.getResponseCode();
                    if (code != 200) { conn.disconnect(); throw new Exception("下载 HTTP " + code); }
                    long total = conn.getContentLength();
                    MessageDigest md = MessageDigest.getInstance("SHA-256");
                    InputStream in = conn.getInputStream();
                    FileOutputStream fo = new FileOutputStream(out);
                    byte[] buf = new byte[8192];
                    long got = 0;
                    int last = -1;
                    int n;
                    while ((n = in.read(buf)) > 0) {
                        fo.write(buf, 0, n);
                        md.update(buf, 0, n);
                        got += n;
                        if (total > 0) {
                            final int p = (int) (got * 100 / total);
                            if (p != last) {
                                last = p;
                                act.runOnUiThread(new Runnable() { @Override public void run() { pd.setProgress(p); } });
                            }
                        }
                    }
                    fo.close();
                    in.close();
                    conn.disconnect();
                    String hex = hex(md.digest());
                    if (!hex.equalsIgnoreCase(sha)) throw new Exception("SHA-256 校验失败");
                    PackageManager pm = act.getPackageManager();
                    PackageInfo pi = pm.getPackageArchiveInfo(out.getAbsolutePath(), PackageManager.GET_SIGNATURES);
                    if (pi == null || !act.getPackageName().equals(pi.packageName)) throw new Exception("安装包包名无效");
                    if (pi.versionCode != remoteCode) throw new Exception("安装包版本号不匹配");
                    if (!sameSignature(pm, act.getPackageName(), pi)) throw new Exception("安装包签名不一致");
                    act.runOnUiThread(new Runnable() {
                        @Override public void run() { pd.dismiss(); install(act, out); }
                    });
                } catch (final Exception e) {
                    if (out.exists()) out.delete();
                    act.runOnUiThread(new Runnable() {
                        @Override public void run() { pd.dismiss(); toast(act, "更新失败：" + e.getMessage()); }
                    });
                }
            }
        }, "ota-download").start();
    }

    private static boolean sameSignature(PackageManager pm, String pkg, PackageInfo archive) {
        try {
            PackageInfo cur = pm.getPackageInfo(pkg, PackageManager.GET_SIGNATURES);
            Signature[] a = archive.signatures;
            Signature[] b = cur.signatures;
            if (a == null || b == null || a.length == 0 || b.length == 0) return false;
            Set<String> sa = new HashSet<>();
            for (Signature s : a) sa.add(hex(s.toByteArray()));
            Set<String> sb = new HashSet<>();
            for (Signature s : b) sb.add(hex(s.toByteArray()));
            return sa.equals(sb);
        } catch (Exception e) {
            return false;
        }
    }

    private static void install(Activity act, File f) {
        if (Build.VERSION.SDK_INT >= 26 && !act.getPackageManager().canRequestPackageInstalls()) {
            pendingInstall = f;
            new AlertDialog.Builder(act)
                    .setTitle("需要安装权限")
                    .setMessage("请允许本应用安装未知来源应用，然后返回应用继续。")
                    .setPositiveButton("去设置", (d, w) -> {
                        try {
                            act.startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                    Uri.parse("package:" + act.getPackageName())));
                        } catch (Exception e) {
                            toast(act, "无法打开设置：" + e.getMessage());
                        }
                    })
                    .setNegativeButton("取消", null)
                    .show();
            return;
        }
        pendingInstall = null;
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(ApkProvider.uri(), "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            act.startActivity(i);
        } catch (Exception e) {
            toast(act, "无法启动安装器：" + e.getMessage());
        }
    }

    public static void onResume(Activity act) {
        if (pendingInstall != null && Build.VERSION.SDK_INT >= 26
                && act.getPackageManager().canRequestPackageInstalls()) {
            File f = pendingInstall;
            pendingInstall = null;
            install(act, f);
        }
    }

    private static void toast(Activity act, final String m) {
        act.runOnUiThread(new Runnable() {
            @Override public void run() { Toast.makeText(act, m, Toast.LENGTH_LONG).show(); }
        });
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) sb.append(String.format("%02x", x & 0xff));
        return sb.toString();
    }
}
