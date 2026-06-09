package com.mrss.mobile.data;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

public class MobileDatabase extends SQLiteOpenHelper {
    private static final String DATABASE_NAME = "mrss_mobile.db";
    private static final int DATABASE_VERSION = 1;

    public MobileDatabase(Context context) {
        super(context, DATABASE_NAME, null, DATABASE_VERSION);
    }

    @Override
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE categories (" +
                "id INTEGER PRIMARY KEY, " +
                "name TEXT NOT NULL, " +
                "description TEXT, " +
                "position INTEGER NOT NULL DEFAULT 0, " +
                "feed_count INTEGER NOT NULL DEFAULT 0, " +
                "unread_count INTEGER NOT NULL DEFAULT 0)");

        db.execSQL("CREATE TABLE feeds (" +
                "id INTEGER PRIMARY KEY, " +
                "url TEXT NOT NULL, " +
                "title TEXT NOT NULL, " +
                "description TEXT, " +
                "site_url TEXT, " +
                "icon_url TEXT, " +
                "category_id INTEGER, " +
                "fetch_interval INTEGER NOT NULL DEFAULT 3600, " +
                "last_fetched_at TEXT, " +
                "auto_translate INTEGER NOT NULL DEFAULT 0, " +
                "auto_summarize INTEGER NOT NULL DEFAULT 0, " +
                "target_language TEXT, " +
                "translate_method TEXT NOT NULL DEFAULT 'none', " +
                "is_active INTEGER NOT NULL DEFAULT 1, " +
                "use_playwright INTEGER NOT NULL DEFAULT 0, " +
                "position INTEGER NOT NULL DEFAULT 0, " +
                "unread_count INTEGER NOT NULL DEFAULT 0, " +
                "article_count INTEGER NOT NULL DEFAULT 0)");

        db.execSQL("CREATE TABLE articles (" +
                "id INTEGER PRIMARY KEY, " +
                "feed_id INTEGER NOT NULL, " +
                "feed_title TEXT, " +
                "title TEXT NOT NULL, " +
                "link TEXT, " +
                "content TEXT, " +
                "full_content TEXT, " +
                "summary TEXT, " +
                "translation TEXT, " +
                "author TEXT, " +
                "published_at TEXT, " +
                "created_at TEXT, " +
                "updated_at TEXT, " +
                "is_read INTEGER NOT NULL DEFAULT 0, " +
                "is_favorite INTEGER NOT NULL DEFAULT 0, " +
                "read_at TEXT)");

        db.execSQL("CREATE TABLE pending_actions (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "client_action_id TEXT NOT NULL, " +
                "type TEXT NOT NULL, " +
                "article_id INTEGER NOT NULL, " +
                "value INTEGER, " +
                "created_at INTEGER NOT NULL)");

        db.execSQL("CREATE INDEX idx_feeds_category ON feeds(category_id)");
        db.execSQL("CREATE INDEX idx_articles_feed ON articles(feed_id)");
        db.execSQL("CREATE INDEX idx_articles_published ON articles(published_at)");
        db.execSQL("CREATE INDEX idx_articles_read ON articles(is_read)");
        db.execSQL("CREATE INDEX idx_articles_favorite ON articles(is_favorite)");
        db.execSQL("CREATE INDEX idx_pending_actions_created ON pending_actions(created_at)");
    }

    @Override
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        db.execSQL("DROP TABLE IF EXISTS pending_actions");
        db.execSQL("DROP TABLE IF EXISTS articles");
        db.execSQL("DROP TABLE IF EXISTS feeds");
        db.execSQL("DROP TABLE IF EXISTS categories");
        onCreate(db);
    }
}
