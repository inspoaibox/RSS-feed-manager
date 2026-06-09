package com.mrss.mobile.model;

import java.util.ArrayList;
import java.util.List;

public class SyncResult {
    public String serverTime;
    public boolean hasMore;
    public Integer nextOffset;
    public final List<Category> categories = new ArrayList<>();
    public final List<Feed> feeds = new ArrayList<>();
    public final List<Article> articles = new ArrayList<>();
    public final List<ArticleState> states = new ArrayList<>();
}
