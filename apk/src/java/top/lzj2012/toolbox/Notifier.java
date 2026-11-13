package top.lzj2012.toolbox;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;

public class Notifier {
    public static final String CH = "approval";
    public static final String CH_UPDATE = "update";
    public static final int ONGOING = 1001;
    public static final int NOTIF_BASE = 10000;

    public static void ensureChannel(Context c) {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            NotificationChannel ch = new NotificationChannel(CH, "服务通知", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("服务器准入审批与账号状态");
            ch.enableVibration(true);
            ch.setVibrationPattern(new long[]{0, 400, 200, 400});
            nm.createNotificationChannel(ch);
            NotificationChannel up = new NotificationChannel(CH_UPDATE, "版本更新", NotificationManager.IMPORTANCE_HIGH);
            up.setDescription("应用版本更新提醒");
            nm.createNotificationChannel(up);
        }
    }

    public static boolean enabled(Context c) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 24 && !nm.areNotificationsEnabled()) return false;
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = nm.getNotificationChannel(CH);
            if (ch != null && ch.getImportance() == NotificationManager.IMPORTANCE_NONE) return false;
        }
        return true;
    }

    public static Notification ongoing(Context c) {
        Intent i = new Intent(c, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(c, 900, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CH)
                : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle("LZJ 通讯")
                .setContentText("正在接收审批与更新通知")
                .setOngoing(true)
                .setContentIntent(pi);
        return b.build();
    }

    public static void showApproval(Context c, Api.Pending p) {
        ensureChannel(c);
        if (!enabled(c)) return;
        Intent open = new Intent(c, MainActivity.class);
        open.putExtra("approval", true);
        open.putExtra("approval_id", p.id);
        open.putExtra("approval_name", p.name);
        open.putExtra("approval_code", p.code);
        PendingIntent piOpen = PendingIntent.getActivity(c, 1000 + p.id, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent allow = new Intent(c, ActionReceiver.class);
        allow.setAction("top.lzj2012.toolbox.ALLOW");
        allow.putExtra("id", p.id);
        allow.putExtra("name", p.name);
        PendingIntent piAllow = PendingIntent.getBroadcast(c, 2000 + p.id, allow,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent deny = new Intent(c, ActionReceiver.class);
        deny.setAction("top.lzj2012.toolbox.DENY");
        deny.putExtra("id", p.id);
        deny.putExtra("name", p.name);
        PendingIntent piDeny = PendingIntent.getBroadcast(c, 3000 + p.id, deny,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CH)
                : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle("服务器准入申请")
                .setContentText(p.name + " 申请进入 Minecraft 服务器")
                .setSubText("认证链接 " + p.code)
                .setPriority(Notification.PRIORITY_HIGH)
                .setDefaults(Notification.DEFAULT_ALL)
                .setVibrate(new long[]{0, 400, 200, 400})
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setAutoCancel(true)
                .setContentIntent(piOpen)
                .addAction(new Notification.Action.Builder(
                        Icon.createWithResource(c, android.R.drawable.stat_notify_chat),
                        "批准", piAllow).build())
                .addAction(new Notification.Action.Builder(
                        Icon.createWithResource(c, android.R.drawable.stat_notify_chat),
                        "拒绝", piDeny).build());
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.notify(NOTIF_BASE + p.id, b.build());
    }

    public static void showLoginExpired(Context c) {
        ensureChannel(c);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CH)
                : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.stat_notify_error)
                .setContentTitle("登录状态已失效")
                .setContentText("请打开应用重新登录")
                .setAutoCancel(true);
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.notify(ONGOING + 1, b.build());
    }

    public static void showUpdate(Context c, String versionName, String notes) {
        ensureChannel(c);
        if (!enabled(c)) return;
        Intent open = new Intent(c, MainActivity.class);
        open.putExtra("ota_prompt", true);
        PendingIntent pi = PendingIntent.getActivity(c, 11000, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String text = notes == null || notes.length() == 0 ? "点按查看并安装新版本" : notes;
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CH_UPDATE)
                : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle("发现新版本 v" + versionName)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setPriority(Notification.PRIORITY_HIGH)
                .setCategory(Notification.CATEGORY_RECOMMENDATION)
                .setAutoCancel(true)
                .setContentIntent(pi);
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.notify(11000, b.build());
    }

    public static void cancel(Context c, int id) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.cancel(NOTIF_BASE + id);
    }
}
