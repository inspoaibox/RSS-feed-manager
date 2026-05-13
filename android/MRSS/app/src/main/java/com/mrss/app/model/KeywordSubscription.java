package com.mrss.app.model;

public class KeywordSubscription {
    public long id;
    public String name;
    public String keyword;
    public boolean active;
    public int matchTitle = 1;
    public int matchContent = 1;
    public int matchAuthor = 0;
    public int matchFeedTitle = 1;
    public long createdAt;
    public long updatedAt;

    @Override
    public String toString() {
        return name == null || name.trim().isEmpty() ? keyword : name;
    }
}
