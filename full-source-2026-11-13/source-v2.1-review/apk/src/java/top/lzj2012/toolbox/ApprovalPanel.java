package top.lzj2012.toolbox;

import android.app.Activity;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Build;
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
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;

import java.util.List;

public class ApprovalPanel extends LinearLayout {
    public interface LoginListener { void onLoggedIn(String token); }

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final LoginListener listener;
    private String token = "";

    public ApprovalPanel(Context c, LoginListener l) {
        super(c);
        listener = l;
        setOrientation(VERTICAL);
        setBackgroundColor(0xFFF5F7FB);
        int p = dp(20);
        setPadding(p, dp(24), p, dp(24));
        token = Prefs.token(getContext());
        if (token.isEmpty()) showLogin(); else { showMain(); startWatch(); }
    }

    public void reload() {
        token = Prefs.token(getContext());
        if (token.isEmpty()) showLogin(); else { showMain(); startWatch(); }
    }

    public void setToken(String t) {
        if (t == null || t.isEmpty()) return;
        token = t;
        showMain();
        startWatch();
    }

    private int dp(int v) { return Math.round(getResources().getDisplayMetrics().density * v); }

    private TextView text(String t, int size, int color) {
        TextView v = new TextView(getContext());
        v.setText(t);
        v.setTextSize(TypedValue.COMPLEX_UNIT_SP, size);
        v.setTextColor(color);
        v.setPadding(0, 0, 0, dp(6));
        return v;
    }

    private Button btn(String t, int bg, int fg) {
        Button b = new Button(getContext());
        b.setText(t);
        b.setTextColor(fg);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        b.setBackgroundColor(bg);
        b.setAllCaps(false);
        return b;
    }

    private EditText input(String hint, boolean pass) {
        EditText e = new EditText(getContext());
        e.setHint(hint);
        e.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        e.setSingleLine(true);
        if (pass) e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        return e;
    }

    private void showLogin() {
        removeAllViews();
        addView(text("批准中心", 26, 0xFF111827));
        addView(text("登录后接收我的世界进服请求", 13, 0xFF64748B));
        final EditText email = input("邮箱", false);
        email.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        final EditText pass = input("密码", true);
        addView(email);
        addView(pass);
        final TextView err = text("", 13, 0xFFDC2626);
        final Button login = btn("登录", 0xFF2563EB, Color.WHITE);
        addView(login, new LinearLayout.LayoutParams(-1, dp(48)));
        Button test = btn("测试通知", 0xFFE2E8F0, 0xFF1F2937);
        addView(test, new LinearLayout.LayoutParams(-1, dp(44)));
        addView(err);

        login.setOnClickListener(new OnClickListener() {
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
                        Prefs.saveToken(getContext(), tk);
                        Prefs.setName(getContext(), nick);
                        Prefs.setLoggedOut(getContext(), false);
                        token = tk;
                        ui.post(new Runnable() { @Override public void run() {
                            if (listener != null) listener.onLoggedIn(tk);
                            showMain();
                            startWatch();
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

        test.setOnClickListener(new OnClickListener() {
            @Override public void onClick(View v) {
                boolean ok = Notifier.enabled(getContext());
                Api.Pending p = new Api.Pending();
                p.id = 999999; p.name = "测试玩家"; p.code = "0000-0000"; p.ttl = 300;
                if (ok) Notifier.showApproval(getContext(), p);
                Toast.makeText(getContext(), ok ? "已发送测试通知" : "系统通知被关闭，请到设置里允许", Toast.LENGTH_LONG).show();
            }
        });
    }

    private void showMain() {
        removeAllViews();
        addView(text("批准中心", 26, 0xFF111827));
        String name = Prefs.name(getContext());
        addView(text(name.isEmpty() ? "已登录" : "已登录：" + name, 13, 0xFF64748B));
        boolean on = Notifier.enabled(getContext());
        addView(text(on ? "系统通知：已开启" : "系统通知：已关闭", 13, on ? 0xFF059669 : 0xFFB91C1C));
        addView(text(WatchService.running ? "后台监听：运行中" : "后台监听：未启动", 13,
                WatchService.running ? 0xFF059669 : 0xFFB45309));

        LinearLayout row = new LinearLayout(getContext());
        row.setOrientation(HORIZONTAL);
        Button refresh = btn("刷新", 0xFFE2E8F0, 0xFF1F2937);
        Button test = btn("测试通知", 0xFFE2E8F0, 0xFF1F2937);
        Button logout = btn("退出", 0xFFFEE2E2, 0xFFB91C1C);
        row.addView(refresh, new LinearLayout.LayoutParams(0, dp(42), 1f));
        row.addView(test, new LinearLayout.LayoutParams(0, dp(42), 1f));
        row.addView(logout, new LinearLayout.LayoutParams(0, dp(42), 1f));
        addView(row);

        final LinearLayout list = new LinearLayout(getContext());
        list.setOrientation(VERTICAL);
        addView(list);

        refresh.setOnClickListener(new OnClickListener() {
            @Override public void onClick(View v) { load(list); }
        });
        test.setOnClickListener(new OnClickListener() {
            @Override public void onClick(View v) {
                boolean ok = Notifier.enabled(getContext());
                Api.Pending p = new Api.Pending();
                p.id = 999999; p.name = "测试玩家"; p.code = "0000-0000"; p.ttl = 300;
                if (ok) Notifier.showApproval(getContext(), p);
                Toast.makeText(getContext(), ok ? "已发送测试通知" : "系统通知被关闭，请到设置里允许", Toast.LENGTH_LONG).show();
            }
        });
        logout.setOnClickListener(new OnClickListener() {
            @Override public void onClick(View v) {
                getContext().stopService(new Intent(getContext(), WatchService.class));
                Prefs.clear(getContext());
                Prefs.setLoggedOut(getContext(), true);
                token = "";
                showLogin();
            }
        });
        load(list);
    }

    private void load(final LinearLayout list) {
        final String tk = token;
        new Thread(new Runnable() { @Override public void run() {
            try {
                final List<Api.Pending> ps = Api.pending(tk);
                ui.post(new Runnable() { @Override public void run() { render(list, ps); } });
            } catch (final Exception e) {
                ui.post(new Runnable() { @Override public void run() {
                    list.removeAllViews();
                    list.addView(text("读取失败：" + (e.getMessage() == null ? "网络错误" : e.getMessage()), 13, 0xFFDC2626));
                }});
            }
        }}).start();
    }

    private void render(LinearLayout list, List<Api.Pending> ps) {
        list.removeAllViews();
        if (ps.isEmpty()) { list.addView(text("暂无待批准请求", 14, 0xFF64748B)); return; }
        for (final Api.Pending p : ps) {
            LinearLayout card = new LinearLayout(getContext());
            card.setOrientation(VERTICAL);
            card.setBackgroundColor(Color.WHITE);
            card.setPadding(dp(14), dp(12), dp(14), dp(12));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
            lp.topMargin = dp(10);
            card.setLayoutParams(lp);
            card.addView(text(p.name, 17, 0xFF111827));
            card.addView(text("验证码 " + p.code + " · 剩余 " + p.ttl + " 秒", 12, 0xFF64748B));
            LinearLayout btns = new LinearLayout(getContext());
            btns.setOrientation(HORIZONTAL);
            Button allow = btn("允许", 0xFF2563EB, Color.WHITE);
            Button deny = btn("拒绝", 0xFFE2E8F0, 0xFF334155);
            btns.addView(allow, new LinearLayout.LayoutParams(0, dp(42), 1f));
            btns.addView(deny, new LinearLayout.LayoutParams(0, dp(42), 1f));
            card.addView(btns);
            allow.setOnClickListener(new OnClickListener() {
                @Override public void onClick(View v) { act(p.id, true); }
            });
            deny.setOnClickListener(new OnClickListener() {
                @Override public void onClick(View v) { act(p.id, false); }
            });
            list.addView(card);
        }
    }

    private void act(final int id, final boolean allow) {
        final String tk = token;
        new Thread(new Runnable() { @Override public void run() {
            try {
                if (allow) Api.approve(tk, id); else Api.deny(tk, id);
                ui.post(new Runnable() { @Override public void run() {
                    Toast.makeText(getContext(), allow ? "已允许" : "已拒绝", Toast.LENGTH_SHORT).show();
                    showMain();
                }});
            } catch (final Exception e) {
                ui.post(new Runnable() { @Override public void run() {
                    Toast.makeText(getContext(), e.getMessage() == null ? "操作失败" : e.getMessage(), Toast.LENGTH_LONG).show();
                }});
            }
        }}).start();
    }

    private void startWatch() {
        Intent i = new Intent(getContext(), WatchService.class);
        if (Build.VERSION.SDK_INT >= 26) getContext().startForegroundService(i);
        else getContext().startService(i);
    }
}
