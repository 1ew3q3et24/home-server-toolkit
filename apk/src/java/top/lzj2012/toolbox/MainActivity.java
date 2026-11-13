package top.lzj2012.toolbox;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

public class MainActivity extends Activity {
    private static final String CHAT = "https://chat.lzj2012.top/";
    private static final int BLUE = 0xFF2563EB;
    private static final int GREY = 0xFF64748B;
    private static final int REQ_FILE = 71;

    private WebView web;
    private SettingsPanel settings;
    private TextView tabChat;
    private TextView tabSettings;
    private ValueCallback<Uri[]> filePathCallback;
    private boolean approvalDialogShowing = false;
    private final Handler ui = new Handler(Looper.getMainLooper());

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (BuildFlags.HARDENED) SecurityCheck.verify(this);
        buildUi();
        setupStatusBar();
        setupWebView();
        showTab(0);
        syncAuth();
        web.loadUrl(CHAT);
        handleIntent(getIntent());
        ui.postDelayed(new Runnable() {
            @Override public void run() { UpdateManager.check(MainActivity.this, false); }
        }, 1500);
    }

    private int dp(int v) { return Math.round(getResources().getDisplayMetrics().density * v); }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1f));

        web = new WebView(this);
        settings = new SettingsPanel(this, new SettingsPanel.Host() {
            @Override public void onLogin(String token) { syncWeb(token); }
            @Override public void onLogout() {
                CookieManager.getInstance().removeAllCookies(null);
                CookieManager.getInstance().flush();
                web.loadUrl(CHAT);
            }
        });
        settings.setVisibility(View.GONE);
        content.addView(web, new FrameLayout.LayoutParams(-1, -1));
        content.addView(settings, new FrameLayout.LayoutParams(-1, -1));

        View divider = new View(this);
        divider.setBackgroundColor(0xFFE5E7EB);
        root.addView(divider, new LinearLayout.LayoutParams(-1, dp(1)));

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setBackgroundColor(0xFFFFFFFF);
        bar.setPadding(dp(6), dp(4), dp(6), dp(4));
        tabChat = makeTab("消息");
        tabSettings = makeTab("设置");
        bar.addView(tabChat, new LinearLayout.LayoutParams(0, dp(46), 1f));
        bar.addView(tabSettings, new LinearLayout.LayoutParams(0, dp(46), 1f));
        root.addView(bar, new LinearLayout.LayoutParams(-1, -2));

        tabChat.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { showTab(0); }
        });
        tabSettings.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { showTab(1); }
        });
        setContentView(root);
    }

    private TextView makeTab(String text) {
        TextView tv = new TextView(this);
        tv.setText(text);
        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        tv.setGravity(Gravity.CENTER);
        TypedValue out = new TypedValue();
        getTheme().resolveAttribute(android.R.attr.selectableItemBackground, out, true);
        tv.setBackgroundResource(out.resourceId);
        return tv;
    }

    private void showTab(int i) {
        boolean chat = i == 0;
        web.setVisibility(chat ? View.VISIBLE : View.GONE);
        settings.setVisibility(chat ? View.GONE : View.VISIBLE);
        tabChat.setTextColor(chat ? BLUE : GREY);
        tabSettings.setTextColor(chat ? GREY : BLUE);
    }

    private void setupStatusBar() {
        if (Build.VERSION.SDK_INT >= 21) {
            getWindow().setStatusBarColor(0xFFF0F4F9);
            getWindow().setNavigationBarColor(0xFFFFFFFF);
        }
        int flags = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
        if (Build.VERSION.SDK_INT >= 26) flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        getWindow().getDecorView().setSystemUiVisibility(flags);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        if (Build.VERSION.SDK_INT >= 19) WebView.setWebContentsDebuggingEnabled(false);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setAllowFileAccessFromFileURLs(false);
        s.setAllowUniversalAccessFromFileURLs(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setSupportMultipleWindows(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setUserAgentString(s.getUserAgentString() + " LZJToolbox/" + UpdateManager.versionName(this));
        if (Build.VERSION.SDK_INT >= 21) s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setBackgroundColor(0xFFFFFFFF);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);

        CookieManager.getInstance().setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= 21) CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);

        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleUrl(request.getUrl().toString());
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return handleUrl(url);
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) Toast.makeText(MainActivity.this, "聊天加载失败，请检查网络", Toast.LENGTH_SHORT).show();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                try {
                    startActivityForResult(Intent.createChooser(i, "选择文件"), REQ_FILE);
                } catch (Exception e) {
                    filePathCallback = null;
                    Toast.makeText(MainActivity.this, "无法打开文件选择器", Toast.LENGTH_SHORT).show();
                    return false;
                }
                return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request) {
                if (Build.VERSION.SDK_INT < 21) { request.deny(); return; }
                String[] res = request.getResources();
                boolean audio = false, video = false;
                for (String r : res) {
                    if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(r)) audio = true;
                    if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(r)) video = true;
                }
                if ((audio && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
                        || (video && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)) {
                    Toast.makeText(MainActivity.this, "请先在设置中授予麦克风或相机权限", Toast.LENGTH_LONG).show();
                    request.deny();
                    return;
                }
                request.grant(res);
            }
        });
        web.setDownloadListener(new DownloadListener() {
            @Override public void onDownloadStart(String url, String ua, String cd, String mime, long len) {
                openExternal(Uri.parse(url));
            }
        });
    }

    private boolean isInternal(Uri u) {
        String h = u.getHost();
        if (h == null) return false;
        return h.equals("chat.lzj2012.top") || h.equals("lzj2012.top") || h.endsWith(".lzj2012.top");
    }

    private boolean handleUrl(String url) {
        if (url == null) return false;
        if (url.startsWith("file://")) return false;
        Uri u = Uri.parse(url);
        String scheme = u.getScheme() == null ? "" : u.getScheme().toLowerCase();
        if (scheme.equals("http") || scheme.equals("https")) {
            if (isInternal(u)) return false;
            openExternal(u);
            return true;
        }
        if (scheme.equals("intent")) return true;
        if (scheme.equals("mailto") || scheme.equals("tel") || scheme.equals("sms")
                || scheme.equals("market")) {
            openExternal(u);
            return true;
        }
        return true;
    }

    private void openExternal(Uri uri) {
        try {
            if ("intent".equals(uri.getScheme())) return;
            Intent i = new Intent(Intent.ACTION_VIEW, uri);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "没有可打开此链接的应用", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "链接打开失败", Toast.LENGTH_SHORT).show();
        }
    }

    private static String pickCookie(String all, String name) {
        if (all == null) return "";
        for (String p : all.split(";")) {
            p = p.trim();
            if (p.startsWith(name + "=")) return p;
        }
        return "";
    }

    private void syncAuth() {
        final String tok = Prefs.token(this);
        String all = CookieManager.getInstance().getCookie(CHAT);
        final String ck = pickCookie(all, "chq");
        if (!tok.isEmpty()) {
            syncWeb(tok);
        } else if (!ck.isEmpty() && !Prefs.loggedOut(this)) {
            new Thread(new Runnable() { @Override public void run() {
                try {
                    JSONObject j = Api.tokenFromCookie(ck);
                    final String tk = j.optString("token");
                    JSONObject u = j.optJSONObject("user");
                    Prefs.saveToken(MainActivity.this, tk);
                    Prefs.setName(MainActivity.this, u == null ? "" : u.optString("nickname"));
                    Prefs.setLoggedOut(MainActivity.this, false);
                } catch (Exception ignored) { }
            }}).start();
        }
    }

    private void syncWeb(final String tok) {
        new Thread(new Runnable() { @Override public void run() {
            try {
                JSONObject j = Api.webLogin(tok);
                final String cookie = j.optString("cookie");
                if (!cookie.isEmpty()) {
                    CookieManager.getInstance().setCookie(CHAT, cookie);
                    CookieManager.getInstance().flush();
                    ui.post(new Runnable() { @Override public void run() {
                        if (web.getUrl() != null) web.reload();
                    }});
                }
            } catch (Exception ignored) { }
        }}).start();
    }

    private void showApproval(int id, String name, String code) {
        if (approvalDialogShowing) return;
        if (Prefs.token(this).isEmpty()) {
            showTab(1);
            Toast.makeText(this, "请先在设置中登录", Toast.LENGTH_LONG).show();
            return;
        }
        approvalDialogShowing = true;
        String msg = (name == null || name.isEmpty() ? "未知玩家" : name)
                + " 申请进入 Minecraft 服务器。\n\n认证链接：" + (code == null ? "" : code);
        AlertDialog d = new AlertDialog.Builder(this)
                .setTitle("服务器准入申请")
                .setMessage(msg)
                .setPositiveButton("批准", new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface dialog, int which) { doApproval(id, true); }
                })
                .setNegativeButton("拒绝", new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface dialog, int which) { doApproval(id, false); }
                })
                .create();
        d.setOnDismissListener(new DialogInterface.OnDismissListener() {
            @Override public void onDismiss(DialogInterface dialog) { approvalDialogShowing = false; }
        });
        d.show();
    }

    private void doApproval(final int id, final boolean allow) {
        final String tk = Prefs.token(this);
        if (tk.isEmpty()) { Toast.makeText(this, "请先在设置中登录", Toast.LENGTH_SHORT).show(); return; }
        new Thread(new Runnable() { @Override public void run() {
            try {
                if (allow) Api.approve(tk, id); else Api.deny(tk, id);
                WatchService.forget(id);
                ui.post(new Runnable() { @Override public void run() {
                    Toast.makeText(MainActivity.this, allow ? "已批准" : "已拒绝", Toast.LENGTH_SHORT).show();
                }});
            } catch (final Exception e) {
                ui.post(new Runnable() { @Override public void run() {
                    Toast.makeText(MainActivity.this, e.getMessage() == null ? "操作失败" : e.getMessage(), Toast.LENGTH_LONG).show();
                }});
            }
        }}).start();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent == null) return;
        if (intent.getBooleanExtra("ota_prompt", false)) UpdateManager.check(this, true);
        if (intent.getBooleanExtra("approval", false)) {
            showApproval(intent.getIntExtra("approval_id", 0),
                    intent.getStringExtra("approval_name"),
                    intent.getStringExtra("approval_code"));
        }
        Uri u = intent.getData();
        if (u == null || !"lzjapp".equals(u.getScheme())) return;
        if ("approve".equals(u.getHost())) {
            String t = u.getQueryParameter("t");
            if (t != null && t.matches("[0-9a-fA-F]{12}")) {
                web.loadUrl("https://chat.lzj2012.top/v/" + t);
                showTab(0);
            }
        } else if ("chat".equals(u.getHost())) {
            showTab(0);
        }
    }

    @Override public void onBackPressed() {
        if (web != null && web.getVisibility() == View.VISIBLE && web.canGoBack()) { web.goBack(); return; }
        super.onBackPressed();
    }

    @Override protected void onResume() {
        super.onResume();
        UpdateManager.onResume(this);
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (settings != null) settings.onPermissionsChanged();
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_FILE) {
            Uri[] result = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getData() != null) result = new Uri[]{data.getData()};
                else if (data.getClipData() != null) {
                    ClipData cd = data.getClipData();
                    result = new Uri[cd.getItemCount()];
                    for (int i = 0; i < cd.getItemCount(); i++) result[i] = cd.getItemAt(i).getUri();
                }
            }
            if (filePathCallback != null) filePathCallback.onReceiveValue(result);
            filePathCallback = null;
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override protected void onPause() {
        CookieManager.getInstance().flush();
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (web != null) { web.stopLoading(); web.destroy(); }
        super.onDestroy();
    }
}
