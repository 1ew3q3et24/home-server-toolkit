package top.lzj2012.approval;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;

import java.util.List;

public class MainActivity extends Activity {
    private LinearLayout content;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private String token = "";

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Notifier.ensureChannel(this);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(0xFFF5F7FB);
        content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        content.setPadding(pad, dp(28), pad, dp(28));
        sv.addView(content, new ViewGroup.LayoutParams(-1, -2));
        setContentView(sv);
        requestNotif();
        token = Prefs.token(this);
        if (token.isEmpty()) showLogin(); else { showMain(); startWatch(); }
    }

    private int dp(int v) { return Math.round(getResources().getDisplayMetrics().density * v); }

    private void requestNotif() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission("android.permission.POST_NOTIFICATIONS") != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 10);
        }
    }

    private TextView title(String t, int size, int color) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, size);
        v.setTextColor(color);
        v.setPadding(0, 0, 0, dp(6));
        return v;
    }

    private Button button(String t, int bg, int fg) {
        Button b = new Button(this);
        b.setText(t);
        b.setTextColor(fg);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        b.setBackgroundColor(bg);
        b.setAllCaps(false);
        return b;
    }

    private EditText field(String hint, boolean pass) {
        EditText e = new EditText(this);
        e.setHint(hint);
        e.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        e.setSingleLine(true);
        if (pass) e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        return e;
    }

    private void showLogin() {
        content.removeAllViews();
        content.addView(title("LZJ 批准", 26, 0xFF111827));
        content.addView(title("登录后接收我的世界进服请求", 13, 0xFF64748B));
        final EditText email = field("邮箱", false);
        email.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        final EditText pass = field("密码", true);
        content.addView(email);
        content.addView(pass);
        final TextView err = title("", 13, 0xFFDC2626);
        final Button login = button("登录", 0xFF2563EB, Color.WHITE);
        content.addView(login, new LinearLayout.LayoutParams(-1, dp(48)));
        Button test0 = button("测试通知（无需登录）", 0xFFE2E8F0, 0xFF1F2937);
        content.addView(test0, new LinearLayout.LayoutParams(-1, dp(44)));
        test0.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                Api.Pending p = new Api.Pending();
                p.id = 999999; p.name = "测试玩家"; p.code = "0000-0000"; p.ttl = 300;
                Notifier.showApproval(MainActivity.this, p);
            }
        });
        content.addView(err);
        login.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                final String em = email.getText().toString().trim();
                final String pw = pass.getText().toString();
                if (em.isEmpty() || pw.isEmpty()) { err.setText("请填写邮箱和密码"); return; }
                login.setEnabled(false);
                err.setText("登录中…");
                new Thread(new Runnable() { @Override public void run() {
                    try {
                        JSONObject j = Api.login(em, pw, "Android " + Build.MODEL);
                        final String tk = j.optString("token");
                        JSONObject u = j.optJSONObject("user");
                        final String nick = u == null ? "" : u.optString("nickname");
                        Prefs.saveToken(MainActivity.this, tk);
                        Prefs.setName(MainActivity.this, nick);
                        token = tk;
                        ui.post(new Runnable() { @Override public void run() {
                            showMain(); startWatch();
                        }});
                    } catch (final Exception e) {
                        ui.post(new Runnable() { @Override public void run() {
                            login.setEnabled(true);
                            err.setText(e.getMessage() == null ? "登录失败" : e.getMessage());
                        }});
                    }
                }}).start();
            }
        });
    }

    private void showMain() {
        content.removeAllViews();
        content.addView(title("批准中心", 26, 0xFF111827));
        String name = Prefs.name(this);
        content.addView(title(name.isEmpty() ? "已登录" : "已登录：" + name, 13, 0xFF64748B));

        final TextView status = title(WatchService.running ? "后台监听：运行中" : "后台监听：未启动", 13,
                WatchService.running ? 0xFF059669 : 0xFFB45309);
        content.addView(status);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        Button refresh = button("刷新", 0xFFE2E8F0, 0xFF1F2937);
        Button test = button("测试通知", 0xFFE2E8F0, 0xFF1F2937);
        Button logout = button("退出", 0xFFFEE2E2, 0xFFB91C1C);
        row.addView(refresh, new LinearLayout.LayoutParams(0, dp(42), 1f));
        row.addView(test, new LinearLayout.LayoutParams(0, dp(42), 1f));
        row.addView(logout, new LinearLayout.LayoutParams(0, dp(42), 1f));
        content.addView(row);

        final LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        content.addView(list);

        refresh.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { load(list); }
        });
        test.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                Api.Pending p = new Api.Pending();
                p.id = 999999; p.name = "测试玩家"; p.code = "0000-0000"; p.ttl = 300;
                Notifier.showApproval(MainActivity.this, p);
                Toast.makeText(MainActivity.this, "已发测试通知", Toast.LENGTH_SHORT).show();
            }
        });
        logout.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                stopService(new Intent(MainActivity.this, WatchService.class));
                Prefs.clear(MainActivity.this);
                token = "";
                showLogin();
            }
        });
        load(list);
    }

    private void load(final LinearLayout list) {
        new Thread(new Runnable() { @Override public void run() {
            try {
                final List<Api.Pending> ps = Api.pending(token);
                ui.post(new Runnable() { @Override public void run() { render(list, ps); } });
            } catch (final Exception e) {
                ui.post(new Runnable() { @Override public void run() {
                    list.removeAllViews();
                    list.addView(title("读取失败：" + (e.getMessage() == null ? "网络错误" : e.getMessage()), 13, 0xFFDC2626));
                }});
            }
        }}).start();
    }

    private void render(LinearLayout list, List<Api.Pending> ps) {
        list.removeAllViews();
        if (ps.isEmpty()) {
            list.addView(title("暂无待批准请求", 14, 0xFF64748B));
            return;
        }
        for (final Api.Pending p : ps) {
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setBackgroundColor(Color.WHITE);
            card.setPadding(dp(14), dp(12), dp(14), dp(12));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.topMargin = dp(10);
            card.setLayoutParams(lp);
            card.addView(title(p.name, 17, 0xFF111827));
            card.addView(title("验证码 " + p.code + " · 剩余 " + p.ttl + " 秒", 12, 0xFF64748B));
            LinearLayout btns = new LinearLayout(this);
            btns.setOrientation(LinearLayout.HORIZONTAL);
            Button allow = button("允许", 0xFF2563EB, Color.WHITE);
            Button deny = button("拒绝", 0xFFE2E8F0, 0xFF334155);
            btns.addView(allow, new LinearLayout.LayoutParams(0, dp(42), 1f));
            btns.addView(deny, new LinearLayout.LayoutParams(0, dp(42), 1f));
            card.addView(btns);
            allow.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { act(p.id, true); }
            });
            deny.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) { act(p.id, false); }
            });
            list.addView(card);
        }
        if (ps.isEmpty()) list.addView(title("暂无待批准请求", 14, 0xFF64748B));
    }

    private void act(final int id, final boolean allow) {
        new Thread(new Runnable() { @Override public void run() {
            try {
                if (allow) Api.approve(token, id); else Api.deny(token, id);
                ui.post(new Runnable() { @Override public void run() {
                    Toast.makeText(MainActivity.this, allow ? "已允许" : "已拒绝", Toast.LENGTH_SHORT).show();
                    showMain();
                }});
            } catch (final Exception e) {
                ui.post(new Runnable() { @Override public void run() {
                    Toast.makeText(MainActivity.this, e.getMessage() == null ? "操作失败" : e.getMessage(), Toast.LENGTH_LONG).show();
                }});
            }
        }}).start();
    }

    private void startWatch() {
        Intent i = new Intent(this, WatchService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(i); else startService(i);
    }
}
