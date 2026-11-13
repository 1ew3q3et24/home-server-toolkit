package top.lzj2012.toolbox;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public class WatchService extends Service {
    public static volatile boolean running = false;
    private Thread thread;
    private volatile boolean stop = false;
    private static final Set<Integer> notified = ConcurrentHashMap.newKeySet();
    private String lastSig = "";

    @Override public void onCreate() {
        super.onCreate();
        Notifier.ensureChannel(this);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(Notifier.ONGOING, Notifier.ongoing(this));
        running = true;
        if (thread == null) {
            thread = new Thread(new Runnable() { @Override public void run() { loop(); } });
            thread.start();
        }
        return START_STICKY;
    }

    private void loop() {
        while (!stop) {
            String token = Prefs.token(this);
            if (token.isEmpty()) break;
            try {
                JSONObject j;
                try {
                    j = Api.waitPoll(token, lastSig, 20);
                } catch (Exception e1) {
                    j = Api.waitSse(token, lastSig);
                }
                List<Api.Pending> ps = Api.parse(j);
                handle(ps);
                lastSig = j.optString("sig", "");
            } catch (Exception e) {
                if (e instanceof Api.ApiException && ((Api.ApiException) e).status == 401) {
                    Prefs.clear(this);
                    Notifier.showLoginExpired(this);
                    break;
                }
                try { handle(Api.pending(token)); } catch (Exception ignored) { }
                sleep(5000);
            }
        }
        running = false;
        stopSelf();
    }

    private void handle(List<Api.Pending> ps) {
        List<Integer> ids = new ArrayList<>();
        for (Api.Pending p : ps) {
            ids.add(p.id);
            if (!notified.contains(p.id)) {
                notified.add(p.id);
                Notifier.showApproval(this, p);
            }
        }
        for (Integer id : new ArrayList<>(notified)) {
            if (!ids.contains(id)) {
                Notifier.cancel(this, id);
                notified.remove(id);
            }
        }
    }

    public static void forget(int id) {
        notified.remove(id);
    }

    private void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) {}
    }

    @Override public void onDestroy() {
        stop = true;
        running = false;
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
