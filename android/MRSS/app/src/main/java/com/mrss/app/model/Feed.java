package com.mrss.app.model;

public class Feed {
    public long id;
    public Long categoryId;
    public String categoryName;
    public String url;
    public String title;
    public String description;
    public String siteUrl;
    public String iconUrl;
    public int fetchIntervalSeconds;
    public long lastFetchedAt;
    public String lastError;
    public int errorCount;
    public boolean active;
    public boolean translateEnabled;
    public String translationMode;
    public String translationLanguage;
    public int position;
    public int articleCount;
    public int unreadCount;

    public Feed() {
        active = true;
        fetchIntervalSeconds = 3600;
        translationMode = "off";
        translationLanguage = "中文";
    }
}
