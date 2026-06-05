package com.mrss.app.model;

public class WebScrapingRule {
    public long id;
    public Long feedId;
    public String name;
    public String type = "html";
    public String listUrl;
    public String baseUrl;
    public String itemSelector;
    public String titleSelector;
    public String linkSelector;
    public String summarySelector;
    public String contentSelector;
    public String authorSelector;
    public String dateSelector;
    public String coverSelector;
    public String nextPageSelector;
    public String pageUrlTemplate;
    public int maxPages = 1;
    public String requestHeaders;
    public String dateFormat;
    public String encoding;
    public boolean enabled = true;
    public long createdAt;
    public long updatedAt;
}
