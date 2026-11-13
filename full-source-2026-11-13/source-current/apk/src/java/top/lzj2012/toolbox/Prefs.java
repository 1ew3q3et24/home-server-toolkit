package top.lzj2012.toolbox;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public class Prefs {
    private static final String SP = "lzj_approval";
    private static final String ALIAS = "lzj_token_key";
    private static final String K_TOKEN = "token_enc";
    private static final String K_NAME = "nickname";
    private static final String K_OUT = "logged_out";

    private static SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (!ks.containsAlias(ALIAS)) {
            KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            kg.init(new KeyGenParameterSpec.Builder(ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            kg.generateKey();
        }
        return (SecretKey) ks.getKey(ALIAS, null);
    }

    public static void saveToken(Context c, String token) {
        try {
            Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
            ci.init(Cipher.ENCRYPT_MODE, key());
            byte[] iv = ci.getIV();
            byte[] ct = ci.doFinal(token.getBytes("UTF-8"));
            byte[] out = new byte[iv.length + ct.length];
            System.arraycopy(iv, 0, out, 0, iv.length);
            System.arraycopy(ct, 0, out, iv.length, ct.length);
            sp(c).edit().putString(K_TOKEN, Base64.encodeToString(out, Base64.NO_WRAP)).apply();
        } catch (Exception e) {
            sp(c).edit().remove(K_TOKEN).apply();
        }
    }

    public static String token(Context c) {
        String s = sp(c).getString(K_TOKEN, "");
        if (s == null || s.isEmpty()) return "";
        try {
            byte[] all = Base64.decode(s, Base64.NO_WRAP);
            byte[] iv = new byte[12];
            System.arraycopy(all, 0, iv, 0, 12);
            Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
            ci.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, iv));
            byte[] pt = ci.doFinal(all, 12, all.length - 12);
            return new String(pt, "UTF-8");
        } catch (Exception e) {
            return "";
        }
    }

    public static void clear(Context c) {
        sp(c).edit().remove(K_TOKEN).remove(K_NAME).apply();
    }

    public static void setName(Context c, String n) { sp(c).edit().putString(K_NAME, n).apply(); }
    public static void setLoggedOut(Context c, boolean v) { sp(c).edit().putBoolean(K_OUT, v).apply(); }
    public static boolean loggedOut(Context c) { return sp(c).getBoolean(K_OUT, false); }
    public static String name(Context c) { return sp(c).getString(K_NAME, ""); }

    private static SharedPreferences sp(Context c) {
        return c.getSharedPreferences(SP, Context.MODE_PRIVATE);
    }
}
