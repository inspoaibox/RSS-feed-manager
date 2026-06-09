package com.mrss.mobile.model;

public class Article {
    public long id;
    public long feedId;
    public String feedTitle;
    public String title;
    public String link;
    public String content;
    public String fullContent;
    public String summary;
    public String translation;
    public String author;
    public String publishedAt;
    public String createdAt;
    public String updatedAt;
    public boolean read;
    public boolean favorite;
    public String readAt;

    @Override
    public String toString() {
        String prefix = read ? "" : "• ";
        String source = feedTitle == null || feedTitle.trim().isEmpty() ? "" : "\n" + feedTitle;
        return prefix + title + source;
    }
}
