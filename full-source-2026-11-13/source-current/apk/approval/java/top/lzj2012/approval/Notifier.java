package top.lzj2012.approval;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;

public class Notifier {
    public static final String CH = "approval";
    public static final int ONGOING = 1001;

    public static void ensureChannel(Context c) {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            NotificationChannel ch = new NotificationChannel(CH, "进服批准", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("我的世界进服请求");
            ch.enableVibration(true);
            nm.createNotificationChannel(ch);
        }
    }

    public static Notification ongoing(Context c) {
        Intent i = new Intent(c, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(c, 900, i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CH)
                : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle("LZJ 批准")
                .setContentText("正在监听进服请求")
                .setOngoing(true)
                .setContentIntent(pi);
        return b.build();
    }

    public static void showApproval(Context c, Api.Pending p) {
        ensureChannel(c);
        Intent open = new Intent(c, MainActivity.class);
        PendingIntent piOpen = PendingIntent.getActivity(c, 1000 + p.id, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent allow = new Intent(c, ActionReceiver.class);
        allow.setAction("top.lzj2012.approval.ALLOW");
        allow.putExtra("id", p.id);
        allow.putExtra("name", p.name);
        PendingIntent piAllow = PendingIntent.getBroadcast(c, 2000 + p.id, allow,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent deny = new Intent(c, ActionReceiver.class);
        deny.setAction("top.lzj2012.approval.DENY");
        deny.putExtra("id", p.id);
        deny.putExtra("name", p.name);
        PendingIntent piDeny = PendingIntent.getBroadcast(c, 3000 + p.id, deny,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(c, CH)
                : new Notification.Builder(c);
        b.setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle("进服请求")
                .setContentText(p.name + " 请求进入我的世界服务器")
                .setSubText("验证码 " + p.code)
                .setPriority(Notification.PRIORITY_HIGH)
                .setAutoCancel(true)
                .setContentIntent(piOpen)
                .addAction(new Notification.Action.Builder(
                        Icon.createWithResource(c, android.R.drawable.stat_notify_chat),
                        "允许", piAllow).build())
                .addAction(new Notification.Action.Builder(
                        Icon.createWithResource(c, android.R.drawable.stat_notify_chat),
                        "拒绝", piDeny).build());
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.notify(p.id, b.build());
    }

    public static void cancel(Context c, int id) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        nm.cancel(id);
    }
}
