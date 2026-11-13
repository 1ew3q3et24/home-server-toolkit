package top.lzj2012.toolbox;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

public class SettingsPanel extends ScrollView {
    public interface Host {
        void onLogin(String token);
        void onLogout();
    }

    public static final int REQ_NOTIF = 41;
    public static final int REQ_MIC = 42;
    public static final int REQ_CAM = 43;
    public static final int REQ_STORAGE = 44;

    private static final int BG = 0xFFF5F7FA;
    private static final int CARD = 0xFFFFFFFF;
    private static final int LINE = 0xFFE5E7EB;
    private static final int TEXT = 0xFF111827;
    private static final int SUB = 0xFF64748B;
    private static final int BLUE = 0xFF2563EB;
    private static final int GREEN = 0xFF047857;
    private static final int RED = 0xFFB91C1C;

    private final Activity act;
    private final Host host;
    private final LinearLayout box;
    private boolean needTos = true;
    private String nickname = "";
    private boolean loadingUser = false;

    public SettingsPanel(Activity a, Host h) {
        super(a);
        act = a;
        host = h;
        setFillViewport(true);
        setBackgroundColor(BG);
        box = new LinearLayout(a);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(16), dp(16), dp(28));
        addView(box);
        rebuild();
        refreshAccount();
    }

    private int dp(int v) { return Math.round(getResources().getDisplayMetrics().density * v); }

    private GradientDrawable bg(int color, int radius, int stroke) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(color);
        g.setCornerRadius(dp(radius));
        if (stroke != 0) g.setStroke(dp(1), stroke);
        return g;
    }

    private TextView tv(String text, int size, int color, boolean bold) {
        TextView v = new TextView(act);
        v.setText(text);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, size);
        v.setTextColor(color);
        if (bold) v.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        v.setLineSpacing(dp(2), 1f);
        return v;
    }

    private LinearLayout card() {
        LinearLayout c = new LinearLayout(act);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setBackground(bg(CARD, 16, LINE));
        c.setPadding(dp(16), dp(14), dp(16), dp(14));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.bottomMargin = dp(12);
        c.setLayoutParams(lp);
        return c;
    }

    private TextView action(String text, boolean primary) {
        TextView b = tv(text, 13, primary ? Color.WHITE : TEXT, true);
        b.setGravity(Gravity.CENTER);
        b.setPadding(dp(12), dp(8), dp(12), dp(8));
        b.setBackground(bg(primary ? BLUE : 0xFFEEF2F7, 10, 0));
        b.setClickable(true);
        b.setFocusable(true);
        return b;
    }

    private LinearLayout row(String title, String desc, String status, int statusColor, TextView btn) {
        LinearLayout r = new LinearLayout(act);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(0, dp(9), 0, dp(9));
        LinearLayout left = new LinearLayout(act);
        left.setOrientation(LinearLayout.VERTICAL);
        left.addView(tv(title, 15, TEXT, true));
        if (desc != null && desc.length() > 0) left.addView(tv(desc, 12, SUB, false));
        if (status != null && status.length() > 0) left.addView(tv(status, 12, statusColor, false));
        r.addView(left, new LinearLayout.LayoutParams(0, -2, 1f));
        if (btn != null) r.addView(btn, new LinearLayout.LayoutParams(-2, -2));
        return r;
    }

    private void section(String text) {
        TextView t = tv(text, 13, SUB, true);
        t.setPadding(dp(4), dp(8), dp(4), dp(6));
        box.addView(t);
    }

    private void rebuild() {
        box.removeAllViews();
        TextView h = tv("设置", 26, TEXT, true);
        h.setPadding(dp(2), 0, 0, dp(2));
        box.addView(h);
        box.addView(tv("账号、更新、隐私与权限", 13, SUB, false));

        section("账号");
        LinearLayout acc = card();
        String token = Prefs.token(act);
        if (token.isEmpty()) {
            acc.addView(tv("登录 LZJ 通讯", 16, TEXT, true));
            acc.addView(tv("登录后可在应用内接收服务器准入审批与版本更新。", 12, SUB, false));
            final EditText email = field("邮箱", false);
            final EditText pass = field("密码", true);
            final TextView err = tv("", 12, RED, false);
            TextView login = action("登录", true);
            acc.addView(email);
            acc.addView(pass);
            acc.addView(login, new LinearLayout.LayoutParams(-1, dp(42)));
            acc.addView(err);
            login.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    final String em = email.getText().toString().trim();
                    final String pw = pass.getText().toString();
                    if (em.isEmpty() || pw.isEmpty()) { err.setText("请填写邮箱与密码"); return; }
                    login.setEnabled(false); err.setText("正在登录…");
                    new Thread(new Runnable() { @Override public void run() {
                        try {
                            JSONObject j = Api.login(em, pw, "Android " + Build.MODEL);
                            final String tk = j.optString("token");
                            JSONObject u = j.optJSONObject("user");
                            final String nick = u == null ? "" : u.optString("nickname");
                            final boolean nt = u == null || u.optBoolean("need_tos", true);
                            Prefs.saveToken(act, tk);
                            Prefs.setName(act, nick);
                            Prefs.setLoggedOut(act, false);
                            act.runOnUiThread(new Runnable() { @Override public void run() {
                                nickname = nick; needTos = nt;
                                if (host != null) host.onLogin(tk);
                                startWatch();
                                rebuild();
                            }});
                        } catch (final Exception e) {
                            act.runOnUiThread(new Runnable() { @Override public void run() {
                                login.setEnabled(true);
                                err.setText(e.getMessage() == null ? "登录失败" : e.getMessage());
                            }});
                        }
                    }}).start();
                }
            });
        } else {
            acc.addView(tv(nickname.isEmpty() ? "已登录" : nickname, 17, TEXT, true));
            acc.addView(tv("账号已连接；聊天与审批共用同一会话。", 12, SUB, false));
            TextView out = action("退出登录", false);
            acc.addView(out, new LinearLayout.LayoutParams(-2, -2));
            out.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    act.stopService(new Intent(act, WatchService.class));
                    Prefs.clear(act);
                    Prefs.setLoggedOut(act, true);
                    nickname = ""; needTos = true;
                    if (host != null) host.onLogout();
                    rebuild();
                }
            });
        }
        box.addView(acc);

        section("应用更新");
        LinearLayout upd = card();
        upd.addView(tv("版本 v" + UpdateManager.versionName(act), 16, TEXT, true));
        upd.addView(tv("通过云端 OTA 获取新版本；下载后校验完整性并调用系统安装器。", 12, SUB, false));
        TextView check = action("检查更新", true);
        upd.addView(check, new LinearLayout.LayoutParams(-2, -2));
        check.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { UpdateManager.check(act, true); }
        });
        box.addView(upd);

        section("隐私与协议");
        LinearLayout pri = card();
        pri.addView(tv("隐私政策与用户协议", 16, TEXT, true));
        pri.addView(tv(needTos ? "尚未同意；同意后方可正常使用账号功能。" : "已同意。", 12, needTos ? RED : GREEN, false));
        TextView agree = action(needTos ? "阅读并同意" : "查看协议", true);
        pri.addView(agree, new LinearLayout.LayoutParams(-2, -2));
        agree.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { showPrivacy(); }
        });
        box.addView(pri);

        section("权限");
        LinearLayout perm = card();
        perm.addView(row("通知", "接收服务器准入审批与版本更新提醒。", notifGranted() ? "已授权" : "未授权", notifGranted() ? GREEN : RED,
                notifGranted() ? action("设置", false) : action("授权", true)));
        View notifBtn = ((LinearLayout) perm.getChildAt(perm.getChildCount() - 1)).getChildAt(1);
        notifBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (notifGranted()) openNotificationSettings(); else requestNotif();
            }
        });

        perm.addView(divider());
        perm.addView(row("麦克风", "用于语音消息与语音通话；仅在录音时使用。", has(Manifest.permission.RECORD_AUDIO) ? "已授权" : "未授权",
                has(Manifest.permission.RECORD_AUDIO) ? GREEN : RED,
                has(Manifest.permission.RECORD_AUDIO) ? action("设置", false) : action("授权", true)));
        View micBtn = ((LinearLayout) perm.getChildAt(perm.getChildCount() - 1)).getChildAt(1);
        micBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (has(Manifest.permission.RECORD_AUDIO)) openAppSettings(); else act.requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);
            }
        });

        perm.addView(divider());
        perm.addView(row("相机", "用于拍照、扫描二维码与视频通话。", has(Manifest.permission.CAMERA) ? "已授权" : "未授权",
                has(Manifest.permission.CAMERA) ? GREEN : RED,
                has(Manifest.permission.CAMERA) ? action("设置", false) : action("授权", true)));
        View camBtn = ((LinearLayout) perm.getChildAt(perm.getChildCount() - 1)).getChildAt(1);
        camBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (has(Manifest.permission.CAMERA)) openAppSettings(); else act.requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAM);
            }
        });

        perm.addView(divider());
        boolean st = has(storagePerm());
        perm.addView(row("存储与照片", "用于选择图片、文件与保存聊天附件。", st ? "已授权" : "未授权", st ? GREEN : RED,
                st ? action("设置", false) : action("授权", true)));
        View stBtn = ((LinearLayout) perm.getChildAt(perm.getChildCount() - 1)).getChildAt(1);
        stBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (has(storagePerm())) openAppSettings(); else act.requestPermissions(new String[]{storagePerm()}, REQ_STORAGE);
            }
        });

        perm.addView(divider());
        perm.addView(row("自启动与后台运行", "用于保持审批通知在线。Android 无统一 API，需在系统设置中开启。", "系统设置", SUB,
                action("去设置", false)));
        View autoBtn = ((LinearLayout) perm.getChildAt(perm.getChildCount() - 1)).getChildAt(1);
        autoBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { openAutoStart(); }
        });
        box.addView(perm);

        section("关于");
        LinearLayout about = card();
        about.addView(tv("LZJ 通讯", 16, TEXT, true));
        about.addView(tv("版本 v" + UpdateManager.versionName(act) + "（" + UpdateManager.versionCode(act) + "）", 12, SUB, false));
        about.addView(tv("服务：chat.lzj2012.top · 更新：download.lzj2012.top", 12, SUB, false));
        box.addView(about);
    }

    private View divider() {
        View v = new View(act);
        v.setBackgroundColor(LINE);
        v.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(1)));
        return v;
    }

    private EditText field(String hint, boolean pass) {
        EditText e = new EditText(act);
        e.setHint(hint);
        e.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        e.setSingleLine(true);
        e.setBackground(bg(0xFFF8FAFC, 10, LINE));
        e.setPadding(dp(12), dp(10), dp(12), dp(10));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.topMargin = dp(8);
        e.setLayoutParams(lp);
        if (pass) e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        return e;
    }

    private boolean has(String p) {
        return Build.VERSION.SDK_INT < 23 || act.checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED;
    }

    private String storagePerm() {
        return Build.VERSION.SDK_INT >= 33 ? Manifest.permission.READ_MEDIA_IMAGES : Manifest.permission.READ_EXTERNAL_STORAGE;
    }

    private boolean notifGranted() {
        if (Build.VERSION.SDK_INT >= 33) return has(Manifest.permission.POST_NOTIFICATIONS);
        return Notifier.enabled(act);
    }

    private void requestNotif() {
        if (Build.VERSION.SDK_INT >= 33) act.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIF);
        else openNotificationSettings();
    }

    private void openNotificationSettings() {
        Intent i = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS);
        i.putExtra(Settings.EXTRA_APP_PACKAGE, act.getPackageName());
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try { act.startActivity(i); } catch (Exception e) { openAppSettings(); }
    }

    private void openAppSettings() {
        try {
            act.startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:" + act.getPackageName())).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (Exception ignored) { }
    }

    private void openAutoStart() {
        String[][] list = new String[][]{
                {"com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity"},
                {"com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.BgStartUpManager"},
                {"com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity"},
                {"com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity"},
                {"com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"},
                {"com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"}
        };
        for (String[] x : list) {
            try {
                Intent i = new Intent();
                i.setComponent(new ComponentName(x[0], x[1]));
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                act.startActivity(i);
                return;
            } catch (Exception ignored) { }
        }
        openAppSettings();
        Toast.makeText(act, "请在系统设置中允许自启动与后台运行", Toast.LENGTH_LONG).show();
    }

    private void showPrivacy() {
        String msg = "本应用仅处理提供服务所必需的数据：\n\n"
                + "1. 账号：邮箱、昵称、加密后的密码摘要，用于登录与身份识别。\n"
                + "2. 设备：设备标识与登录令牌，用于保持会话与推送审批。\n"
                + "3. 内容：聊天消息与附件，仅在提供服务所需范围内处理。\n"
                + "4. 权限：通知、麦克风、相机、存储，仅在对应功能使用时申请。\n\n"
                + "你可以随时在系统设置中撤回权限。";
        new AlertDialog.Builder(act)
                .setTitle("隐私政策与用户协议")
                .setMessage(msg)
                .setPositiveButton(needTos ? "同意" : "关闭", (d, w) -> { if (needTos) agreeTos(); })
                .setNeutralButton("查看完整协议", (d, w) -> {
                    try {
                        act.startActivity(new Intent(Intent.ACTION_VIEW,
                                Uri.parse("https://mcverify.lzj2012.top/")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                    } catch (Exception ignored) { }
                })
                .setNegativeButton("取消", null)
                .show();
    }

    private void agreeTos() {
        final String tk = Prefs.token(act);
        if (tk.isEmpty()) { Toast.makeText(act, "请先登录", Toast.LENGTH_SHORT).show(); return; }
        new Thread(new Runnable() { @Override public void run() {
            try {
                Api.tosAgree(tk);
                act.runOnUiThread(new Runnable() { @Override public void run() {
                    needTos = false;
                    Toast.makeText(act, "已记录同意状态", Toast.LENGTH_SHORT).show();
                    rebuild();
                }});
            } catch (final Exception e) {
                act.runOnUiThread(new Runnable() { @Override public void run() {
                    Toast.makeText(act, e.getMessage() == null ? "提交失败" : e.getMessage(), Toast.LENGTH_LONG).show();
                }});
            }
        }}).start();
    }

    private void refreshAccount() {
        if (loadingUser) return;
        final String tk = Prefs.token(act);
        if (tk.isEmpty()) { needTos = true; rebuild(); return; }
        loadingUser = true;
        new Thread(new Runnable() { @Override public void run() {
            try {
                JSONObject u = Api.me(tk).optJSONObject("user");
                final boolean nt = u == null || u.optBoolean("need_tos", true);
                final String nick = u == null ? "" : u.optString("nickname");
                if (nick != null && nick.length() > 0) Prefs.setName(act, nick);
                act.runOnUiThread(new Runnable() { @Override public void run() {
                    loadingUser = false; needTos = nt; nickname = nick == null ? "" : nick;
                    rebuild();
                }});
            } catch (final Exception e) {
                act.runOnUiThread(new Runnable() { @Override public void run() {
                    loadingUser = false;
                    if (e instanceof Api.ApiException && ((Api.ApiException) e).status == 401) {
                        Prefs.clear(act);
                        if (host != null) host.onLogout();
                        rebuild();
                    }
                }});
            }
        }}).start();
    }

    public void onPermissionsChanged() { rebuild(); }

    private void startWatch() {
        Intent i = new Intent(act, WatchService.class);
        if (Build.VERSION.SDK_INT >= 26) act.startForegroundService(i);
        else act.startService(i);
    }
}
