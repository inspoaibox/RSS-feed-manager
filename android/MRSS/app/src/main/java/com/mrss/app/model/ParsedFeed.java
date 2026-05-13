package com.mrss.app.model;

import java.util.ArrayList;
import java.util.List;

public class ParsedFeed {
    public String title;
    public String description;
    public String siteUrl;
    public String iconUrl;
    public final List<ParsedArticle> articles = new ArrayList<>();
}
