package com.mrss.app.data;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

public class MrssDatabase extends SQLiteOpenHelper {
    private static final String DATABASE_NAME = "mrss.db";
    private static final int DATABASE_VERSION = 6;

    public MrssDatabase(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE categories (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "name TEXT NOT NULL UNIQUE, " +
                "description TEXT, " +
                "position INTEGER NOT NULL DEFAULT 0, " +
                "created_at INTEGER NOT NULL, " +
                "updated_at INTEGER)");

        db.execSQL("CREATE TABLE feeds (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL, " +
                "url TEXT NOT NULL UNIQUE, " +
                "title TEXT NOT NULL, " +
                "description TEXT, " +
                "site_url TEXT, " +
                "icon_url TEXT, " +
                "fetch_interval INTEGER NOT NULL DEFAULT 3600, " +
                "last_fetched_at INTEGER NOT NULL DEFAULT 0, " +
                "last_error TEXT, " +
                "error_count INTEGER NOT NULL DEFAULT 0, " +
                "is_active INTEGER NOT NULL DEFAULT 1, " +
                "translate_enabled INTEGER NOT NULL DEFAULT 0, " +
                "translation_mode TEXT NOT NULL DEFAULT 'off', " +
                "translation_language TEXT NOT NULL DEFAULT '中文', " +
                "position INTEGER NOT NULL DEFAULT 0, " +
                "created_at INTEGER NOT NULL, " +
                "updated_at INTEGER)");

        db.execSQL("CREATE TABLE articles (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE, " +
                "guid TEXT NOT NULL, " +
                "link TEXT, " +
                "title TEXT NOT NULL, " +
                "content TEXT, " +
                "original_title TEXT, " +
                "original_content TEXT, " +
                "translation_language TEXT, " +
                "translation_status TEXT, " +
                "translation_error TEXT, " +
                "author TEXT, " +
                "published_at INTEGER NOT NULL DEFAULT 0, " +
                "created_at INTEGER NOT NULL, " +
                "is_read INTEGER NOT NULL DEFAULT 0, " +
                "is_favorite INTEGER NOT NULL DEFAULT 0, " +
                "read_at INTEGER NOT NULL DEFAULT 0, " +
                "favorited_at INTEGER NOT NULL DEFAULT 0, " +
                "UNIQUE(feed_id, guid))");

        db.execSQL("CREATE INDEX idx_feeds_category ON feeds(category_id)");
        db.execSQL("CREATE INDEX idx_articles_feed ON articles(feed_id)");
        db.execSQL("CREATE INDEX idx_articles_published ON articles(published_at)");
        db.execSQL("CREATE INDEX idx_articles_read ON articles(is_read)");
        db.execSQL("CREATE INDEX idx_articles_favorite ON articles(is_favorite)");
        createKeywordSubscriptions(db);
        createWebScrapingRules(db);
        createAiChannels(db);
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if (oldVersion < 2) {
            createKeywordSubscriptions(db);
        }
        if (oldVersion < 3) {
            addColumn(db, "feeds", "translate_enabled", "INTEGER NOT NULL DEFAULT 0");
            addColumn(db, "feeds", "translation_language", "TEXT NOT NULL DEFAULT '中文'");
            addColumn(db, "articles", "original_title", "TEXT");
            addColumn(db, "articles", "original_content", "TEXT");
            addColumn(db, "articles", "translation_language", "TEXT");
            addColumn(db, "articles", "translation_status", "TEXT");
            addColumn(db, "articles", "translation_error", "TEXT");
            createAiChannels(db);
        }
        if (oldVersion < 4) {
            addColumn(db, "ai_channels", "models_json", "TEXT");
        }
        if (oldVersion < 5) {
            addColumn(db, "feeds", "translation_mode", "TEXT NOT NULL DEFAULT 'off'");
            db.execSQL("UPDATE feeds SET translation_mode = 'ai' WHERE translate_enabled = 1 AND (translation_mode IS NULL OR translation_mode = '' OR translation_mode = 'off')");
        }
        if (oldVersion < 6) {
            createWebScrapingRules(db);
        }
    }

    @Override
    public void onConfigure(SQLiteDatabase db) {
        super.onConfigure(db);
        db.setForeignKeyConstraintsEnabled(true);
    }

    private void createKeywordSubscriptions(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS keyword_subscriptions (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "name TEXT NOT NULL, " +
                "keyword TEXT NOT NULL UNIQUE, " +
                "is_active INTEGER NOT NULL DEFAULT 1, " +
                "match_title INTEGER NOT NULL DEFAULT 1, " +
                "match_content INTEGER NOT NULL DEFAULT 1, " +
                "match_author INTEGER NOT NULL DEFAULT 0, " +
                "match_feed_title INTEGER NOT NULL DEFAULT 1, " +
                "created_at INTEGER NOT NULL, " +
                "updated_at INTEGER)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_keyword_subscriptions_active ON keyword_subscriptions(is_active)");
    }

    private void createAiChannels(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS ai_channels (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "name TEXT NOT NULL, " +
                "provider TEXT NOT NULL DEFAULT 'openai', " +
                "base_url TEXT, " +
                "api_key TEXT, " +
                "model TEXT, " +
                "models_json TEXT, " +
                "is_default INTEGER NOT NULL DEFAULT 0, " +
                "created_at INTEGER NOT NULL, " +
                "updated_at INTEGER)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_ai_channels_default ON ai_channels(is_default)");
    }

    private void createWebScrapingRules(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE IF NOT EXISTS web_scraping_rules (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "feed_id INTEGER REFERENCES feeds(id) ON DELETE CASCADE, " +
                "name TEXT NOT NULL, " +
                "type TEXT NOT NULL DEFAULT 'html', " +
                "list_url TEXT NOT NULL UNIQUE, " +
                "base_url TEXT, " +
                "item_selector TEXT NOT NULL, " +
                "title_selector TEXT, " +
                "link_selector TEXT, " +
                "summary_selector TEXT, " +
                "content_selector TEXT, " +
                "author_selector TEXT, " +
                "date_selector TEXT, " +
                "cover_selector TEXT, " +
                "next_page_selector TEXT, " +
                "page_url_template TEXT, " +
                "max_pages INTEGER NOT NULL DEFAULT 1, " +
                "request_headers TEXT, " +
                "date_format TEXT, " +
                "encoding TEXT, " +
                "enabled INTEGER NOT NULL DEFAULT 1, " +
                "created_at INTEGER NOT NULL, " +
                "updated_at INTEGER)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_web_scraping_rules_feed ON web_scraping_rules(feed_id)");
        db.execSQL("CREATE INDEX IF NOT EXISTS idx_web_scraping_rules_enabled ON web_scraping_rules(enabled)");
    }

    private void addColumn(SQLiteDatabase db, String table, String column, String definition) {
        try {
            db.execSQL("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition);
        } catch (Exception ignored) {
        }
    }
}
