package top.lzj2012.toolbox;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;

import java.io.File;
import java.io.FileNotFoundException;

/** 只暴露缓存目录里的 update.apk，供系统安装器读取 */
public class ApkProvider extends ContentProvider {
    static final String AUTHORITY = "top.lzj2012.toolbox.apkprovider";

    static Uri uri() {
        return Uri.parse("content://" + AUTHORITY + "/update.apk");
    }

    @Override public boolean onCreate() { return true; }

    @Override public ParcelFileDescriptor openFile(Uri u, String mode) throws FileNotFoundException {
        if (getContext() == null || u == null || !"/update.apk".equals(u.getPath())) {
            throw new FileNotFoundException("bad uri");
        }
        File f = UpdateManager.apkFile(getContext());
        if (!f.isFile()) throw new FileNotFoundException("apk missing");
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override public String getType(Uri u) { return "application/vnd.android.package-archive"; }
    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public Uri insert(Uri u, ContentValues v) { return null; }
    @Override public int delete(Uri u, String s, String[] a) { return 0; }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { return 0; }
}
