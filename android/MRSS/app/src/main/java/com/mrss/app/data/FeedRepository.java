package com.mrss.app.data;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.text.TextUtils;

import com.mrss.app.model.Article;
import com.mrss.app.model.ArticleTranslation;
import com.mrss.app.model.AiChannel;
import com.mrss.app.model.Category;
import com.mrss.app.model.Feed;
import com.mrss.app.model.KeywordSubscription;
import com.mrss.app.model.OpmlFeed;
import com.mrss.app.model.ParsedArticle;
import com.mrss.app.model.ParsedFeed;
import com.mrss.app.model.Stats;
import com.mrss.app.model.TranslationJob;
import com.mrss.app.model.WebScrapingRule;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;

public class FeedRepository {
    private final MrssDatabase database;

    public FeedRepository(Context context) {
        database = new MrssDatabase(context.getApplicationContext());
    }

    public synchronized long addFeed(String url, ParsedFeed parsedFeed) {
        return addFeed(url, parsedFeed, null, 3600);
    }

    public synchronized long addFeed(String url, ParsedFeed parsedFeed, Long categoryId, int fetchIntervalSeconds) {
        return addFeed(url, parsedFeed, categoryId, fetchIntervalSeconds, "off", "中文");
    }

    public synchronized long addFeed(String url, ParsedFeed parsedFeed, Long categoryId, int fetchIntervalSeconds, boolean translateEnabled, String translationLanguage) {
        return addFeed(url, parsedFeed, categoryId, fetchIntervalSeconds, translateEnabled ? "ai" : "off", translationLanguage);
    }

    public synchronized long addFeed(String url, ParsedFeed parsedFeed, Long categoryId, int fetchIntervalSeconds, String translationMode, String translationLanguage) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        String normalizedMode = normalizeTranslationMode(translationMode);
        db.beginTransaction();
        try {
            Long existing = findFeedIdByUrl(db, url);
            if (existing != null) {
                saveArticles(db, existing, parsedFeed);
                db.setTransactionSuccessful();
                return existing;
            }

            ContentValues values = new ContentValues();
            if (categoryId != null) {
                values.put("category_id", categoryId);
            }
            values.put("url", url);
            values.put("title", safeTitle(parsedFeed.title, url));
            values.put("description", parsedFeed.description);
            values.put("site_url", parsedFeed.siteUrl);
            values.put("icon_url", parsedFeed.iconUrl);
            values.put("fetch_interval", fetchIntervalSeconds);
            values.put("last_fetched_at", now);
            values.put("is_active", 1);
            values.put("translate_enabled", isTranslationEnabled(normalizedMode) ? 1 : 0);
            values.put("translation_mode", normalizedMode);
            values.put("translation_language", normalizeLanguage(translationLanguage));
            values.put("created_at", now);
            long feedId = db.insertOrThrow("feeds", null, values);
            saveArticles(db, feedId, parsedFeed);
            db.setTransactionSuccessful();
            return feedId;
        } finally {
            db.endTransaction();
        }
    }

    public synchronized int importOpmlFeeds(List<OpmlFeed> opmlFeeds, int defaultFetchIntervalSeconds) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        int imported = 0;
        db.beginTransaction();
        try {
            for (OpmlFeed opmlFeed : opmlFeeds) {
                if (opmlFeed.url == null || opmlFeed.url.trim().isEmpty() || findFeedIdByUrl(db, opmlFeed.url) != null) {
                    continue;
                }
                Long categoryId = null;
                if (opmlFeed.category != null && !opmlFeed.category.trim().isEmpty()) {
                    categoryId = getOrCreateCategory(db, opmlFeed.category.trim(), now);
                }
                ContentValues values = new ContentValues();
                if (categoryId != null) {
                    values.put("category_id", categoryId);
                }
                values.put("url", opmlFeed.url.trim());
                values.put("title", truncate(firstNonEmpty(opmlFeed.title, opmlFeed.url, "Untitled Feed"), 255));
                values.put("site_url", opmlFeed.siteUrl);
                values.put("fetch_interval", defaultFetchIntervalSeconds);
                values.put("is_active", 1);
                values.put("created_at", now);
                long rowId = db.insertWithOnConflict("feeds", null, values, SQLiteDatabase.CONFLICT_IGNORE);
                if (rowId != -1) {
                    imported++;
                }
            }
            db.setTransactionSuccessful();
            return imported;
        } finally {
            db.endTransaction();
        }
    }

    public synchronized int refreshFeed(Feed feed, ParsedFeed parsedFeed) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        db.beginTransaction();
        try {
            ContentValues values = new ContentValues();
            values.put("title", safeTitle(parsedFeed.title, feed.url));
            values.put("description", parsedFeed.description);
            values.put("site_url", parsedFeed.siteUrl);
            values.put("icon_url", parsedFeed.iconUrl);
            values.put("last_fetched_at", now);
            values.putNull("last_error");
            values.put("error_count", 0);
            values.put("updated_at", now);
            db.update("feeds", values, "id = ?", new String[]{String.valueOf(feed.id)});
            int inserted = saveArticles(db, feed.id, parsedFeed);
            db.setTransactionSuccessful();
            return inserted;
        } finally {
            db.endTransaction();
        }
    }

    public synchronized void markFeedError(long feedId, String error) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        ContentValues values = new ContentValues();
        values.put("last_error", error);
        values.put("last_fetched_at", now);
        values.put("updated_at", now);
        db.execSQL("UPDATE feeds SET error_count = error_count + 1 WHERE id = ?", new Object[]{feedId});
        db.update("feeds", values, "id = ?", new String[]{String.valueOf(feedId)});
    }

    public synchronized List<Feed> getFeeds() {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT f.*, " +
                "(SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id) AS article_count, " +
                "(SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id AND a.is_read = 0) AS unread_count " +
                "FROM feeds f ORDER BY f.position ASC, f.title COLLATE NOCASE ASC";
        List<Feed> feeds = new ArrayList<>();
        try (Cursor cursor = db.rawQuery(sql, null)) {
            while (cursor.moveToNext()) {
                feeds.add(readFeed(cursor));
            }
        }
        return feeds;
    }

    public synchronized List<Category> getCategories() {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT c.*, " +
                "(SELECT COUNT(*) FROM feeds f WHERE f.category_id = c.id) AS feed_count, " +
                "(SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id = a.feed_id WHERE f.category_id = c.id AND a.is_read = 0) AS unread_count " +
                "FROM categories c ORDER BY c.position ASC, c.name COLLATE NOCASE ASC";
        List<Category> categories = new ArrayList<>();
        try (Cursor cursor = db.rawQuery(sql, null)) {
            while (cursor.moveToNext()) {
                categories.add(readCategory(cursor));
            }
        }
        return categories;
    }

    public synchronized List<Feed> getDueFeeds(long now) {
        SQLiteDatabase db = database.getReadableDatabase();
        List<Feed> feeds = new ArrayList<>();
        String sql = "SELECT f.*, " +
                "(SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id) AS article_count, " +
                "(SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id AND a.is_read = 0) AS unread_count " +
                "FROM feeds f WHERE f.is_active = 1 AND (f.last_fetched_at = 0 OR f.last_fetched_at + f.fetch_interval * 1000 <= ?) " +
                "ORDER BY CASE WHEN f.last_fetched_at = 0 THEN 0 ELSE f.last_fetched_at + f.fetch_interval * 1000 END ASC";
        try (Cursor cursor = db.rawQuery(sql, new String[]{String.valueOf(now)})) {
            while (cursor.moveToNext()) {
                feeds.add(readFeed(cursor));
            }
        }
        return feeds;
    }

    public synchronized long getNextDueAt(long now) {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT MIN(CASE WHEN last_fetched_at = 0 THEN ? ELSE last_fetched_at + fetch_interval * 1000 END) " +
                "FROM feeds WHERE is_active = 1";
        return scalarLong(db, sql, new String[]{String.valueOf(now)});
    }

    public synchronized List<Article> getArticles(Long feedId, boolean unreadOnly, boolean favoritesOnly, String query) {
        return getArticles(feedId, null, null, unreadOnly, favoritesOnly, query, 0, 0, "published_at", true, 300, 0);
    }

    public synchronized List<Article> getArticles(Long feedId, Long categoryId, boolean unreadOnly, boolean favoritesOnly, String query) {
        return getArticles(feedId, categoryId, null, unreadOnly, favoritesOnly, query, 0, 0, "published_at", true);
    }

    public synchronized List<Article> getArticles(
            Long feedId,
            Long categoryId,
            Long keywordId,
            boolean unreadOnly,
            boolean favoritesOnly,
            String query,
            long dateFrom,
            long dateTo,
            String sortBy,
            boolean descending
    ) {
        return getArticles(feedId, categoryId, keywordId, unreadOnly, favoritesOnly, query, dateFrom, dateTo, sortBy, descending, 300, 0);
    }

    public synchronized List<Article> getArticles(
            Long feedId,
            Long categoryId,
            Long keywordId,
            boolean unreadOnly,
            boolean favoritesOnly,
            String query,
            long dateFrom,
            long dateTo,
            String sortBy,
            boolean descending,
            int limit,
            int offset
        ) {
        SQLiteDatabase db = database.getReadableDatabase();
        List<String> args = new ArrayList<>();
        StringBuilder where = buildArticleWhere(db, feedId, categoryId, keywordId, unreadOnly, favoritesOnly, query, dateFrom, dateTo, args);

        String orderColumn;
        if ("created_at".equals(sortBy)) {
            orderColumn = "a.created_at";
        } else if ("title".equals(sortBy)) {
            orderColumn = "a.title COLLATE NOCASE";
        } else {
            orderColumn = "CASE WHEN a.published_at = 0 THEN a.created_at ELSE a.published_at END";
        }
        String orderDirection = descending ? " DESC" : " ASC";

        String sql = "SELECT a.*, f.title AS feed_title, f.translation_mode AS feed_translation_mode FROM articles a " +
                "JOIN feeds f ON f.id = a.feed_id " +
                where +
                " ORDER BY " + orderColumn + orderDirection + " " +
                "LIMIT ? OFFSET ?";
        args.add(String.valueOf(Math.max(1, limit)));
        args.add(String.valueOf(Math.max(0, offset)));
        List<Article> articles = new ArrayList<>();
        try (Cursor cursor = db.rawQuery(sql, args.toArray(new String[0]))) {
            while (cursor.moveToNext()) {
                articles.add(readArticle(cursor));
            }
        }
        return articles;
    }

    public synchronized Article getArticle(long articleId) {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT a.*, f.title AS feed_title, f.translation_mode AS feed_translation_mode FROM articles a " +
                "JOIN feeds f ON f.id = a.feed_id " +
                "WHERE a.id = ? LIMIT 1";
        try (Cursor cursor = db.rawQuery(sql, new String[]{String.valueOf(articleId)})) {
            if (cursor.moveToFirst()) {
                return readArticle(cursor);
            }
        }
        return null;
    }

    public synchronized int countArticles(
            Long feedId,
            Long categoryId,
            boolean unreadOnly,
            boolean favoritesOnly,
            String query,
            long dateFrom,
            long dateTo
    ) {
        return countArticles(feedId, categoryId, null, unreadOnly, favoritesOnly, query, dateFrom, dateTo);
    }

    public synchronized int countArticles(
            Long feedId,
            Long categoryId,
            Long keywordId,
            boolean unreadOnly,
            boolean favoritesOnly,
            String query,
            long dateFrom,
            long dateTo
    ) {
        SQLiteDatabase db = database.getReadableDatabase();
        List<String> args = new ArrayList<>();
        StringBuilder where = buildArticleWhere(db, feedId, categoryId, keywordId, unreadOnly, favoritesOnly, query, dateFrom, dateTo, args);
        String sql = "SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id = a.feed_id " + where;
        return scalarInt(db, sql, args.toArray(new String[0]));
    }

    private StringBuilder buildArticleWhere(
            SQLiteDatabase db,
            Long feedId,
            Long categoryId,
            Long keywordId,
            boolean unreadOnly,
            boolean favoritesOnly,
            String query,
            long dateFrom,
            long dateTo,
            List<String> args
    ) {
        StringBuilder where = new StringBuilder(" WHERE 1 = 1");
        if (feedId != null) {
            where.append(" AND a.feed_id = ?");
            args.add(String.valueOf(feedId));
        }
        if (categoryId != null) {
            where.append(" AND f.category_id = ?");
            args.add(String.valueOf(categoryId));
        }
        if (keywordId != null) {
            KeywordSubscription keyword = getKeywordSubscription(db, keywordId);
            if (keyword == null || !keyword.active || keyword.keyword == null || keyword.keyword.trim().isEmpty()) {
                where.append(" AND 1 = 0");
            } else {
                appendKeywordWhere(where, args, keyword);
            }
        }
        if (unreadOnly) {
            where.append(" AND a.is_read = 0");
        }
        if (favoritesOnly) {
            where.append(" AND a.is_favorite = 1");
        }
        if (query != null && !query.trim().isEmpty()) {
            where.append(" AND (a.title LIKE ? OR a.content LIKE ? OR f.title LIKE ?)");
            String pattern = "%" + query.trim() + "%";
            args.add(pattern);
            args.add(pattern);
            args.add(pattern);
        }
        if (dateFrom > 0) {
            where.append(" AND CASE WHEN a.published_at = 0 THEN a.created_at ELSE a.published_at END >= ?");
            args.add(String.valueOf(dateFrom));
        }
        if (dateTo > 0) {
            where.append(" AND CASE WHEN a.published_at = 0 THEN a.created_at ELSE a.published_at END <= ?");
            args.add(String.valueOf(dateTo));
        }
        return where;
    }

    private void appendKeywordWhere(StringBuilder where, List<String> args, KeywordSubscription keyword) {
        List<String> clauses = new ArrayList<>();
        if (keyword.matchTitle == 1) {
            clauses.add("a.title LIKE ?");
        }
        if (keyword.matchContent == 1) {
            clauses.add("a.content LIKE ?");
        }
        if (keyword.matchAuthor == 1) {
            clauses.add("a.author LIKE ?");
        }
        if (keyword.matchFeedTitle == 1 && !isDigitsOnly(keyword.keyword)) {
            clauses.add("f.title LIKE ?");
        }
        if (clauses.isEmpty()) {
            clauses.add("a.title LIKE ?");
        }
        where.append(" AND (").append(TextUtils.join(" OR ", clauses)).append(")");
        String pattern = "%" + keyword.keyword.trim() + "%";
        for (int i = 0; i < clauses.size(); i++) {
            args.add(pattern);
        }
    }

    public synchronized Stats getStats() {
        SQLiteDatabase db = database.getReadableDatabase();
        Stats stats = new Stats();
        stats.categoryCount = scalarInt(db, "SELECT COUNT(*) FROM categories", null);
        stats.feedCount = scalarInt(db, "SELECT COUNT(*) FROM feeds", null);
        stats.activeFeedCount = scalarInt(db, "SELECT COUNT(*) FROM feeds WHERE is_active = 1", null);
        stats.articleCount = scalarInt(db, "SELECT COUNT(*) FROM articles", null);
        stats.unreadCount = scalarInt(db, "SELECT COUNT(*) FROM articles WHERE is_read = 0", null);
        stats.favoriteCount = scalarInt(db, "SELECT COUNT(*) FROM articles WHERE is_favorite = 1", null);
        Calendar calendar = Calendar.getInstance();
        calendar.set(Calendar.HOUR_OF_DAY, 0);
        calendar.set(Calendar.MINUTE, 0);
        calendar.set(Calendar.SECOND, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        long startOfToday = calendar.getTimeInMillis();
        long sevenDaysAgo = startOfToday - 6L * 86400000L;
        stats.todayCount = scalarInt(db, "SELECT COUNT(*) FROM articles WHERE CASE WHEN published_at = 0 THEN created_at ELSE published_at END >= ?", new String[]{String.valueOf(startOfToday)});
        stats.lastSevenDaysCount = scalarInt(db, "SELECT COUNT(*) FROM articles WHERE CASE WHEN published_at = 0 THEN created_at ELSE published_at END >= ?", new String[]{String.valueOf(sevenDaysAgo)});
        stats.latestArticleAt = scalarLong(db, "SELECT MAX(CASE WHEN published_at = 0 THEN created_at ELSE published_at END) FROM articles", null);
        return stats;
    }

    public synchronized List<KeywordSubscription> getKeywordSubscriptions() {
        SQLiteDatabase db = database.getReadableDatabase();
        List<KeywordSubscription> keywords = new ArrayList<>();
        try (Cursor cursor = db.rawQuery("SELECT * FROM keyword_subscriptions ORDER BY created_at ASC, name COLLATE NOCASE ASC", null)) {
            while (cursor.moveToNext()) {
                keywords.add(readKeywordSubscription(cursor));
            }
        }
        return keywords;
    }

    public synchronized KeywordSubscription getKeywordSubscription(long keywordId) {
        SQLiteDatabase db = database.getReadableDatabase();
        return getKeywordSubscription(db, keywordId);
    }

    private KeywordSubscription getKeywordSubscription(SQLiteDatabase db, long keywordId) {
        try (Cursor cursor = db.rawQuery("SELECT * FROM keyword_subscriptions WHERE id = ?", new String[]{String.valueOf(keywordId)})) {
            if (cursor.moveToFirst()) {
                return readKeywordSubscription(cursor);
            }
        }
        return null;
    }

    public synchronized long createKeywordSubscription(String name, String keyword) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        ContentValues values = new ContentValues();
        values.put("name", truncate(firstNonEmpty(name, keyword), 100));
        values.put("keyword", truncate(keyword.trim(), 200));
        values.put("is_active", 1);
        values.put("match_title", 1);
        values.put("match_content", 1);
        values.put("match_author", 0);
        values.put("match_feed_title", 0);
        values.put("created_at", now);
        values.put("updated_at", now);
        return db.insertOrThrow("keyword_subscriptions", null, values);
    }

    public synchronized void updateKeywordSubscription(long keywordId, String name, String keyword, boolean active) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("name", truncate(firstNonEmpty(name, keyword), 100));
        values.put("keyword", truncate(keyword.trim(), 200));
        values.put("is_active", active ? 1 : 0);
        values.put("updated_at", System.currentTimeMillis());
        db.update("keyword_subscriptions", values, "id = ?", new String[]{String.valueOf(keywordId)});
    }

    public synchronized void deleteKeywordSubscription(long keywordId) {
        SQLiteDatabase db = database.getWritableDatabase();
        db.delete("keyword_subscriptions", "id = ?", new String[]{String.valueOf(keywordId)});
    }

    public synchronized long createCategory(String name) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        Long existing = findCategoryIdByName(db, name);
        if (existing != null) {
            return existing;
        }
        ContentValues values = new ContentValues();
        values.put("name", truncate(name.trim(), 100));
        values.put("created_at", now);
        return db.insertOrThrow("categories", null, values);
    }

    public synchronized void renameCategory(long categoryId, String name) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("name", truncate(name.trim(), 100));
        values.put("updated_at", System.currentTimeMillis());
        db.update("categories", values, "id = ?", new String[]{String.valueOf(categoryId)});
    }

    public synchronized void deleteCategory(long categoryId) {
        SQLiteDatabase db = database.getWritableDatabase();
        db.delete("categories", "id = ?", new String[]{String.valueOf(categoryId)});
    }

    public synchronized void updateFeed(long feedId, String title, Long categoryId, int fetchIntervalSeconds, boolean active, boolean translateEnabled, String translationLanguage) {
        updateFeed(feedId, title, categoryId, fetchIntervalSeconds, active, translateEnabled ? "ai" : "off", translationLanguage);
    }

    public synchronized void updateFeed(long feedId, String title, Long categoryId, int fetchIntervalSeconds, boolean active, String translationMode, String translationLanguage) {
        SQLiteDatabase db = database.getWritableDatabase();
        String normalizedMode = normalizeTranslationMode(translationMode);
        ContentValues values = new ContentValues();
        values.put("title", truncate(firstNonEmpty(title, "Untitled Feed"), 255));
        if (categoryId == null) {
            values.putNull("category_id");
        } else {
            values.put("category_id", categoryId);
        }
        values.put("fetch_interval", fetchIntervalSeconds);
        values.put("is_active", active ? 1 : 0);
        values.put("translate_enabled", isTranslationEnabled(normalizedMode) ? 1 : 0);
        values.put("translation_mode", normalizedMode);
        values.put("translation_language", normalizeLanguage(translationLanguage));
        values.put("updated_at", System.currentTimeMillis());
        db.update("feeds", values, "id = ?", new String[]{String.valueOf(feedId)});
    }

    public synchronized void deleteFeed(long feedId) {
        SQLiteDatabase db = database.getWritableDatabase();
        db.delete("feeds", "id = ?", new String[]{String.valueOf(feedId)});
    }

    public synchronized List<WebScrapingRule> getWebScrapingRules() {
        SQLiteDatabase db = database.getReadableDatabase();
        List<WebScrapingRule> rules = new ArrayList<>();
        try (Cursor cursor = db.rawQuery("SELECT * FROM web_scraping_rules ORDER BY created_at ASC, name COLLATE NOCASE ASC", null)) {
            while (cursor.moveToNext()) {
                rules.add(readWebScrapingRule(cursor));
            }
        }
        return rules;
    }

    public synchronized long saveWebScrapingRule(WebScrapingRule rule) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        ContentValues values = webScrapingRuleValues(rule, now);
        if (rule.id > 0) {
            values.put("updated_at", now);
            db.update("web_scraping_rules", values, "id = ?", new String[]{String.valueOf(rule.id)});
            return rule.id;
        }
        values.put("created_at", now);
        values.put("updated_at", now);
        return db.insertOrThrow("web_scraping_rules", null, values);
    }

    public synchronized void deleteWebScrapingRule(long ruleId) {
        SQLiteDatabase db = database.getWritableDatabase();
        db.delete("web_scraping_rules", "id = ?", new String[]{String.valueOf(ruleId)});
    }

    public synchronized List<Feed> getFeedsForExport() {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT f.*, c.name AS category_name, " +
                "(SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id) AS article_count, " +
                "(SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id AND a.is_read = 0) AS unread_count " +
                "FROM feeds f LEFT JOIN categories c ON c.id = f.category_id " +
                "ORDER BY c.position ASC, c.name COLLATE NOCASE ASC, f.position ASC, f.title COLLATE NOCASE ASC";
        List<Feed> feeds = new ArrayList<>();
        try (Cursor cursor = db.rawQuery(sql, null)) {
            while (cursor.moveToNext()) {
                feeds.add(readFeed(cursor));
            }
        }
        return feeds;
    }

    public synchronized String exportBackupJson() throws Exception {
        SQLiteDatabase db = database.getReadableDatabase();
        JSONObject root = new JSONObject();
        root.put("schema_version", 1);
        root.put("exported_at", System.currentTimeMillis());
        root.put("categories", tableToJson(db, "SELECT * FROM categories ORDER BY id ASC"));
        root.put("feeds", tableToJson(db, "SELECT * FROM feeds ORDER BY id ASC"));
        root.put("web_scraping_rules", tableToJson(db, "SELECT * FROM web_scraping_rules ORDER BY id ASC"));
        root.put("articles", tableToJson(db, "SELECT * FROM articles ORDER BY id ASC"));
        return root.toString(2);
    }

    public synchronized String exportSubscriptionSyncJson() throws Exception {
        SQLiteDatabase db = database.getReadableDatabase();
        JSONObject root = new JSONObject();
        root.put("schema_version", 1);
        root.put("type", "mrss_subscriptions");
        root.put("exported_at", System.currentTimeMillis());
        root.put("categories", tableToJson(db, "SELECT id, name, description, position, created_at, updated_at FROM categories ORDER BY position ASC, name COLLATE NOCASE ASC"));
        root.put("feeds", tableToJson(db, "SELECT id, category_id, url, title, description, site_url, icon_url, fetch_interval, is_active, translate_enabled, translation_mode, translation_language, position, created_at, updated_at FROM feeds ORDER BY position ASC, title COLLATE NOCASE ASC"));
        root.put("keyword_subscriptions", tableToJson(db, "SELECT id, name, keyword, is_active, match_title, match_content, match_author, match_feed_title, created_at, updated_at FROM keyword_subscriptions ORDER BY created_at ASC"));
        root.put("web_scraping_rules", tableToJson(db, "SELECT id, feed_id, name, type, list_url, base_url, item_selector, title_selector, link_selector, summary_selector, content_selector, author_selector, date_selector, cover_selector, next_page_selector, page_url_template, max_pages, request_headers, date_format, encoding, enabled, created_at, updated_at FROM web_scraping_rules ORDER BY created_at ASC, name COLLATE NOCASE ASC"));
        return root.toString(2);
    }

    public synchronized int importSubscriptionSyncJson(String json) throws Exception {
        JSONObject root = new JSONObject(json);
        JSONArray categories = root.optJSONArray("categories");
        JSONArray feeds = root.optJSONArray("feeds");
        JSONArray keywordSubscriptions = root.optJSONArray("keyword_subscriptions");
        JSONArray webScrapingRules = root.optJSONArray("web_scraping_rules");
        if (categories == null || feeds == null) {
            throw new IllegalArgumentException("同步数据缺少 categories / feeds");
        }

        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        int changed = 0;
        db.beginTransaction();
        try {
            for (int i = 0; i < categories.length(); i++) {
                JSONObject category = categories.getJSONObject(i);
                String name = category.optString("name", "").trim();
                if (name.isEmpty()) {
                    continue;
                }
                Long categoryId = findCategoryIdByName(db, name);
                ContentValues values = new ContentValues();
                values.put("name", truncate(name, 100));
                values.put("description", nullableString(category, "description"));
                values.put("position", category.optInt("position", 0));
                values.put("updated_at", now);
                if (categoryId == null) {
                    values.put("created_at", category.optLong("created_at", now));
                    db.insertOrThrow("categories", null, values);
                    changed++;
                } else {
                    db.update("categories", values, "id = ?", new String[]{String.valueOf(categoryId)});
                    changed++;
                }
            }

            for (int i = 0; i < feeds.length(); i++) {
                JSONObject feed = feeds.getJSONObject(i);
                String url = feed.optString("url", "").trim();
                if (url.isEmpty()) {
                    continue;
                }
                Long categoryId = null;
                if (!feed.isNull("category_id")) {
                    String categoryName = categoryNameByExportId(categories, feed.optLong("category_id"));
                    if (categoryName != null && !categoryName.trim().isEmpty()) {
                        categoryId = getOrCreateCategory(db, categoryName.trim(), now);
                    }
                }
                Long existingFeedId = findFeedIdByUrl(db, url);
                ContentValues values = new ContentValues();
                if (categoryId == null) {
                    values.putNull("category_id");
                } else {
                    values.put("category_id", categoryId);
                }
                values.put("url", url);
                values.put("title", truncate(firstNonEmpty(feed.optString("title", null), url, "Untitled Feed"), 255));
                values.put("description", nullableString(feed, "description"));
                values.put("site_url", nullableString(feed, "site_url"));
                values.put("icon_url", nullableString(feed, "icon_url"));
                values.put("fetch_interval", feed.optInt("fetch_interval", 3600));
                values.put("is_active", feed.optInt("is_active", 1));
                String translationMode = normalizeTranslationMode(feed.optString("translation_mode", feed.optInt("translate_enabled", 0) == 1 ? "ai" : "off"));
                values.put("translate_enabled", isTranslationEnabled(translationMode) ? 1 : 0);
                values.put("translation_mode", translationMode);
                values.put("translation_language", normalizeLanguage(feed.optString("translation_language", "中文")));
                values.put("position", feed.optInt("position", 0));
                values.put("updated_at", now);
                if (existingFeedId == null) {
                    values.put("last_fetched_at", 0);
                    values.put("created_at", feed.optLong("created_at", now));
                    db.insertOrThrow("feeds", null, values);
                    changed++;
                } else {
                    db.update("feeds", values, "id = ?", new String[]{String.valueOf(existingFeedId)});
                    changed++;
                }
            }

            if (keywordSubscriptions != null) {
                for (int i = 0; i < keywordSubscriptions.length(); i++) {
                    JSONObject keyword = keywordSubscriptions.getJSONObject(i);
                    String keywordText = keyword.optString("keyword", "").trim();
                    if (keywordText.isEmpty()) {
                        continue;
                    }
                    Long existingKeywordId = findKeywordIdByKeyword(db, keywordText);
                    ContentValues values = new ContentValues();
                    values.put("name", truncate(firstNonEmpty(keyword.optString("name", null), keywordText), 100));
                    values.put("keyword", truncate(keywordText, 200));
                    values.put("is_active", keyword.optInt("is_active", 1));
                    values.put("match_title", keyword.optInt("match_title", 1));
                    values.put("match_content", keyword.optInt("match_content", 1));
                    values.put("match_author", keyword.optInt("match_author", 0));
                    values.put("match_feed_title", keyword.optInt("match_feed_title", 0));
                    values.put("updated_at", now);
                    if (existingKeywordId == null) {
                        values.put("created_at", keyword.optLong("created_at", now));
                        db.insertOrThrow("keyword_subscriptions", null, values);
                    } else {
                        db.update("keyword_subscriptions", values, "id = ?", new String[]{String.valueOf(existingKeywordId)});
                    }
                    changed++;
                }
            }
            if (webScrapingRules != null) {
                for (int i = 0; i < webScrapingRules.length(); i++) {
                    JSONObject rule = webScrapingRules.getJSONObject(i);
                    String listUrl = rule.optString("list_url", "").trim();
                    if (listUrl.isEmpty()) {
                        continue;
                    }
                    Long existingRuleId = findWebScrapingRuleIdByListUrl(db, listUrl);
                    Long feedId = null;
                    if (!rule.isNull("feed_id")) {
                        String feedUrl = feedUrlByExportId(feeds, rule.optLong("feed_id"));
                        if (feedUrl != null && !feedUrl.trim().isEmpty()) {
                            feedId = findFeedIdByUrl(db, feedUrl.trim());
                        }
                    }
                    ContentValues values = webScrapingRuleValues(rule, feedId, now);
                    values.put("updated_at", now);
                    if (existingRuleId == null) {
                        values.put("created_at", rule.optLong("created_at", now));
                        db.insertOrThrow("web_scraping_rules", null, values);
                    } else {
                        db.update("web_scraping_rules", values, "id = ?", new String[]{String.valueOf(existingRuleId)});
                    }
                    changed++;
                }
            }
            db.setTransactionSuccessful();
            return changed;
        } finally {
            db.endTransaction();
        }
    }

    public synchronized void restoreBackupJson(String json) throws Exception {
        JSONObject root = new JSONObject(json);
        JSONArray categories = root.optJSONArray("categories");
        JSONArray feeds = root.optJSONArray("feeds");
        JSONArray webScrapingRules = root.optJSONArray("web_scraping_rules");
        JSONArray articles = root.optJSONArray("articles");
        if (categories == null || feeds == null || articles == null) {
            throw new IllegalArgumentException("备份文件缺少 categories / feeds / articles");
        }

        SQLiteDatabase db = database.getWritableDatabase();
        db.beginTransaction();
        try {
            db.delete("articles", null, null);
            db.delete("web_scraping_rules", null, null);
            db.delete("feeds", null, null);
            db.delete("categories", null, null);
            insertJsonRows(db, "categories", categories);
            insertJsonRows(db, "feeds", feeds);
            if (webScrapingRules != null) {
                insertJsonRows(db, "web_scraping_rules", webScrapingRules);
            }
            insertJsonRows(db, "articles", articles);
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    public synchronized void markRead(long articleId) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("is_read", 1);
        values.put("read_at", System.currentTimeMillis());
        db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
    }

    public synchronized void markUnread(long articleId) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("is_read", 0);
        values.put("read_at", 0);
        db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
    }

    public synchronized boolean toggleFavorite(long articleId) {
        SQLiteDatabase db = database.getWritableDatabase();
        boolean next;
        try (Cursor cursor = db.rawQuery("SELECT is_favorite FROM articles WHERE id = ?", new String[]{String.valueOf(articleId)})) {
            if (!cursor.moveToFirst()) {
                return false;
            }
            next = cursor.getInt(0) == 0;
        }
        ContentValues values = new ContentValues();
        values.put("is_favorite", next ? 1 : 0);
        values.put("favorited_at", next ? System.currentTimeMillis() : 0);
        db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
        return next;
    }

    public synchronized int markAllRead(Long feedId) {
        return markAllRead(feedId, null);
    }

    public synchronized int markAllRead(Long feedId, Long categoryId) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("is_read", 1);
        values.put("read_at", System.currentTimeMillis());
        String where = "is_read = 0";
        List<String> argList = new ArrayList<>();
        if (feedId != null) {
            where += " AND feed_id = ?";
            argList.add(String.valueOf(feedId));
        } else if (categoryId != null) {
            where += " AND feed_id IN (SELECT id FROM feeds WHERE category_id = ?)";
            argList.add(String.valueOf(categoryId));
        }
        String[] args = argList.isEmpty() ? null : argList.toArray(new String[0]);
        return db.update("articles", values, where, args);
    }

    private int saveArticles(SQLiteDatabase db, long feedId, ParsedFeed parsedFeed) {
        int inserted = 0;
        long now = System.currentTimeMillis();
        for (ParsedArticle article : parsedFeed.articles) {
            ContentValues values = new ContentValues();
            values.put("feed_id", feedId);
            values.put("guid", truncate(firstNonEmpty(article.guid, article.link, article.title), 2048));
            values.put("link", truncate(article.link, 2048));
            values.put("title", truncate(firstNonEmpty(article.title, "Untitled"), 500));
            values.put("content", article.content);
            values.put("author", truncate(article.author, 500));
            values.put("published_at", article.publishedAt);
            values.put("created_at", now);
            long rowId = db.insertWithOnConflict("articles", null, values, SQLiteDatabase.CONFLICT_IGNORE);
            if (rowId != -1) {
                inserted++;
            }
        }
        return inserted;
    }

    public synchronized List<AiChannel> getAiChannels() {
        SQLiteDatabase db = database.getReadableDatabase();
        List<AiChannel> channels = new ArrayList<>();
        try (Cursor cursor = db.rawQuery("SELECT * FROM ai_channels ORDER BY is_default DESC, name COLLATE NOCASE ASC", null)) {
            while (cursor.moveToNext()) {
                channels.add(readAiChannel(cursor));
            }
        }
        return channels;
    }

    public synchronized AiChannel getDefaultAiChannel() {
        SQLiteDatabase db = database.getReadableDatabase();
        try (Cursor cursor = db.rawQuery("SELECT * FROM ai_channels ORDER BY is_default DESC, id ASC LIMIT 1", null)) {
            if (cursor.moveToFirst()) {
                return readAiChannel(cursor);
            }
        }
        return null;
    }

    public synchronized void saveAiChannels(List<AiChannel> channels) {
        SQLiteDatabase db = database.getWritableDatabase();
        long now = System.currentTimeMillis();
        db.beginTransaction();
        try {
            db.delete("ai_channels", null, null);
            boolean defaultWritten = false;
            for (AiChannel channel : channels) {
                if (channel.name == null || channel.name.trim().isEmpty()) {
                    continue;
                }
                ContentValues values = new ContentValues();
                values.put("name", truncate(channel.name.trim(), 100));
                values.put("provider", normalizeAiProvider(channel.provider, channel.baseUrl));
                values.put("base_url", channel.baseUrl);
                values.put("api_key", channel.apiKey);
                values.put("model", channel.model);
                values.put("models_json", modelsToJson(channel.models));
                boolean isDefault = channel.isDefault && !defaultWritten;
                values.put("is_default", isDefault ? 1 : 0);
                values.put("created_at", now);
                values.put("updated_at", now);
                db.insertOrThrow("ai_channels", null, values);
                defaultWritten = defaultWritten || isDefault;
            }
            if (!defaultWritten) {
                db.execSQL("UPDATE ai_channels SET is_default = 1 WHERE id = (SELECT id FROM ai_channels ORDER BY id ASC LIMIT 1)");
            }
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    public synchronized List<TranslationJob> pendingTranslationJobs(int limit) {
        return pendingTranslationJobs("ai", limit);
    }

    public synchronized List<TranslationJob> pendingTranslationJobs(String translationMode, int limit) {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT a.id AS article_id, a.feed_id, a.title, a.content, a.link, f.translation_language, f.translation_mode " +
                "FROM articles a JOIN feeds f ON f.id = a.feed_id " +
                "WHERE f.translate_enabled = 1 " +
                "AND f.translation_mode = ? " +
                "AND (a.translation_status IS NULL OR a.translation_status = '' OR a.translation_status = 'pending') " +
                "AND (a.original_content IS NULL OR a.original_content = '') " +
                "ORDER BY a.created_at DESC LIMIT ?";
        List<TranslationJob> jobs = new ArrayList<>();
        String normalizedMode = normalizeTranslationMode(translationMode);
        try (Cursor cursor = db.rawQuery(sql, new String[]{normalizedMode, String.valueOf(Math.max(1, limit))})) {
            while (cursor.moveToNext()) {
                TranslationJob job = new TranslationJob();
                job.articleId = getLong(cursor, "article_id");
                job.feedId = getLong(cursor, "feed_id");
                job.translationMode = normalizeTranslationMode(getString(cursor, "translation_mode"));
                job.title = getString(cursor, "title");
                job.content = getString(cursor, "content");
                job.link = getString(cursor, "link");
                job.targetLanguage = normalizeLanguage(getString(cursor, "translation_language"));
                jobs.add(job);
            }
        }
        return jobs;
    }

    public synchronized int countPendingTranslationJobs() {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT COUNT(*) " +
                "FROM articles a JOIN feeds f ON f.id = a.feed_id " +
                "WHERE f.translate_enabled = 1 " +
                "AND f.translation_mode IN ('ai', 'standard') " +
                "AND (a.translation_status IS NULL OR a.translation_status = '' OR a.translation_status = 'pending') " +
                "AND (a.original_content IS NULL OR a.original_content = '')";
        return scalarInt(db, sql, null);
    }

    public synchronized int countPendingTranslationJobs(String translationMode) {
        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT COUNT(*) " +
                "FROM articles a JOIN feeds f ON f.id = a.feed_id " +
                "WHERE f.translate_enabled = 1 " +
                "AND f.translation_mode = ? " +
                "AND (a.translation_status IS NULL OR a.translation_status = '' OR a.translation_status = 'pending') " +
                "AND (a.original_content IS NULL OR a.original_content = '')";
        return scalarInt(db, sql, new String[]{normalizeTranslationMode(translationMode)});
    }

    public synchronized int resetFailedTranslationsForFeed(long feedId) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("translation_status", "pending");
        values.putNull("translation_error");
        return db.update(
                "articles",
                values,
                "feed_id = ? AND translation_status = 'failed' AND (original_content IS NULL OR original_content = '')",
                new String[]{String.valueOf(feedId)}
        );
    }

    public synchronized void saveTranslation(long articleId, String language, ArticleTranslation translation) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        try (Cursor cursor = db.rawQuery("SELECT title, content FROM articles WHERE id = ?", new String[]{String.valueOf(articleId)})) {
            if (cursor.moveToFirst()) {
                values.put("original_title", getString(cursor, "title"));
                values.put("original_content", getString(cursor, "content"));
            }
        }
        values.put("title", firstNonEmpty(translation.title, "Untitled"));
        values.put("content", translation.content);
        values.put("translation_language", normalizeLanguage(language));
        values.put("translation_status", "done");
        values.putNull("translation_error");
        int updated = db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
        if (updated <= 0) {
            throw new IllegalStateException("翻译结果保存失败：文章不存在");
        }
    }

    public synchronized void markTranslationFailed(long articleId, String error) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("translation_status", "failed");
        values.put("translation_error", truncate(error == null ? "" : error, 1000));
        db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
    }

    public synchronized void saveTranslation(long articleId, String language, ArticleTranslation translation, String originalTitle, String originalContent) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("original_title", firstNonEmpty(originalTitle, ""));
        values.put("original_content", firstNonEmpty(originalContent, ""));
        values.put("title", firstNonEmpty(translation.title, "Untitled"));
        values.put("content", translation.content);
        values.put("translation_language", normalizeLanguage(language));
        values.put("translation_status", "done");
        values.putNull("translation_error");
        int updated = db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
        if (updated <= 0) {
            throw new IllegalStateException("翻译结果保存失败：文章不存在");
        }
    }

    private Long findFeedIdByUrl(SQLiteDatabase db, String url) {
        try (Cursor cursor = db.rawQuery("SELECT id FROM feeds WHERE url = ?", new String[]{url})) {
            if (cursor.moveToFirst()) {
                return cursor.getLong(0);
            }
        }
        return null;
    }

    private JSONArray tableToJson(SQLiteDatabase db, String sql) throws Exception {
        JSONArray rows = new JSONArray();
        try (Cursor cursor = db.rawQuery(sql, null)) {
            while (cursor.moveToNext()) {
                JSONObject row = new JSONObject();
                for (int i = 0; i < cursor.getColumnCount(); i++) {
                    String name = cursor.getColumnName(i);
                    if (cursor.isNull(i)) {
                        row.put(name, JSONObject.NULL);
                    } else {
                        int type = cursor.getType(i);
                        if (type == Cursor.FIELD_TYPE_INTEGER) {
                            row.put(name, cursor.getLong(i));
                        } else {
                            row.put(name, cursor.getString(i));
                        }
                    }
                }
                rows.put(row);
            }
        }
        return rows;
    }

    private void insertJsonRows(SQLiteDatabase db, String table, JSONArray rows) throws Exception {
        for (int i = 0; i < rows.length(); i++) {
            JSONObject row = rows.getJSONObject(i);
            ContentValues values = new ContentValues();
            JSONArray names = row.names();
            if (names == null) {
                continue;
            }
            for (int j = 0; j < names.length(); j++) {
                String name = names.getString(j);
                Object value = row.get(name);
                if (value == JSONObject.NULL) {
                    values.putNull(name);
                } else if (value instanceof Number) {
                    values.put(name, ((Number) value).longValue());
                } else {
                    values.put(name, String.valueOf(value));
                }
            }
            db.insertOrThrow(table, null, values);
        }
    }

    private int scalarInt(SQLiteDatabase db, String sql, String[] args) {
        return (int) scalarLong(db, sql, args);
    }

    private long scalarLong(SQLiteDatabase db, String sql, String[] args) {
        try (Cursor cursor = db.rawQuery(sql, args)) {
            if (cursor.moveToFirst() && !cursor.isNull(0)) {
                return cursor.getLong(0);
            }
        }
        return 0;
    }

    private Long findCategoryIdByName(SQLiteDatabase db, String name) {
        try (Cursor cursor = db.rawQuery("SELECT id FROM categories WHERE name = ?", new String[]{name})) {
            if (cursor.moveToFirst()) {
                return cursor.getLong(0);
            }
        }
        return null;
    }

    private Long findKeywordIdByKeyword(SQLiteDatabase db, String keyword) {
        try (Cursor cursor = db.rawQuery("SELECT id FROM keyword_subscriptions WHERE keyword = ?", new String[]{keyword})) {
            if (cursor.moveToFirst()) {
                return cursor.getLong(0);
            }
        }
        return null;
    }

    private Long findWebScrapingRuleIdByListUrl(SQLiteDatabase db, String listUrl) {
        try (Cursor cursor = db.rawQuery("SELECT id FROM web_scraping_rules WHERE list_url = ?", new String[]{listUrl})) {
            if (cursor.moveToFirst()) {
                return cursor.getLong(0);
            }
        }
        return null;
    }

    private Long getOrCreateCategory(SQLiteDatabase db, String name, long now) {
        Long existing = findCategoryIdByName(db, name);
        if (existing != null) {
            return existing;
        }
        ContentValues values = new ContentValues();
        values.put("name", truncate(name, 100));
        values.put("created_at", now);
        return db.insertOrThrow("categories", null, values);
    }

    private static String categoryNameByExportId(JSONArray categories, long exportId) throws Exception {
        for (int i = 0; i < categories.length(); i++) {
            JSONObject category = categories.getJSONObject(i);
            if (category.optLong("id", -1) == exportId) {
                return category.optString("name", null);
            }
        }
        return null;
    }

    private static String feedUrlByExportId(JSONArray feeds, long exportId) throws Exception {
        for (int i = 0; i < feeds.length(); i++) {
            JSONObject feed = feeds.getJSONObject(i);
            if (feed.optLong("id", -1) == exportId) {
                return feed.optString("url", null);
            }
        }
        return null;
    }

    private static String nullableString(JSONObject object, String key) {
        if (!object.has(key) || object.isNull(key)) {
            return null;
        }
        String value = object.optString(key, null);
        return value == null || value.trim().isEmpty() ? null : value;
    }

    private Feed readFeed(Cursor cursor) {
        Feed feed = new Feed();
        feed.id = getLong(cursor, "id");
        int categoryColumn = cursor.getColumnIndex("category_id");
        if (categoryColumn >= 0 && !cursor.isNull(categoryColumn)) {
            feed.categoryId = cursor.getLong(categoryColumn);
        }
        feed.categoryName = getString(cursor, "category_name");
        feed.url = getString(cursor, "url");
        feed.title = getString(cursor, "title");
        feed.description = getString(cursor, "description");
        feed.siteUrl = getString(cursor, "site_url");
        feed.iconUrl = getString(cursor, "icon_url");
        feed.fetchIntervalSeconds = getInt(cursor, "fetch_interval");
        feed.lastFetchedAt = getLong(cursor, "last_fetched_at");
        feed.lastError = getString(cursor, "last_error");
        feed.errorCount = getInt(cursor, "error_count");
        feed.active = getInt(cursor, "is_active") == 1;
        feed.translateEnabled = getInt(cursor, "translate_enabled") == 1;
        feed.translationMode = normalizeTranslationMode(getString(cursor, "translation_mode"));
        if (feed.translateEnabled && "off".equals(feed.translationMode)) {
            feed.translationMode = "ai";
        }
        feed.translationLanguage = normalizeLanguage(getString(cursor, "translation_language"));
        feed.position = getInt(cursor, "position");
        feed.articleCount = getInt(cursor, "article_count");
        feed.unreadCount = getInt(cursor, "unread_count");
        return feed;
    }

    private WebScrapingRule readWebScrapingRule(Cursor cursor) {
        WebScrapingRule rule = new WebScrapingRule();
        rule.id = getLong(cursor, "id");
        int feedIdIndex = cursor.getColumnIndex("feed_id");
        rule.feedId = feedIdIndex < 0 || cursor.isNull(feedIdIndex) ? null : cursor.getLong(feedIdIndex);
        rule.name = getString(cursor, "name");
        rule.type = normalizeWebScrapingRuleType(getString(cursor, "type"));
        rule.listUrl = getString(cursor, "list_url");
        rule.baseUrl = getString(cursor, "base_url");
        rule.itemSelector = getString(cursor, "item_selector");
        rule.titleSelector = getString(cursor, "title_selector");
        rule.linkSelector = getString(cursor, "link_selector");
        rule.summarySelector = getString(cursor, "summary_selector");
        rule.contentSelector = getString(cursor, "content_selector");
        rule.authorSelector = getString(cursor, "author_selector");
        rule.dateSelector = getString(cursor, "date_selector");
        rule.coverSelector = getString(cursor, "cover_selector");
        rule.nextPageSelector = getString(cursor, "next_page_selector");
        rule.pageUrlTemplate = getString(cursor, "page_url_template");
        rule.maxPages = clampMaxPages(getInt(cursor, "max_pages"));
        rule.requestHeaders = getString(cursor, "request_headers");
        rule.dateFormat = getString(cursor, "date_format");
        rule.encoding = getString(cursor, "encoding");
        rule.enabled = getInt(cursor, "enabled") != 0;
        rule.createdAt = getLong(cursor, "created_at");
        rule.updatedAt = getLong(cursor, "updated_at");
        return rule;
    }

    private ContentValues webScrapingRuleValues(WebScrapingRule rule, long now) {
        ContentValues values = new ContentValues();
        if (rule.feedId == null) {
            values.putNull("feed_id");
        } else {
            values.put("feed_id", rule.feedId);
        }
        values.put("name", truncate(firstNonEmpty(rule.name, rule.listUrl, "网页订阅"), 255));
        values.put("type", normalizeWebScrapingRuleType(rule.type));
        values.put("list_url", truncate(firstNonEmpty(rule.listUrl, ""), 2048));
        values.put("base_url", truncate(rule.baseUrl, 2048));
        values.put("item_selector", truncate(firstNonEmpty(rule.itemSelector, ""), 1000));
        values.put("title_selector", truncate(rule.titleSelector, 1000));
        values.put("link_selector", truncate(rule.linkSelector, 1000));
        values.put("summary_selector", truncate(rule.summarySelector, 1000));
        values.put("content_selector", truncate(rule.contentSelector, 1000));
        values.put("author_selector", truncate(rule.authorSelector, 1000));
        values.put("date_selector", truncate(rule.dateSelector, 1000));
        values.put("cover_selector", truncate(rule.coverSelector, 1000));
        values.put("next_page_selector", truncate(rule.nextPageSelector, 1000));
        values.put("page_url_template", truncate(rule.pageUrlTemplate, 2048));
        values.put("max_pages", clampMaxPages(rule.maxPages));
        values.put("request_headers", rule.requestHeaders);
        values.put("date_format", truncate(rule.dateFormat, 200));
        values.put("encoding", truncate(rule.encoding, 100));
        values.put("enabled", rule.enabled ? 1 : 0);
        values.put("updated_at", now);
        return values;
    }

    private ContentValues webScrapingRuleValues(JSONObject rule, Long feedId, long now) {
        ContentValues values = new ContentValues();
        if (feedId == null) {
            values.putNull("feed_id");
        } else {
            values.put("feed_id", feedId);
        }
        String listUrl = rule.optString("list_url", "").trim();
        values.put("name", truncate(firstNonEmpty(rule.optString("name", null), listUrl, "网页订阅"), 255));
        values.put("type", normalizeWebScrapingRuleType(rule.optString("type", "html")));
        values.put("list_url", truncate(listUrl, 2048));
        values.put("base_url", nullableString(rule, "base_url"));
        values.put("item_selector", truncate(firstNonEmpty(rule.optString("item_selector", null), ""), 1000));
        values.put("title_selector", nullableString(rule, "title_selector"));
        values.put("link_selector", nullableString(rule, "link_selector"));
        values.put("summary_selector", nullableString(rule, "summary_selector"));
        values.put("content_selector", nullableString(rule, "content_selector"));
        values.put("author_selector", nullableString(rule, "author_selector"));
        values.put("date_selector", nullableString(rule, "date_selector"));
        values.put("cover_selector", nullableString(rule, "cover_selector"));
        values.put("next_page_selector", nullableString(rule, "next_page_selector"));
        values.put("page_url_template", nullableString(rule, "page_url_template"));
        values.put("max_pages", clampMaxPages(rule.optInt("max_pages", 1)));
        values.put("request_headers", nullableString(rule, "request_headers"));
        values.put("date_format", nullableString(rule, "date_format"));
        values.put("encoding", nullableString(rule, "encoding"));
        values.put("enabled", rule.optInt("enabled", 1) == 0 ? 0 : 1);
        values.put("updated_at", now);
        return values;
    }

    private Category readCategory(Cursor cursor) {
        Category category = new Category();
        category.id = getLong(cursor, "id");
        category.name = getString(cursor, "name");
        category.description = getString(cursor, "description");
        category.position = getInt(cursor, "position");
        category.feedCount = getInt(cursor, "feed_count");
        category.unreadCount = getInt(cursor, "unread_count");
        return category;
    }

    private KeywordSubscription readKeywordSubscription(Cursor cursor) {
        KeywordSubscription keyword = new KeywordSubscription();
        keyword.id = getLong(cursor, "id");
        keyword.name = getString(cursor, "name");
        keyword.keyword = getString(cursor, "keyword");
        keyword.active = getInt(cursor, "is_active") == 1;
        keyword.matchTitle = getInt(cursor, "match_title");
        keyword.matchContent = getInt(cursor, "match_content");
        keyword.matchAuthor = getInt(cursor, "match_author");
        keyword.matchFeedTitle = getInt(cursor, "match_feed_title");
        keyword.createdAt = getLong(cursor, "created_at");
        keyword.updatedAt = getLong(cursor, "updated_at");
        return keyword;
    }

    private Article readArticle(Cursor cursor) {
        Article article = new Article();
        article.id = getLong(cursor, "id");
        article.feedId = getLong(cursor, "feed_id");
        article.feedTitle = getString(cursor, "feed_title");
        article.guid = getString(cursor, "guid");
        article.link = getString(cursor, "link");
        article.title = getString(cursor, "title");
        article.content = getString(cursor, "content");
        article.originalTitle = getString(cursor, "original_title");
        article.originalContent = getString(cursor, "original_content");
        article.feedTranslationMode = normalizeTranslationMode(getString(cursor, "feed_translation_mode"));
        article.translationLanguage = getString(cursor, "translation_language");
        article.translationStatus = getString(cursor, "translation_status");
        article.translationError = getString(cursor, "translation_error");
        article.author = getString(cursor, "author");
        article.publishedAt = getLong(cursor, "published_at");
        article.createdAt = getLong(cursor, "created_at");
        article.read = getInt(cursor, "is_read") == 1;
        article.favorite = getInt(cursor, "is_favorite") == 1;
        return article;
    }

    private AiChannel readAiChannel(Cursor cursor) {
        AiChannel channel = new AiChannel();
        channel.id = getLong(cursor, "id");
        channel.name = getString(cursor, "name");
        channel.provider = normalizeAiProvider(getString(cursor, "provider"), getString(cursor, "base_url"));
        channel.baseUrl = getString(cursor, "base_url");
        channel.apiKey = getString(cursor, "api_key");
        channel.model = getString(cursor, "model");
        channel.models = modelsFromJson(getString(cursor, "models_json"));
        if ((channel.models == null || channel.models.isEmpty()) && channel.model != null && !channel.model.trim().isEmpty()) {
            channel.models.add(channel.model.trim());
        }
        channel.isDefault = getInt(cursor, "is_default") == 1;
        return channel;
    }

    private String modelsToJson(List<String> models) {
        JSONArray array = new JSONArray();
        if (models != null) {
            for (String model : models) {
                if (model != null && !model.trim().isEmpty()) {
                    array.put(model.trim());
                }
            }
        }
        return array.toString();
    }

    private List<String> modelsFromJson(String json) {
        List<String> models = new ArrayList<>();
        if (json == null || json.trim().isEmpty()) {
            return models;
        }
        try {
            JSONArray array = new JSONArray(json);
            for (int i = 0; i < array.length(); i++) {
                String model = array.optString(i, "");
                if (!model.trim().isEmpty()) {
                    models.add(model);
                }
            }
        } catch (Exception ignored) {
        }
        return models;
    }

    private String normalizeAiProvider(String provider, String baseUrl) {
        if ("openai".equals(provider) && baseUrl != null && !baseUrl.trim().isEmpty()
                && !"https://api.openai.com/v1".equalsIgnoreCase(trimEnd(baseUrl.trim()))) {
            return "openai_compatible";
        }
        if ("gemini".equals(provider)) {
            return "gemini";
        }
        if ("qwen".equals(provider)) {
            return "qwen";
        }
        if ("doubao".equals(provider)) {
            return "doubao";
        }
        if ("deepseek".equals(provider)) {
            return "deepseek";
        }
        if ("kimi".equals(provider)) {
            return "kimi";
        }
        if ("zhipu".equals(provider)) {
            return "zhipu";
        }
        if ("openai_compatible".equals(provider)) {
            return "openai_compatible";
        }
        return "openai";
    }

    private String trimEnd(String value) {
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private String safeTitle(String title, String fallback) {
        String value = firstNonEmpty(title, fallback, "Untitled Feed");
        return truncate(value, 255);
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) {
                return value.trim();
            }
        }
        return "";
    }

    private static String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength);
    }

    private static boolean isDigitsOnly(String value) {
        if (value == null || value.trim().isEmpty()) {
            return false;
        }
        String trimmed = value.trim();
        for (int i = 0; i < trimmed.length(); i++) {
            if (!Character.isDigit(trimmed.charAt(i))) {
                return false;
            }
        }
        return true;
    }

    private static String normalizeLanguage(String value) {
        return value == null || value.trim().isEmpty() ? "中文" : value.trim();
    }

    private static String normalizeTranslationMode(String value) {
        if ("ai".equals(value) || "standard".equals(value)) {
            return value;
        }
        return "off";
    }

    private static boolean isTranslationEnabled(String mode) {
        return "ai".equals(mode) || "standard".equals(mode);
    }

    private static String normalizeWebScrapingRuleType(String value) {
        if ("json".equals(value) || "html".equals(value)) {
            return value;
        }
        return "html";
    }

    private static int clampMaxPages(int value) {
        if (value < 1) {
            return 1;
        }
        return Math.min(value, 20);
    }

    private static String getString(Cursor cursor, String name) {
        int index = cursor.getColumnIndex(name);
        if (index < 0 || cursor.isNull(index)) {
            return null;
        }
        return cursor.getString(index);
    }

    private static int getInt(Cursor cursor, String name) {
        int index = cursor.getColumnIndex(name);
        return index < 0 || cursor.isNull(index) ? 0 : cursor.getInt(index);
    }

    private static long getLong(Cursor cursor, String name) {
        int index = cursor.getColumnIndex(name);
        return index < 0 || cursor.isNull(index) ? 0L : cursor.getLong(index);
    }
}
