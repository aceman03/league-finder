package com.aceman03.leaguefinder;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Downloads an update APK from a private GitHub release and opens Android's
 * installer, so updating doesn't need a browser signed in to GitHub.
 *
 *   install({ url, token }) -> { status: "installing" | "needs-permission" }
 *
 * url is the release asset's API URL (api.github.com/.../releases/assets/ID).
 * GitHub answers it with a redirect to a short-lived download link, which is
 * fetched without the token. Android still asks before installing; the first
 * time it also needs "install unknown apps" allowed for this app, so the call
 * opens that setting and reports "needs-permission".
 */
@CapacitorPlugin(name = "UpdateInstaller")
public class UpdateInstallerPlugin extends Plugin {
    private static final int MAX_REDIRECTS = 5;

    @PluginMethod
    public void install(PluginCall call) {
        String url = call.getString("url");
        String token = call.getString("token", "");
        if (url == null || !url.startsWith("https://api.github.com/")) {
            call.reject("Not a GitHub release asset URL.");
            return;
        }
        new Thread(() -> {
            try {
                File apk = download(url, token);
                if (!canInstall()) {
                    Intent allow = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:" + getContext().getPackageName()))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    getContext().startActivity(allow);
                    call.resolve(status("needs-permission"));
                    return;
                }
                Uri uri = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", apk);
                Intent install = new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                getContext().startActivity(install);
                call.resolve(status("installing"));
            } catch (Exception e) {
                call.reject("Couldn't download the update: " + e.getMessage());
            }
        }).start();
    }

    private boolean canInstall() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O
            || getContext().getPackageManager().canRequestPackageInstalls();
    }

    private static JSObject status(String value) {
        JSObject result = new JSObject();
        result.put("status", value);
        return result;
    }

    private File download(String url, String token) throws IOException {
        File dir = new File(getContext().getCacheDir(), "updates");
        if (!dir.isDirectory() && !dir.mkdirs()) throw new IOException("can't create the download folder");
        File apk = new File(dir, "League-Finder.apk");

        HttpURLConnection conn = null;
        boolean ok = false;
        String next = url;
        for (int hop = 0; hop <= MAX_REDIRECTS; hop++) {
            conn = (HttpURLConnection) new URL(next).openConnection();
            conn.setInstanceFollowRedirects(false);
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(60000);
            conn.setRequestProperty("User-Agent", "LeagueFinder");
            // Only GitHub's API gets the token; the redirect target is a pre-signed link.
            if (next.startsWith("https://api.github.com/")) {
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setRequestProperty("Accept", "application/octet-stream");
            }
            int code = conn.getResponseCode();
            if (code >= 300 && code < 400) {
                String location = conn.getHeaderField("Location");
                conn.disconnect();
                if (location == null || !location.startsWith("https://")) throw new IOException("bad redirect");
                next = location;
                continue;
            }
            if (code != 200) {
                conn.disconnect();
                throw new IOException("GitHub answered " + code);
            }
            ok = true;
            break;
        }
        if (!ok) throw new IOException("too many redirects");

        try (InputStream in = conn.getInputStream(); OutputStream out = new FileOutputStream(apk)) {
            byte[] buf = new byte[64 * 1024];
            int n;
            while ((n = in.read(buf)) != -1) out.write(buf, 0, n);
        } finally {
            conn.disconnect();
        }
        return apk;
    }
}
