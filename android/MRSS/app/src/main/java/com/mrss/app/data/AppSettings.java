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
    private static final String KEY_DEFAULT_TRANSLATION_MODE = "default_translation_mode";
    private static final String KEY_STANDARD_TRANSLATION_PROVIDER = "standard_translation_provider";
    private static final String KEY_BAIDU_APP_ID = "baidu_translate_app_id";
    private static final String KEY_BAIDU_SECRET = "baidu_translate_secret";
    private static final String KEY_TENCENT_SECRET_ID = "tencent_translate_secret_id";
    private static final String KEY_TENCENT_SECRET_KEY = "tencent_translate_secret_key";
    private static final String KEY_TENCENT_REGION = "tencent_translate_region";
    private static final String KEY_GOOGLE_API_KEY = "google_translate_api_key";
    private static final String KEY_MICROSOFT_KEY = "microsoft_translate_key";
    private static final String KEY_MICROSOFT_REGION = "microsoft_translate_region";
    private static final String KEY_APP_LANGUAGE = "app_language";

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

    public String getDefaultTranslationMode() {
        return normalizeTranslationMode(preferences.getString(KEY_DEFAULT_TRANSLATION_MODE, "off"));
    }

    public void setDefaultTranslationMode(String mode) {
        preferences.edit().putString(KEY_DEFAULT_TRANSLATION_MODE, normalizeTranslationMode(mode)).apply();
    }

    public String getStandardTranslationProvider() {
        String value = preferences.getString(KEY_STANDARD_TRANSLATION_PROVIDER, "microsoft");
        if ("baidu".equals(value) || "tencent".equals(value) || "google".equals(value) || "microsoft".equals(value)) {
            return value;
        }
        return "microsoft";
    }

    public void setStandardTranslationProvider(String provider) {
        if (!"baidu".equals(provider) && !"tencent".equals(provider) && !"google".equals(provider) && !"microsoft".equals(provider)) {
            provider = "microsoft";
        }
        preferences.edit().putString(KEY_STANDARD_TRANSLATION_PROVIDER, provider).apply();
    }

    public String getBaiduTranslateAppId() {
        return preferences.getString(KEY_BAIDU_APP_ID, "");
    }

    public String getBaiduTranslateSecret() {
        return preferences.getString(KEY_BAIDU_SECRET, "");
    }

    public void setBaiduTranslateSettings(String appId, String secret) {
        preferences.edit()
                .putString(KEY_BAIDU_APP_ID, appId == null ? "" : appId.trim())
                .putString(KEY_BAIDU_SECRET, secret == null ? "" : secret.trim())
                .apply();
    }

    public String getTencentTranslateSecretId() {
        return preferences.getString(KEY_TENCENT_SECRET_ID, "");
    }

    public String getTencentTranslateSecretKey() {
        return preferences.getString(KEY_TENCENT_SECRET_KEY, "");
    }

    public String getTencentTranslateRegion() {
        String value = preferences.getString(KEY_TENCENT_REGION, "ap-beijing");
        return value == null || value.trim().isEmpty() ? "ap-beijing" : value.trim();
    }

    public void setTencentTranslateSettings(String secretId, String secretKey, String region) {
        preferences.edit()
                .putString(KEY_TENCENT_SECRET_ID, secretId == null ? "" : secretId.trim())
                .putString(KEY_TENCENT_SECRET_KEY, secretKey == null ? "" : secretKey.trim())
                .putString(KEY_TENCENT_REGION, region == null || region.trim().isEmpty() ? "ap-beijing" : region.trim())
                .apply();
    }

    public String getGoogleTranslateApiKey() {
        return preferences.getString(KEY_GOOGLE_API_KEY, "");
    }

    public void setGoogleTranslateApiKey(String apiKey) {
        preferences.edit().putString(KEY_GOOGLE_API_KEY, apiKey == null ? "" : apiKey.trim()).apply();
    }

    public String getMicrosoftTranslateKey() {
        return preferences.getString(KEY_MICROSOFT_KEY, "");
    }

    public String getMicrosoftTranslateRegion() {
        String value = preferences.getString(KEY_MICROSOFT_REGION, "global");
        return value == null || value.trim().isEmpty() ? "global" : value.trim();
    }

    public void setMicrosoftTranslateSettings(String key, String region) {
        preferences.edit()
                .putString(KEY_MICROSOFT_KEY, key == null ? "" : key.trim())
                .putString(KEY_MICROSOFT_REGION, region == null || region.trim().isEmpty() ? "global" : region.trim())
                .apply();
    }

    public String getAppLanguage() {
        String value = preferences.getString(KEY_APP_LANGUAGE, "zh");
        if ("en".equals(value)) {
            return "en";
        }
        return "zh";
    }

    public void setAppLanguage(String language) {
        preferences.edit()
                .putString(KEY_APP_LANGUAGE, "en".equals(language) ? "en" : "zh")
                .apply();
    }

    private String normalizeTranslationMode(String mode) {
        if ("ai".equals(mode) || "standard".equals(mode)) {
            return mode;
        }
        return "off";
    }
}
