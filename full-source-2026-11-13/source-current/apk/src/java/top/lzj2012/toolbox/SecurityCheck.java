package top.lzj2012.toolbox;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;

import java.security.MessageDigest;

/** 加固版启动校验：签名不一致即拒绝运行，防止二次打包 */
public final class SecurityCheck {
    private static final String EXPECTED = "2a6bc75bc5fee503eca84268df388c7c7f777265e802927ae8a89d06d48a3dba";

    public static void verify(final Activity act) {
        try {
            PackageInfo pi = act.getPackageManager().getPackageInfo(act.getPackageName(), PackageManager.GET_SIGNATURES);
            Signature[] ss = pi.signatures;
            if (ss == null || ss.length == 0) throw new Exception("no signature");
            String got = hex(MessageDigest.getInstance("SHA-256").digest(ss[0].toByteArray()));
            if (EXPECTED.equalsIgnoreCase(got)) return;
        } catch (Exception ignored) { }
        new AlertDialog.Builder(act)
                .setTitle("安全校验失败")
                .setMessage("应用签名与发布版本不一致，可能已被篡改。请从官方渠道重新安装。")
                .setCancelable(false)
                .setPositiveButton("退出", new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) { act.finish(); }
                })
                .show();
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) sb.append(String.format("%02x", x & 0xff));
        return sb.toString();
    }
}
