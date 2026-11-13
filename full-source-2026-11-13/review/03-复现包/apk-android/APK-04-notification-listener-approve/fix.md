# APK-04 修复建议

## 1. 根因

审批是安全敏感的状态变更，但通知按钮用的是 **广播 PendingIntent**，接收方
`ActionReceiver` 收到就直接调用 `Api.approve()`。`FLAG_IMMUTABLE` 只阻止“发送方填充/改写 Intent”，
不阻止任何持有该 PendingIntent 的组件调用 `send()`；而通知监听应用（用户授予“通知使用权”即可）
能从 `Notification.Action.actionIntent` 直接拿到它。于是审批可以被“自动点击”，用户手势形同虚设。

## 2. 修改 A：把“允许/拒绝”改为需要用户确认的 Activity（推荐）

新增 `apk/src/java/top/lzj2012/toolbox/ConfirmActivity.java`（`exported="false"`）：

```java
public class ConfirmActivity extends Activity {
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        final int id = getIntent().getIntExtra("id", 0);
        final String name = getIntent().getStringExtra("name");
        if (id <= 0) { finish(); return; }
        new AlertDialog.Builder(this)
            .setTitle("确认进服请求")
            .setMessage(name + " 请求进入我的世界服务器")
            .setPositiveButton("允许", (d, w) -> act(id, true))
            .setNegativeButton("拒绝", (d, w) -> act(id, false))
            .setCancelable(true)
            .show();
    }
    private void act(final int id, final boolean allow) {
        final String tk = Prefs.token(this);
        if (tk.isEmpty()) { finish(); return; }
        new Thread(() -> {
            try { if (allow) Api.approve(tk, id); else Api.deny(tk, id); } catch (Exception ignored) { }
            runOnUiThread(this::finish);
        }).start();
    }
}
```

`Notifier.java:60-72` 改为：

```java
         Intent allow = new Intent(c, ConfirmActivity.class);
         allow.putExtra("id", p.id).putExtra("name", p.name)
              .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
         PendingIntent piAllow = PendingIntent.getActivity(c, 2000 + p.id, allow,
                 PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
```

`AndroidManifest.xml` 增加：

```xml
<activity android:name=".ConfirmActivity" android:exported="false"
          android:excludeFromRecents="true" android:noHistory="true" />
```

删除 `ActionReceiver`（或保留但只用于“打开审批页”，不再直接调用 approve），并从清单移除
`<receiver android:name=".ActionReceiver" .../>`。

## 3. 修改 B（最小改动）：广播前加“前台提示 + 时间戳”防自动触发

若暂时不改交互，可在 `ActionReceiver` 中拒绝非“用户最近交互”的广播：

```java
// 依赖：在主界面 onUserInteraction() 时记录 SystemClock.elapsedRealtime()
long since = SystemClock.elapsedRealtime() - Prefs.lastUserInteraction(c);
if (since > 60_000L) { Toast...; return; }   // 1 分钟内无真实触摸则拒绝
```

> 注意：这不是根本修复（监听应用仍可 send()，只是成功率下降），仅作过渡。

## 4. 为什么能堵住复现路径

- 修改 A 把审批动作从“广播→直接调 API”改成“Activity→用户点确认→调 API”。
  通知监听应用 `send()` 只会拉起一个需要用户再次点击的确认框，无法完成审批；
  用户点“允许”本身就是不可伪造的手势。
- 顺带消除 `ActionReceiver` 的 `id` 直拼问题（改为 Activity 里校验 + 服务端仍做归属校验）。

## 5. 兼容 / 迁移风险

- 通知按钮行为从“一键完成”变为“打开确认框”，交互多一步，但安全性提升；
  可在确认框上加“记住此玩家”（服务端策略）来减少打扰。
- 旧版本已发出的通知（其 PendingIntent 指向旧的 ActionReceiver）在升级后失效（点按无响应），
  建议升级后 `NotificationManager.cancelAll()` 并用新格式重发。
- `ConfirmActivity` 需要 `FLAG_ACTIVITY_NEW_TASK`（从通知/服务启动），已包含。
