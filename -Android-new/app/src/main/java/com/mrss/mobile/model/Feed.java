package com.mrss.mobile.model;

public class Feed {
    public long id;
    public String url;
    public String title;
    public String description;
    public String siteUrl;
    public String iconUrl;
    public Long categoryId;
    public int fetchInterval;
    public String lastFetchedAt;
    public boolean autoTranslate;
    public boolean autoSummarize;
    public String targetLanguage;
    public String translateMethod;
    public boolean active;
    public boolean usePlaywright;
    public int position;
    public int unreadCount;
    public int articleCount;

    @Override
    public String toString() {
        if (id == 0) {
            return title;
        }
        return unreadCount > 0 ? title + " (" + unreadCount + ")" : title;
    }
}
