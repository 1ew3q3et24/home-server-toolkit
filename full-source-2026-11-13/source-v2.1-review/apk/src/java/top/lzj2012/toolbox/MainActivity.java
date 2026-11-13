package top.lzj2012.toolbox;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
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

    private WebView web;
    private ApprovalPanel approval;
    private TextView tabChat;
    private TextView tabApproval;
    private final Handler ui = new Handler(Looper.getMainLooper());

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(buildUi());
        setupStatusBar();
        setupWebView();
        showTab(0);
        syncAuth();
        web.loadUrl(CHAT);
        handleIntent(getIntent());
    }

    private int dp(int v) { return Math.round(getResources().getDisplayMetrics().density * v); }

    private View buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.WHITE);

        FrameLayout content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1f));

        web = new WebView(this);
        approval = new ApprovalPanel(this, new ApprovalPanel.LoginListener() {
            @Override public void onLoggedIn(String token) { syncWeb(token); }
        });
        content.addView(web, new FrameLayout.LayoutParams(-1, -1));
        content.addView(approval, new FrameLayout.LayoutParams(-1, -1));

        View divider = new View(this);
        divider.setBackgroundColor(0xFFE5E7EB);
        root.addView(divider, new LinearLayout.LayoutParams(-1, dp(1)));

        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setBackgroundColor(0xFFFFFFFF);
        bar.setPadding(dp(6), dp(4), dp(6), dp(4));
        tabChat = makeTab("聊天");
        tabApproval = makeTab("批准");
        bar.addView(tabChat, new LinearLayout.LayoutParams(0, dp(46), 1f));
        bar.addView(tabApproval, new LinearLayout.LayoutParams(0, dp(46), 1f));
        root.addView(bar, new LinearLayout.LayoutParams(-1, -2));

        tabChat.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { showTab(0); }
        });
        tabApproval.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { showTab(1); }
        });
        return root;
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
        approval.setVisibility(chat ? View.GONE : View.VISIBLE);
        tabChat.setTextColor(chat ? BLUE : GREY);
        tabApproval.setTextColor(chat ? GREY : BLUE);
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
        s.setUserAgentString(s.getUserAgentString() + " LZJToolbox/1.11.2");
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
            @Override public void onPageFinished(WebView view, String url) {
                // 不再自动勾选/隐藏“信任此设备”（R2-A-01）
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) Toast.makeText(MainActivity.this, "聊天加载失败，请检查网络", Toast.LENGTH_SHORT).show();
            }
        });
        web.setWebChromeClient(new WebChromeClient());
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
                    ui.post(new Runnable() { @Override public void run() { approval.setToken(tk); } });
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

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent == null || intent.getData() == null) return;
        Uri u = intent.getData();
        if ("lzjapp".equals(u.getScheme())) {
            if ("approve".equals(u.getHost())) {
                showTab(1);
                if (approval != null) approval.reload();
            } else if ("chat".equals(u.getHost())) {
                showTab(0);
            }
        }
    }

    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) { web.goBack(); return; }
        super.onBackPressed();
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
