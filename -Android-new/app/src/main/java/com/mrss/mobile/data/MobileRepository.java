package com.mrss.mobile.data;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;

import com.mrss.mobile.model.Article;
import com.mrss.mobile.model.ArticleState;
import com.mrss.mobile.model.Category;
import com.mrss.mobile.model.Feed;
import com.mrss.mobile.model.PendingAction;
import com.mrss.mobile.model.SyncResult;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

public class MobileRepository {
    private final MobileDatabase database;

    public MobileRepository(Context context) {
        this.database = new MobileDatabase(context.getApplicationContext());
    }

    public void applySyncResult(SyncResult result, boolean replaceMetadata) {
        SQLiteDatabase db = database.getWritableDatabase();
        db.beginTransaction();
        try {
            if (replaceMetadata) {
                db.delete("categories", null, null);
                db.delete("feeds", null, null);
            }
            for (Category category : result.categories) {
                upsertCategory(db, category);
            }
            for (Feed feed : result.feeds) {
                upsertFeed(db, feed);
            }
            for (Article article : result.articles) {
                upsertArticle(db, article);
            }
            for (ArticleState state : result.states) {
                applyArticleState(db, state);
            }
            if (replaceMetadata) {
                db.execSQL("DELETE FROM articles WHERE feed_id NOT IN (SELECT id FROM feeds)");
            }
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    public List<Category> getCategoriesWithAll() {
        List<Category> categories = new ArrayList<>();
        Category all = new Category();
        all.id = 0;
        all.name = "全部分类";
        categories.add(all);

        SQLiteDatabase db = database.getReadableDatabase();
        try (Cursor cursor = db.rawQuery(
                "SELECT id, name, description, position, feed_count, unread_count FROM categories ORDER BY position ASC, name ASC",
                null)) {
            while (cursor.moveToNext()) {
                categories.add(readCategory(cursor));
            }
        }
        return categories;
    }

    public List<Feed> getFeedsWithAll(Long categoryId) {
        List<Feed> feeds = new ArrayList<>();
        Feed all = new Feed();
        all.id = 0;
        all.title = "全部订阅";
        feeds.add(all);

        SQLiteDatabase db = database.getReadableDatabase();
        String sql = "SELECT id, url, title, description, site_url, icon_url, category_id, fetch_interval, last_fetched_at, " +
                "auto_translate, auto_summarize, target_language, translate_method, is_active, use_playwright, position, unread_count, article_count " +
                "FROM feeds";
        String[] args = null;
        if (categoryId != null && categoryId > 0) {
            sql += " WHERE category_id = ?";
            args = new String[]{String.valueOf(categoryId)};
        }
        sql += " ORDER BY position ASC, title ASC";

        try (Cursor cursor = db.rawQuery(sql, args)) {
            while (cursor.moveToNext()) {
                feeds.add(readFeed(cursor));
            }
        }
        return feeds;
    }

    public List<Article> getArticles(Long categoryId, Long feedId, boolean unreadOnly, boolean favoritesOnly, String query, int page, int pageSize) {
        SQLiteDatabase db = database.getReadableDatabase();
        List<String> where = new ArrayList<>();
        List<String> args = new ArrayList<>();

        if (categoryId != null && categoryId > 0) {
            where.add("feeds.category_id = ?");
            args.add(String.valueOf(categoryId));
        }
        if (feedId != null && feedId > 0) {
            where.add("articles.feed_id = ?");
            args.add(String.valueOf(feedId));
        }
        if (unreadOnly) {
            where.add("articles.is_read = 0");
        }
        if (favoritesOnly) {
            where.add("articles.is_favorite = 1");
        }
        if (query != null && !query.trim().isEmpty()) {
            where.add("(articles.title LIKE ? OR articles.content LIKE ? OR articles.summary LIKE ? OR articles.translation LIKE ? OR articles.feed_title LIKE ?)");
            String pattern = "%" + query.trim() + "%";
            args.add(pattern);
            args.add(pattern);
            args.add(pattern);
            args.add(pattern);
            args.add(pattern);
        }

        StringBuilder sql = new StringBuilder();
        sql.append("SELECT articles.id, articles.feed_id, articles.feed_title, articles.title, articles.link, articles.content, ")
                .append("articles.full_content, articles.summary, articles.translation, articles.author, articles.published_at, ")
                .append("articles.created_at, articles.updated_at, articles.is_read, articles.is_favorite, articles.read_at ")
                .append("FROM articles LEFT JOIN feeds ON articles.feed_id = feeds.id");
        if (!where.isEmpty()) {
            sql.append(" WHERE ").append(String.join(" AND ", where));
        }
        sql.append(" ORDER BY COALESCE(articles.published_at, articles.created_at) DESC, articles.id DESC LIMIT ? OFFSET ?");
        args.add(String.valueOf(pageSize));
        args.add(String.valueOf(Math.max(0, page) * pageSize));

        List<Article> articles = new ArrayList<>();
        try (Cursor cursor = db.rawQuery(sql.toString(), args.toArray(new String[0]))) {
            while (cursor.moveToNext()) {
                articles.add(readArticle(cursor));
            }
        }
        return articles;
    }

    public Article getArticle(long articleId) {
        SQLiteDatabase db = database.getReadableDatabase();
        try (Cursor cursor = db.rawQuery(
                "SELECT id, feed_id, feed_title, title, link, content, full_content, summary, translation, author, published_at, created_at, updated_at, is_read, is_favorite, read_at FROM articles WHERE id = ?",
                new String[]{String.valueOf(articleId)})) {
            if (cursor.moveToFirst()) {
                return readArticle(cursor);
            }
        }
        return null;
    }

    public void setRead(long articleId, boolean read, boolean enqueue) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("is_read", read ? 1 : 0);
        values.put("read_at", read ? String.valueOf(System.currentTimeMillis()) : null);
        db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
        if (enqueue) {
            enqueueAction(read ? "mark_read" : "mark_unread", articleId, null);
        }
    }

    public void setFavorite(long articleId, boolean favorite, boolean enqueue) {
        SQLiteDatabase db = database.getWritableDatabase();
        ContentValues values = new ContentValues();
        values.put("is_favorite", favorite ? 1 : 0);
        db.update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
        if (enqueue) {
            enqueueAction("set_favorite", articleId, favorite);
        }
    }

    public void updateArticleTranslation(long articleId, String translation) {
        ContentValues values = new ContentValues();
        values.put("translation", translation);
        database.getWritableDatabase().update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
    }

    public void updateArticleSummary(long articleId, String summary) {
        ContentValues values = new ContentValues();
        values.put("summary", summary);
        database.getWritableDatabase().update("articles", values, "id = ?", new String[]{String.valueOf(articleId)});
    }

    public List<PendingAction> getPendingActions(int limit) {
        SQLiteDatabase db = database.getReadableDatabase();
        List<PendingAction> actions = new ArrayList<>();
        try (Cursor cursor = db.rawQuery(
                "SELECT id, client_action_id, type, article_id, value, created_at FROM pending_actions ORDER BY created_at ASC LIMIT ?",
                new String[]{String.valueOf(limit)})) {
            while (cursor.moveToNext()) {
                PendingAction action = new PendingAction();
                action.id = cursor.getLong(0);
                action.clientActionId = cursor.getString(1);
                action.type = cursor.getString(2);
                action.articleId = cursor.getLong(3);
                action.value = cursor.isNull(4) ? null : cursor.getInt(4) == 1;
                action.createdAt = cursor.getLong(5);
                actions.add(action);
            }
        }
        return actions;
    }

    public void deletePendingActions(List<PendingAction> actions) {
        if (actions == null || actions.isEmpty()) {
            return;
        }
        SQLiteDatabase db = database.getWritableDatabase();
        db.beginTransaction();
        try {
            for (PendingAction action : actions) {
                db.delete("pending_actions", "id = ?", new String[]{String.valueOf(action.id)});
            }
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    public void clearAll() {
        SQLiteDatabase db = database.getWritableDatabase();
        db.beginTransaction();
        try {
            db.delete("pending_actions", null, null);
            db.delete("articles", null, null);
            db.delete("feeds", null, null);
            db.delete("categories", null, null);
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    public void clearCachedContent() {
        SQLiteDatabase db = database.getWritableDatabase();
        db.beginTransaction();
        try {
            db.delete("articles", null, null);
            db.delete("feeds", null, null);
            db.delete("categories", null, null);
            db.setTransactionSuccessful();
        } finally {
            db.endTransaction();
        }
    }

    private void enqueueAction(String type, long articleId, Boolean value) {
        ContentValues values = new ContentValues();
        values.put("client_action_id", UUID.randomUUID().toString());
        values.put("type", type);
        values.put("article_id", articleId);
        if (value != null) {
            values.put("value", value ? 1 : 0);
        } else {
            values.putNull("value");
        }
        values.put("created_at", System.currentTimeMillis());
        database.getWritableDatabase().insert("pending_actions", null, values);
    }

    private void upsertCategory(SQLiteDatabase db, Category category) {
        ContentValues values = new ContentValues();
        values.put("id", category.id);
        values.put("name", category.name);
        values.put("description", category.description);
        values.put("position", category.position);
        values.put("feed_count", category.feedCount);
        values.put("unread_count", category.unreadCount);
        db.insertWithOnConflict("categories", null, values, SQLiteDatabase.CONFLICT_REPLACE);
    }

    private void upsertFeed(SQLiteDatabase db, Feed feed) {
        ContentValues values = new ContentValues();
        values.put("id", feed.id);
        values.put("url", feed.url);
        values.put("title", feed.title);
        values.put("description", feed.description);
        values.put("site_url", feed.siteUrl);
        values.put("icon_url", feed.iconUrl);
        if (feed.categoryId != null) {
            values.put("category_id", feed.categoryId);
        } else {
            values.putNull("category_id");
        }
        values.put("fetch_interval", feed.fetchInterval);
        values.put("last_fetched_at", feed.lastFetchedAt);
        values.put("auto_translate", feed.autoTranslate ? 1 : 0);
        values.put("auto_summarize", feed.autoSummarize ? 1 : 0);
        values.put("target_language", feed.targetLanguage);
        values.put("translate_method", feed.translateMethod == null ? "none" : feed.translateMethod);
        values.put("is_active", feed.active ? 1 : 0);
        values.put("use_playwright", feed.usePlaywright ? 1 : 0);
        values.put("position", feed.position);
        values.put("unread_count", feed.unreadCount);
        values.put("article_count", feed.articleCount);
        db.insertWithOnConflict("feeds", null, values, SQLiteDatabase.CONFLICT_REPLACE);
    }

    private void upsertArticle(SQLiteDatabase db, Article article) {
        ContentValues values = new ContentValues();
        values.put("id", article.id);
        values.put("feed_id", article.feedId);
        values.put("feed_title", article.feedTitle);
        values.put("title", article.title);
        values.put("link", article.link);
        values.put("content", article.content);
        values.put("full_content", article.fullContent);
        values.put("summary", article.summary);
        values.put("translation", article.translation);
        values.put("author", article.author);
        values.put("published_at", article.publishedAt);
        values.put("created_at", article.createdAt);
        values.put("updated_at", article.updatedAt);
        values.put("is_read", article.read ? 1 : 0);
        values.put("is_favorite", article.favorite ? 1 : 0);
        values.put("read_at", article.readAt);
        db.insertWithOnConflict("articles", null, values, SQLiteDatabase.CONFLICT_REPLACE);
    }

    private void applyArticleState(SQLiteDatabase db, ArticleState state) {
        ContentValues values = new ContentValues();
        values.put("is_read", state.read ? 1 : 0);
        values.put("is_favorite", state.favorite ? 1 : 0);
        values.put("read_at", state.readAt);
        db.update("articles", values, "id = ?", new String[]{String.valueOf(state.articleId)});
    }

    private Category readCategory(Cursor cursor) {
        Category category = new Category();
        category.id = cursor.getLong(0);
        category.name = cursor.getString(1);
        category.description = cursor.getString(2);
        category.position = cursor.getInt(3);
        category.feedCount = cursor.getInt(4);
        category.unreadCount = cursor.getInt(5);
        return category;
    }

    private Feed readFeed(Cursor cursor) {
        Feed feed = new Feed();
        feed.id = cursor.getLong(0);
        feed.url = cursor.getString(1);
        feed.title = cursor.getString(2);
        feed.description = cursor.getString(3);
        feed.siteUrl = cursor.getString(4);
        feed.iconUrl = cursor.getString(5);
        feed.categoryId = cursor.isNull(6) ? null : cursor.getLong(6);
        feed.fetchInterval = cursor.getInt(7);
        feed.lastFetchedAt = cursor.getString(8);
        feed.autoTranslate = cursor.getInt(9) == 1;
        feed.autoSummarize = cursor.getInt(10) == 1;
        feed.targetLanguage = cursor.getString(11);
        feed.translateMethod = cursor.getString(12);
        feed.active = cursor.getInt(13) == 1;
        feed.usePlaywright = cursor.getInt(14) == 1;
        feed.position = cursor.getInt(15);
        feed.unreadCount = cursor.getInt(16);
        feed.articleCount = cursor.getInt(17);
        return feed;
    }

    private Article readArticle(Cursor cursor) {
        Article article = new Article();
        article.id = cursor.getLong(0);
        article.feedId = cursor.getLong(1);
        article.feedTitle = cursor.getString(2);
        article.title = cursor.getString(3);
        article.link = cursor.getString(4);
        article.content = cursor.getString(5);
        article.fullContent = cursor.getString(6);
        article.summary = cursor.getString(7);
        article.translation = cursor.getString(8);
        article.author = cursor.getString(9);
        article.publishedAt = cursor.getString(10);
        article.createdAt = cursor.getString(11);
        article.updatedAt = cursor.getString(12);
        article.read = cursor.getInt(13) == 1;
        article.favorite = cursor.getInt(14) == 1;
        article.readAt = cursor.getString(15);
        return article;
    }
}
