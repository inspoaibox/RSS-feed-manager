package com.mrss.app.data;

import android.content.Context;
import android.content.SharedPreferences;

public class AppSettings {
    private static final String PREFS_NAME = "mrss_settings";
    private static final String KEY_DEFAULT_INTERVAL = "default_fetch_interval";
    private static final String KEY_BACKGROUND_SYNC = "background_sync_enabled";
    private static final String KEY_LAST_SYNC_COMPLETED_AT = "last_sync_completed_at";
    private static final String KEY_LAST_SYNC_TOTAL_NEW = "last_sync_total_new";
    private static final String KEY_LAST_SYNC_SUCCESS = "last_sync_success";
    private static final String KEY_LAST_SYNC_FAILED = "last_sync_failed";
    private static final String KEY_LAST_SYNC_CANDIDATES = "last_sync_candidates";
    private static final String KEY_GITHUB_TOKEN = "github_token";
    private static final String KEY_GIST_ID = "gist_id";
    private static final String KEY_GIST_FILENAME = "gist_filename";
    private static final String KEY_ARTICLE_PAGE_SIZE = "article_page_size";
    private static final String KEY_DEFAULT_TRANSLATION_LANGUAGE = "default_translation_language";

    private final SharedPreferences preferences;

    public AppSettings(Context context) {
        preferences = context.getApplicationContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    public int getDefaultFetchIntervalSeconds() {
        return preferences.getInt(KEY_DEFAULT_INTERVAL, 3600);
    }

    public void setDefaultFetchIntervalSeconds(int seconds) {
        preferences.edit().putInt(KEY_DEFAULT_INTERVAL, seconds).apply();
    }

    public int getArticlePageSize() {
        int pageSize = preferences.getInt(KEY_ARTICLE_PAGE_SIZE, 50);
        if (pageSize == 30 || pageSize == 50 || pageSize == 100 || pageSize == 200) {
            return pageSize;
        }
        return 50;
    }

    public void setArticlePageSize(int pageSize) {
        if (pageSize != 30 && pageSize != 50 && pageSize != 100 && pageSize != 200) {
            pageSize = 50;
        }
        preferences.edit().putInt(KEY_ARTICLE_PAGE_SIZE, pageSize).apply();
    }

    public boolean isBackgroundSyncEnabled() {
        return preferences.getBoolean(KEY_BACKGROUND_SYNC, true);
    }

    public void setBackgroundSyncEnabled(boolean enabled) {
        preferences.edit().putBoolean(KEY_BACKGROUND_SYNC, enabled).apply();
    }

    public void markSyncCompleted(int totalNew, int success, int failed, int candidates) {
        preferences.edit()
                .putLong(KEY_LAST_SYNC_COMPLETED_AT, System.currentTimeMillis())
                .putInt(KEY_LAST_SYNC_TOTAL_NEW, totalNew)
                .putInt(KEY_LAST_SYNC_SUCCESS, success)
                .putInt(KEY_LAST_SYNC_FAILED, failed)
                .putInt(KEY_LAST_SYNC_CANDIDATES, candidates)
                .apply();
    }

    public long getLastSyncCompletedAt() {
        return preferences.getLong(KEY_LAST_SYNC_COMPLETED_AT, 0L);
    }

    public int getLastSyncTotalNew() {
        return preferences.getInt(KEY_LAST_SYNC_TOTAL_NEW, 0);
    }

    public int getLastSyncSuccess() {
        return preferences.getInt(KEY_LAST_SYNC_SUCCESS, 0);
    }

    public int getLastSyncFailed() {
        return preferences.getInt(KEY_LAST_SYNC_FAILED, 0);
    }

    public int getLastSyncCandidates() {
        return preferences.getInt(KEY_LAST_SYNC_CANDIDATES, 0);
    }

    public String getGithubToken() {
        return preferences.getString(KEY_GITHUB_TOKEN, "");
    }

    public String getGistId() {
        return preferences.getString(KEY_GIST_ID, "");
    }

    public String getGistFilename() {
        return preferences.getString(KEY_GIST_FILENAME, "mrss-subscriptions.json");
    }

    public void setGistSettings(String token, String gistId, String filename) {
        preferences.edit()
                .putString(KEY_GITHUB_TOKEN, token == null ? "" : token)
                .putString(KEY_GIST_ID, gistId == null ? "" : gistId)
                .putString(KEY_GIST_FILENAME, filename == null || filename.trim().isEmpty() ? "mrss-subscriptions.json" : filename.trim())
                .apply();
    }

    public String getDefaultTranslationLanguage() {
        String value = preferences.getString(KEY_DEFAULT_TRANSLATION_LANGUAGE, "中文");
        return value == null || value.trim().isEmpty() ? "中文" : value.trim();
    }

    public void setDefaultTranslationLanguage(String language) {
        preferences.edit()
                .putString(KEY_DEFAULT_TRANSLATION_LANGUAGE, language == null || language.trim().isEmpty() ? "中文" : language.trim())
                .apply();
    }
}
