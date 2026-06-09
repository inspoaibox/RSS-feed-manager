package com.mrss.mobile.data;

import android.content.Context;
import android.content.SharedPreferences;

public class AppSettings {
    private static final String PREFS = "mrss_mobile_settings";
    private static final String KEY_BASE_URL = "base_url";
    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_REFRESH_TOKEN = "refresh_token";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_LAST_SYNC_AT = "last_sync_at";

    private final SharedPreferences prefs;

    public AppSettings(Context context) {
        prefs = context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public String getBaseUrl() {
        return prefs.getString(KEY_BASE_URL, "");
    }

    public void setBaseUrl(String value) {
        prefs.edit().putString(KEY_BASE_URL, normalizeBaseUrl(value)).apply();
    }

    public String getAccessToken() {
        return prefs.getString(KEY_ACCESS_TOKEN, "");
    }

    public String getRefreshToken() {
        return prefs.getString(KEY_REFRESH_TOKEN, "");
    }

    public void saveTokens(String accessToken, String refreshToken) {
        prefs.edit()
                .putString(KEY_ACCESS_TOKEN, accessToken == null ? "" : accessToken)
                .putString(KEY_REFRESH_TOKEN, refreshToken == null ? "" : refreshToken)
                .apply();
    }

    public void clearSession() {
        prefs.edit()
                .remove(KEY_ACCESS_TOKEN)
                .remove(KEY_REFRESH_TOKEN)
                .remove(KEY_USERNAME)
                .remove(KEY_LAST_SYNC_AT)
                .apply();
    }

    public boolean isLoggedIn() {
        return !getAccessToken().trim().isEmpty() && !getRefreshToken().trim().isEmpty();
    }

    public String getUsername() {
        return prefs.getString(KEY_USERNAME, "");
    }

    public void setUsername(String username) {
        prefs.edit().putString(KEY_USERNAME, username == null ? "" : username).apply();
    }

    public String getLastSyncAt() {
        return prefs.getString(KEY_LAST_SYNC_AT, "");
    }

    public void setLastSyncAt(String value) {
        prefs.edit().putString(KEY_LAST_SYNC_AT, value == null ? "" : value).apply();
    }

    public static String normalizeBaseUrl(String value) {
        String base = value == null ? "" : value.trim();
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        String lower = base.toLowerCase();
        if (lower.endsWith("/api/v1")) {
            base = base.substring(0, base.length() - "/api/v1".length());
        } else if (lower.endsWith("/api")) {
            base = base.substring(0, base.length() - "/api".length());
        }
        return base;
    }
}
