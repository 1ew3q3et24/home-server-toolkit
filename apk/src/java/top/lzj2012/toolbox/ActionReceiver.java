package top.lzj2012.toolbox;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.widget.Toast;

public class ActionReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(final Context c, Intent i) {
        final int id = i.getIntExtra("id", 0);
        if (id <= 0) return;
        final boolean allow = "top.lzj2012.toolbox.ALLOW".equals(i.getAction());
        final String token = Prefs.token(c);
        Notifier.cancel(c, id);
        if (token.isEmpty()) {
            Toast.makeText(c, "请先打开应用登录", Toast.LENGTH_LONG).show();
            return;
        }
        final PendingResult pr = goAsync();
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    if (allow) Api.approve(token, id); else Api.deny(token, id);
                } catch (Exception e) {
                    WatchService.forget(id);
                } finally {
                    pr.finish();
                }
            }
        }).start();
    }
}
