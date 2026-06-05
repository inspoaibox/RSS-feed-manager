using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using System.Net.Http;
using Microsoft.Data.Sqlite;
using MRSS.Native.Models;
using MRSS.Native.Services;

namespace MRSS.Native.Data;

public sealed class Repository
{
    private readonly string _dbPath;
    private readonly SemaphoreSlim _writeLock = new(1, 1);

    public Repository(string dbPath)
    {
        _dbPath = dbPath;
        Initialize();
    }

    private SqliteConnection Connect()
    {
        var builder = new SqliteConnectionStringBuilder
        {
            DataSource = _dbPath,
            Mode = SqliteOpenMode.ReadWriteCreate,
            Cache = SqliteCacheMode.Shared
        };
        var connection = new SqliteConnection(builder.ToString());
        connection.Open();
        ExecuteNonQuery(connection, "PRAGMA foreign_keys = ON");
        ExecuteNonQuery(connection, "PRAGMA journal_mode = WAL");
        ExecuteNonQuery(connection, "PRAGMA synchronous = NORMAL");
        return connection;
    }

    private void Initialize()
    {
        using var connection = Connect();
        ExecuteNonQuery(
            connection,
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                position INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                site_url TEXT,
                icon_url TEXT,
                fetch_interval INTEGER NOT NULL DEFAULT 3600,
                last_fetched_at INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                error_count INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                translate_enabled INTEGER NOT NULL DEFAULT 0,
                translation_mode TEXT NOT NULL DEFAULT 'off',
                translation_language TEXT NOT NULL DEFAULT '中文',
                position INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                guid TEXT NOT NULL,
                link TEXT,
                title TEXT NOT NULL,
                content TEXT,
                original_title TEXT,
                original_content TEXT,
                translation_language TEXT,
                translation_status TEXT,
                translation_error TEXT,
                author TEXT,
                published_at INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                is_favorite INTEGER NOT NULL DEFAULT 0,
                read_at INTEGER NOT NULL DEFAULT 0,
                favorited_at INTEGER NOT NULL DEFAULT 0,
                UNIQUE(feed_id, guid)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS keyword_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                keyword TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                match_title INTEGER NOT NULL DEFAULT 1,
                match_content INTEGER NOT NULL DEFAULT 1,
                match_author INTEGER NOT NULL DEFAULT 0,
                match_feed_title INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS web_scraping_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER REFERENCES feeds(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'html',
                list_url TEXT NOT NULL UNIQUE,
                base_url TEXT,
                item_selector TEXT NOT NULL,
                title_selector TEXT,
                link_selector TEXT,
                summary_selector TEXT,
                content_selector TEXT,
                author_selector TEXT,
                date_selector TEXT,
                cover_selector TEXT,
                next_page_selector TEXT,
                page_url_template TEXT,
                max_pages INTEGER NOT NULL DEFAULT 1,
                request_headers TEXT,
                date_format TEXT,
                encoding TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_feeds_category ON feeds(category_id);
            CREATE INDEX IF NOT EXISTS idx_articles_feed ON articles(feed_id);
            CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
            CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(is_read);
            CREATE INDEX IF NOT EXISTS idx_articles_favorite ON articles(is_favorite);
            CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at);
            CREATE INDEX IF NOT EXISTS idx_keyword_subscriptions_active ON keyword_subscriptions(is_active);
            CREATE INDEX IF NOT EXISTS idx_web_scraping_rules_feed ON web_scraping_rules(feed_id);
            CREATE INDEX IF NOT EXISTS idx_web_scraping_rules_enabled ON web_scraping_rules(enabled);
            """);
        EnsureColumn(connection, "feeds", "translate_enabled", "INTEGER NOT NULL DEFAULT 0");
        EnsureColumn(connection, "feeds", "translation_mode", "TEXT NOT NULL DEFAULT 'off'");
        ExecuteNonQuery(connection, "UPDATE feeds SET translation_mode = 'ai' WHERE translate_enabled = 1 AND (translation_mode IS NULL OR translation_mode = '' OR translation_mode = 'off')");
        EnsureColumn(connection, "feeds", "translation_language", "TEXT NOT NULL DEFAULT '中文'");
        EnsureColumn(connection, "articles", "original_title", "TEXT");
        EnsureColumn(connection, "articles", "original_content", "TEXT");
        EnsureColumn(connection, "articles", "translation_language", "TEXT");
        EnsureColumn(connection, "articles", "translation_status", "TEXT");
        EnsureColumn(connection, "articles", "translation_error", "TEXT");
        ExecuteNonQuery(
            connection,
            """
            CREATE TABLE IF NOT EXISTS ai_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'openai',
                base_url TEXT,
                api_key TEXT,
                model TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_ai_channels_default ON ai_channels(is_default);
            """);
    }

    public string GetSetting(string key, string defaultValue = "")
    {
        using var connection = Connect();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT value FROM settings WHERE key = $key";
        command.Parameters.AddWithValue("$key", key);
        return command.ExecuteScalar()?.ToString() ?? defaultValue;
    }

    public async Task SetSettingAsync(string key, string value)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO settings(key, value) VALUES($key, $value) ON CONFLICT(key) DO UPDATE SET value = excluded.value";
            command.Parameters.AddWithValue("$key", key);
            command.Parameters.AddWithValue("$value", value);
            command.ExecuteNonQuery();
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public List<AiChannel> AiChannels()
    {
        using var connection = Connect();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT * FROM ai_channels ORDER BY is_default DESC, name COLLATE NOCASE ASC";
        using var reader = command.ExecuteReader();
        var list = new List<AiChannel>();
        while (reader.Read())
        {
            list.Add(ReadAiChannel(reader));
        }

        return list;
    }

    public AiChannel? DefaultAiChannel()
    {
        using var connection = Connect();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT * FROM ai_channels ORDER BY is_default DESC, id ASC LIMIT 1";
        using var reader = command.ExecuteReader();
        return reader.Read() ? ReadAiChannel(reader) : null;
    }

    public async Task SaveAiChannelsAsync(IEnumerable<AiChannel> channels)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            using var transaction = connection.BeginTransaction();
            ExecuteNonQuery(connection, "DELETE FROM ai_channels");
            var now = Clock.NowMs();
            var defaultWritten = false;
            foreach (var channel in channels)
            {
                if (string.IsNullOrWhiteSpace(channel.Name))
                {
                    continue;
                }

                var provider = NormalizeAiProvider(channel.Provider, channel.BaseUrl);
                var isDefault = channel.IsDefault && !defaultWritten;
                defaultWritten |= isDefault;
                ExecuteNonQuery(
                    connection,
                    """
                    INSERT INTO ai_channels(name, provider, base_url, api_key, model, is_default, created_at, updated_at)
                    VALUES($name, $provider, $base_url, $api_key, $model, $is_default, $created_at, $updated_at)
                    """,
                    ("$name", Truncate(channel.Name.Trim(), 100)),
                    ("$provider", provider),
                    ("$base_url", BlankToNull(channel.BaseUrl)),
                    ("$api_key", BlankToNull(channel.ApiKey)),
                    ("$model", BlankToNull(channel.Model)),
                    ("$is_default", isDefault ? 1 : 0),
                    ("$created_at", channel.CreatedAt <= 0 ? now : channel.CreatedAt),
                    ("$updated_at", now));
            }

            if (!defaultWritten)
            {
                ExecuteNonQuery(connection, "UPDATE ai_channels SET is_default = 1 WHERE id = (SELECT id FROM ai_channels ORDER BY id ASC LIMIT 1)");
            }

            transaction.Commit();
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public List<Category> Categories()
    {
        using var connection = Connect();
        using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT c.*,
                (SELECT COUNT(*) FROM feeds f WHERE f.category_id = c.id) AS feed_count,
                (SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id = a.feed_id WHERE f.category_id = c.id AND a.is_read = 0) AS unread_count
            FROM categories c
            ORDER BY c.position ASC, c.name COLLATE NOCASE ASC
            """;
        using var reader = command.ExecuteReader();
        var list = new List<Category>();
        while (reader.Read())
        {
            list.Add(new Category
            {
                Id = reader.GetInt32(reader.GetOrdinal("id")),
                Name = reader.GetString(reader.GetOrdinal("name")),
                FeedCount = reader.GetInt32(reader.GetOrdinal("feed_count")),
                UnreadCount = reader.GetInt32(reader.GetOrdinal("unread_count"))
            });
        }

        return list;
    }

    public List<Feed> Feeds()
    {
        using var connection = Connect();
        using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT f.*, c.name AS category_name,
                (SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id) AS article_count,
                (SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id AND a.is_read = 0) AS unread_count
            FROM feeds f
            LEFT JOIN categories c ON c.id = f.category_id
            ORDER BY c.position ASC, c.name COLLATE NOCASE ASC, f.position ASC, f.title COLLATE NOCASE ASC
            """;
        using var reader = command.ExecuteReader();
        var list = new List<Feed>();
        while (reader.Read())
        {
            list.Add(ReadFeed(reader));
        }

        return list;
    }

    public AppStats Stats()
    {
        using var connection = Connect();
        var today = DateTime.Today;
        var todayMs = new DateTimeOffset(today).ToUnixTimeMilliseconds();
        var sevenMs = new DateTimeOffset(today.AddDays(-6)).ToUnixTimeMilliseconds();
        return new AppStats
        {
            CategoryCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM categories") ?? 0),
            FeedCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM feeds") ?? 0),
            ActiveFeedCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM feeds WHERE is_active = 1") ?? 0),
            ArticleCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM articles") ?? 0),
            UnreadCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM articles WHERE is_read = 0") ?? 0),
            FavoriteCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM articles WHERE is_favorite = 1") ?? 0),
            TodayCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM articles WHERE CASE WHEN published_at = 0 THEN created_at ELSE published_at END >= $value", ("$value", todayMs)) ?? 0),
            LastSevenDaysCount = Convert.ToInt32(Scalar(connection, "SELECT COUNT(*) FROM articles WHERE CASE WHEN published_at = 0 THEN created_at ELSE published_at END >= $value", ("$value", sevenMs)) ?? 0),
            LatestArticleAt = Convert.ToInt64(Scalar(connection, "SELECT MAX(CASE WHEN published_at = 0 THEN created_at ELSE published_at END) FROM articles") ?? 0)
        };
    }

    public ArticlePage Articles(ArticleQuery query)
    {
        var where = new List<string>();
        var parameters = new List<(string Name, object? Value)>();

        if (query.FeedId is not null)
        {
            where.Add("a.feed_id = $feed_id");
            parameters.Add(("$feed_id", query.FeedId.Value));
        }
        else if (query.UncategorizedOnly)
        {
            where.Add("f.category_id IS NULL");
        }
        else if (query.CategoryId is not null)
        {
            where.Add("f.category_id = $category_id");
            parameters.Add(("$category_id", query.CategoryId.Value));
        }

        if (query.UnreadOnly)
        {
            where.Add("a.is_read = 0");
        }

        if (query.FavoriteOnly)
        {
            where.Add("a.is_favorite = 1");
        }

        if (!string.IsNullOrWhiteSpace(query.Search))
        {
            where.Add("(a.title LIKE $search OR a.content LIKE $search OR f.title LIKE $search)");
            parameters.Add(("$search", $"%{query.Search.Trim()}%"));
        }

        AddDateFilter(query, where, parameters);

        var whereSql = where.Count == 0 ? "" : " WHERE " + string.Join(" AND ", where);
        var sort = query.Sort switch
        {
            "created" => "a.created_at",
            "title" => "a.title COLLATE NOCASE",
            _ => "a.published_at"
        };
        var direction = query.Descending ? "DESC" : "ASC";
        var limit = Math.Clamp(query.Limit, 1, 300);
        var offset = Math.Max(0, query.Offset);

        using var connection = Connect();
        var total = Convert.ToInt32(Scalar(connection, $"SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id = a.feed_id{whereSql}", parameters.ToArray()) ?? 0);
        using var command = connection.CreateCommand();
        command.CommandText =
            $"""
            SELECT a.*, f.title AS feed_title, f.icon_url AS feed_icon_url
            FROM articles a JOIN feeds f ON f.id = a.feed_id
            {whereSql}
            ORDER BY {sort} {direction}, a.id DESC
            LIMIT $limit OFFSET $offset
            """;
        AddParameters(command, parameters);
        command.Parameters.AddWithValue("$limit", limit);
        command.Parameters.AddWithValue("$offset", offset);
        using var reader = command.ExecuteReader();
        var items = new List<Article>();
        while (reader.Read())
        {
            items.Add(ReadArticle(reader));
        }

        return new ArticlePage { Total = total, Items = items };
    }

    public async Task<int> AddCategoryAsync(string name)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            using var command = connection.CreateCommand();
            command.CommandText = "INSERT INTO categories(name, created_at) VALUES($name, $created_at); SELECT last_insert_rowid();";
            command.Parameters.AddWithValue("$name", name.Trim());
            command.Parameters.AddWithValue("$created_at", Clock.NowMs());
            return Convert.ToInt32(command.ExecuteScalar());
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task UpdateCategoryAsync(int categoryId, string name)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(connection, "UPDATE categories SET name = $name, updated_at = $updated_at WHERE id = $id", ("$name", name.Trim()), ("$updated_at", Clock.NowMs()), ("$id", categoryId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task DeleteCategoryAsync(int categoryId)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(connection, "DELETE FROM categories WHERE id = $id", ("$id", categoryId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task<int> AddFeedAsync(ParsedFeed parsed, int? categoryId, int intervalSeconds, bool translateEnabled = false, string translationLanguage = "中文")
    {
        return await AddFeedAsync(parsed, categoryId, intervalSeconds, translateEnabled ? "ai" : "off", translationLanguage);
    }

    public async Task<int> AddFeedAsync(ParsedFeed parsed, int? categoryId, int intervalSeconds, string translationMode, string translationLanguage = "中文")
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            using var transaction = connection.BeginTransaction();
            var existing = Scalar(connection, "SELECT id FROM feeds WHERE url = $url", ("$url", parsed.Url));
            var ts = Clock.NowMs();
            var normalizedMode = NormalizeTranslationMode(translationMode);
            int feedId;
            if (existing is not null)
            {
                feedId = Convert.ToInt32(existing);
                ExecuteNonQuery(
                    connection,
                    """
                    UPDATE feeds SET title = $title, description = $description, site_url = $site_url, icon_url = $icon_url,
                    category_id = $category_id, fetch_interval = $interval, last_fetched_at = $fetched_at,
                    translate_enabled = $translate_enabled, translation_mode = $translation_mode, translation_language = $translation_language,
                    last_error = NULL, error_count = 0, updated_at = $updated_at WHERE id = $id
                    """,
                    ("$title", parsed.Title),
                    ("$description", parsed.Description),
                    ("$site_url", parsed.SiteUrl),
                    ("$icon_url", parsed.IconUrl),
                    ("$category_id", categoryId),
                    ("$interval", intervalSeconds),
                    ("$translate_enabled", TranslationEnabled(normalizedMode) ? 1 : 0),
                    ("$translation_mode", normalizedMode),
                    ("$translation_language", NormalizeLanguage(translationLanguage)),
                    ("$fetched_at", ts),
                    ("$updated_at", ts),
                    ("$id", feedId));
            }
            else
            {
                using var command = connection.CreateCommand();
                command.Transaction = transaction;
                command.CommandText =
                    """
                    INSERT INTO feeds(category_id, url, title, description, site_url, icon_url, fetch_interval, last_fetched_at,
                    is_active, translate_enabled, translation_mode, translation_language, created_at)
                    VALUES($category_id, $url, $title, $description, $site_url, $icon_url, $interval, $fetched_at,
                    1, $translate_enabled, $translation_mode, $translation_language, $created_at);
                    SELECT last_insert_rowid();
                    """;
                command.Parameters.AddWithValue("$category_id", DbValue(categoryId));
                command.Parameters.AddWithValue("$url", parsed.Url);
                command.Parameters.AddWithValue("$title", parsed.Title);
                command.Parameters.AddWithValue("$description", DbValue(parsed.Description));
                command.Parameters.AddWithValue("$site_url", DbValue(parsed.SiteUrl));
                command.Parameters.AddWithValue("$icon_url", DbValue(parsed.IconUrl));
                command.Parameters.AddWithValue("$interval", intervalSeconds);
                command.Parameters.AddWithValue("$translate_enabled", TranslationEnabled(normalizedMode) ? 1 : 0);
                command.Parameters.AddWithValue("$translation_mode", normalizedMode);
                command.Parameters.AddWithValue("$translation_language", NormalizeLanguage(translationLanguage));
                command.Parameters.AddWithValue("$fetched_at", ts);
                command.Parameters.AddWithValue("$created_at", ts);
                feedId = Convert.ToInt32(command.ExecuteScalar());
            }

            SaveArticles(connection, feedId, parsed);
            transaction.Commit();
            return feedId;
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task UpdateFeedAsync(Feed feed)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            var normalizedMode = NormalizeTranslationMode(feed.TranslateEnabled ? feed.TranslationMode : "off");
            ExecuteNonQuery(
                connection,
                """
                UPDATE feeds SET title = $title, category_id = $category_id, fetch_interval = $interval,
                is_active = $active, translate_enabled = $translate_enabled, translation_mode = $translation_mode, translation_language = $translation_language,
                updated_at = $updated_at WHERE id = $id
                """,
                ("$title", string.IsNullOrWhiteSpace(feed.Title) ? "Untitled Feed" : feed.Title.Trim()),
                ("$category_id", feed.CategoryId),
                ("$interval", feed.FetchInterval),
                ("$active", feed.IsActive ? 1 : 0),
                ("$translate_enabled", TranslationEnabled(normalizedMode) ? 1 : 0),
                ("$translation_mode", normalizedMode),
                ("$translation_language", NormalizeLanguage(feed.TranslationLanguage)),
                ("$updated_at", Clock.NowMs()),
                ("$id", feed.Id));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task DeleteFeedAsync(int feedId)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(connection, "DELETE FROM feeds WHERE id = $id", ("$id", feedId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public List<WebScrapingRule> WebScrapingRules()
    {
        using var connection = Connect();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT * FROM web_scraping_rules ORDER BY created_at ASC, name COLLATE NOCASE ASC";
        using var reader = command.ExecuteReader();
        var rules = new List<WebScrapingRule>();
        while (reader.Read())
        {
            rules.Add(ReadWebScrapingRule(reader));
        }

        return rules;
    }

    public async Task<int> SaveWebScrapingRuleAsync(WebScrapingRule rule)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            var now = Clock.NowMs();
            if (rule.Id <= 0)
            {
                using var command = connection.CreateCommand();
                command.CommandText =
                    """
                    INSERT INTO web_scraping_rules(feed_id, name, type, list_url, base_url, item_selector, title_selector,
                    link_selector, summary_selector, content_selector, author_selector, date_selector, cover_selector,
                    next_page_selector, page_url_template, max_pages, request_headers, date_format, encoding, enabled,
                    created_at, updated_at)
                    VALUES($feed_id, $name, $type, $list_url, $base_url, $item_selector, $title_selector,
                    $link_selector, $summary_selector, $content_selector, $author_selector, $date_selector, $cover_selector,
                    $next_page_selector, $page_url_template, $max_pages, $request_headers, $date_format, $encoding, $enabled,
                    $created_at, $updated_at);
                    SELECT last_insert_rowid();
                    """;
                AddWebScrapingRuleParameters(command, rule, now, now);
                return Convert.ToInt32(command.ExecuteScalar());
            }

            using (var command = connection.CreateCommand())
            {
                command.CommandText =
                    """
                    UPDATE web_scraping_rules SET feed_id = $feed_id, name = $name, type = $type, list_url = $list_url,
                    base_url = $base_url, item_selector = $item_selector, title_selector = $title_selector,
                    link_selector = $link_selector, summary_selector = $summary_selector, content_selector = $content_selector,
                    author_selector = $author_selector, date_selector = $date_selector, cover_selector = $cover_selector,
                    next_page_selector = $next_page_selector, page_url_template = $page_url_template, max_pages = $max_pages,
                    request_headers = $request_headers, date_format = $date_format, encoding = $encoding, enabled = $enabled,
                    updated_at = $updated_at WHERE id = $id
                    """;
                command.Parameters.AddWithValue("$id", rule.Id);
                AddWebScrapingRuleParameters(command, rule, null, now);
                command.ExecuteNonQuery();
            }

            return rule.Id;
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task DeleteWebScrapingRuleAsync(int ruleId)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(connection, "DELETE FROM web_scraping_rules WHERE id = $id", ("$id", ruleId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task<RefreshResult> RefreshFeedsAsync(Func<string, CancellationToken, Task<ParsedFeed>> parser, int? feedId = null, int? categoryId = null, bool uncategorized = false, bool dueOnly = false, CancellationToken cancellationToken = default)
    {
        var feeds = Feeds();
        var ts = Clock.NowMs();
        var result = new RefreshResult();

        foreach (var feed in feeds)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!feed.IsActive)
            {
                continue;
            }

            if (feedId is not null && feed.Id != feedId.Value)
            {
                continue;
            }

            if (feedId is null && uncategorized && feed.CategoryId is not null)
            {
                continue;
            }

            if (feedId is null && categoryId is not null && feed.CategoryId != categoryId.Value)
            {
                continue;
            }

            if (dueOnly && feed.LastFetchedAt > 0 && feed.LastFetchedAt + feed.FetchInterval * 1000L > ts)
            {
                continue;
            }

            result.Candidates++;
            try
            {
                var parsed = await parser(feed.Url, cancellationToken);
                parsed.Url = feed.Url;
                var inserted = await SaveRefreshAsync(feed.Id, parsed);
                result.Inserted += inserted;
                result.Success++;
            }
            catch (Exception ex)
            {
                var error = FriendlyRefreshError(ex);
                await SaveRefreshErrorAsync(feed.Id, error);
                result.Failures.Add(new RefreshFailure
                {
                    FeedId = feed.Id,
                    FeedTitle = feed.Title,
                    Url = feed.Url,
                    Error = error
                });
                result.Failed++;
            }
        }

        return result;
    }

    public List<TranslationJob> PendingTranslationJobs(int limit = 20)
    {
        return PendingTranslationJobs("ai", limit);
    }

    public List<TranslationJob> PendingTranslationJobs(string translationMode, int limit = 20)
    {
        using var connection = Connect();
        using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT a.id AS article_id, a.feed_id, a.title, a.content, a.link, f.translation_language, f.translation_mode
            FROM articles a
            JOIN feeds f ON f.id = a.feed_id
            WHERE f.translate_enabled = 1
              AND f.translation_mode = $translation_mode
              AND (a.translation_status IS NULL OR a.translation_status = 'pending')
              AND (a.original_content IS NULL OR a.original_content = '')
            ORDER BY a.created_at DESC
            LIMIT $limit
            """;
        command.Parameters.AddWithValue("$translation_mode", NormalizeTranslationMode(translationMode));
        command.Parameters.AddWithValue("$limit", Math.Clamp(limit, 1, 100));
        using var reader = command.ExecuteReader();
        var jobs = new List<TranslationJob>();
        while (reader.Read())
        {
            jobs.Add(new TranslationJob
            {
                ArticleId = Int(reader, "article_id"),
                FeedId = Int(reader, "feed_id"),
                TranslationMode = NormalizeTranslationMode(NullableText(reader, "translation_mode")),
                TargetLanguage = NormalizeLanguage(NullableText(reader, "translation_language")),
                Title = Text(reader, "title"),
                Content = NullableText(reader, "content") ?? "",
                Link = NullableText(reader, "link")
            });
        }

        return jobs;
    }

    public async Task SaveTranslationAsync(int articleId, string targetLanguage, ArticleTranslation translation)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(
                connection,
                """
                UPDATE articles
                SET original_title = COALESCE(NULLIF(original_title, ''), title),
                    original_content = COALESCE(NULLIF(original_content, ''), content),
                    title = $title,
                    content = $content,
                    translation_language = $language,
                    translation_status = 'done',
                    translation_error = NULL
                WHERE id = $id
                """,
                ("$title", string.IsNullOrWhiteSpace(translation.Title) ? "Untitled" : translation.Title.Trim()),
                ("$content", translation.Content),
                ("$language", NormalizeLanguage(targetLanguage)),
                ("$id", articleId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task MarkTranslationFailedAsync(int articleId, string error)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(
                connection,
                "UPDATE articles SET translation_status = 'failed', translation_error = $error WHERE id = $id",
                ("$error", Truncate(error, 1000)),
                ("$id", articleId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task MarkReadAsync(int articleId, bool read)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(connection, "UPDATE articles SET is_read = $read, read_at = $read_at WHERE id = $id", ("$read", read ? 1 : 0), ("$read_at", read ? Clock.NowMs() : 0), ("$id", articleId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task<bool> ToggleFavoriteAsync(int articleId)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            var current = Convert.ToInt32(Scalar(connection, "SELECT is_favorite FROM articles WHERE id = $id", ("$id", articleId)) ?? 0);
            var next = current == 0;
            ExecuteNonQuery(connection, "UPDATE articles SET is_favorite = $favorite, favorited_at = $favorited_at WHERE id = $id", ("$favorite", next ? 1 : 0), ("$favorited_at", next ? Clock.NowMs() : 0), ("$id", articleId));
            return next;
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task<int> MarkAllReadAsync(int? feedId = null, int? categoryId = null, bool uncategorized = false)
    {
        await _writeLock.WaitAsync();
        try
        {
            var where = "is_read = 0";
            var parameters = new List<(string Name, object? Value)> { ("$read_at", Clock.NowMs()) };
            if (feedId is not null)
            {
                where += " AND feed_id = $feed_id";
                parameters.Add(("$feed_id", feedId.Value));
            }
            else if (uncategorized)
            {
                where += " AND feed_id IN (SELECT id FROM feeds WHERE category_id IS NULL)";
            }
            else if (categoryId is not null)
            {
                where += " AND feed_id IN (SELECT id FROM feeds WHERE category_id = $category_id)";
                parameters.Add(("$category_id", categoryId.Value));
            }

            using var connection = Connect();
            using var command = connection.CreateCommand();
            command.CommandText = $"UPDATE articles SET is_read = 1, read_at = $read_at WHERE {where}";
            AddParameters(command, parameters);
            return command.ExecuteNonQuery();
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public BackupDocument ExportBackup()
    {
        using var connection = Connect();
        var document = new BackupDocument { ExportedAt = Clock.NowMs() };
        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM categories ORDER BY id ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.Categories.Add(new CategoryBackup
                {
                    Id = Int(reader, "id"),
                    Name = Text(reader, "name"),
                    Description = NullableText(reader, "description"),
                    Position = Int(reader, "position"),
                    CreatedAt = Long(reader, "created_at"),
                    UpdatedAt = NullableLong(reader, "updated_at")
                });
            }
        }

        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM feeds ORDER BY id ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.Feeds.Add(new FeedBackup
                {
                    Id = Int(reader, "id"),
                    CategoryId = NullableInt(reader, "category_id"),
                    Url = Text(reader, "url"),
                    Title = Text(reader, "title"),
                    Description = NullableText(reader, "description"),
                    SiteUrl = NullableText(reader, "site_url"),
                    IconUrl = NullableText(reader, "icon_url"),
                    FetchInterval = Int(reader, "fetch_interval"),
                    LastFetchedAt = Long(reader, "last_fetched_at"),
                    LastError = NullableText(reader, "last_error"),
                    ErrorCount = Int(reader, "error_count"),
                    IsActive = Int(reader, "is_active") == 1,
                    TranslateEnabled = Int(reader, "translate_enabled") == 1,
                    TranslationMode = NormalizeTranslationMode(NullableText(reader, "translation_mode")),
                    TranslationLanguage = NormalizeLanguage(NullableText(reader, "translation_language")),
                    Position = Int(reader, "position"),
                    CreatedAt = Long(reader, "created_at"),
                    UpdatedAt = NullableLong(reader, "updated_at")
                });
            }
        }

        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM web_scraping_rules ORDER BY id ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.WebScrapingRules.Add(ReadWebScrapingRuleBackup(reader));
            }
        }

        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM articles ORDER BY id ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.Articles.Add(new ArticleBackup
                {
                    Id = Int(reader, "id"),
                    FeedId = Int(reader, "feed_id"),
                    Guid = Text(reader, "guid"),
                    Link = NullableText(reader, "link"),
                    Title = Text(reader, "title"),
                    Content = NullableText(reader, "content"),
                    OriginalTitle = NullableText(reader, "original_title"),
                    OriginalContent = NullableText(reader, "original_content"),
                    TranslationLanguage = NullableText(reader, "translation_language"),
                    TranslationStatus = NullableText(reader, "translation_status"),
                    TranslationError = NullableText(reader, "translation_error"),
                    Author = NullableText(reader, "author"),
                    PublishedAt = Long(reader, "published_at"),
                    CreatedAt = Long(reader, "created_at"),
                    IsRead = Int(reader, "is_read") == 1,
                    IsFavorite = Int(reader, "is_favorite") == 1,
                    ReadAt = Long(reader, "read_at"),
                    FavoritedAt = Long(reader, "favorited_at")
                });
            }
        }

        return document;
    }

    public SubscriptionSyncDocument ExportSubscriptionSync()
    {
        using var connection = Connect();
        var document = new SubscriptionSyncDocument { ExportedAt = Clock.NowMs() };
        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM categories ORDER BY position ASC, name COLLATE NOCASE ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.Categories.Add(new SubscriptionCategorySync
                {
                    Id = Int(reader, "id"),
                    Name = Text(reader, "name"),
                    Description = NullableText(reader, "description"),
                    Position = Int(reader, "position"),
                    CreatedAt = Long(reader, "created_at"),
                    UpdatedAt = NullableLong(reader, "updated_at")
                });
            }
        }

        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM feeds ORDER BY position ASC, title COLLATE NOCASE ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.Feeds.Add(new SubscriptionFeedSync
                {
                    Id = Int(reader, "id"),
                    CategoryId = NullableInt(reader, "category_id"),
                    Url = Text(reader, "url"),
                    Title = Text(reader, "title"),
                    Description = NullableText(reader, "description"),
                    SiteUrl = NullableText(reader, "site_url"),
                    IconUrl = NullableText(reader, "icon_url"),
                    FetchInterval = Int(reader, "fetch_interval"),
                    IsActive = Int(reader, "is_active"),
                    TranslateEnabled = Int(reader, "translate_enabled"),
                    TranslationMode = NormalizeTranslationMode(NullableText(reader, "translation_mode")),
                    TranslationLanguage = NullableText(reader, "translation_language"),
                    Position = Int(reader, "position"),
                    CreatedAt = Long(reader, "created_at"),
                    UpdatedAt = NullableLong(reader, "updated_at")
                });
            }
        }

        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM keyword_subscriptions ORDER BY created_at ASC, name COLLATE NOCASE ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.KeywordSubscriptions.Add(new KeywordSubscriptionBackup
                {
                    Id = Int(reader, "id"),
                    Name = Text(reader, "name"),
                    Keyword = Text(reader, "keyword"),
                    IsActive = Int(reader, "is_active"),
                    MatchTitle = Int(reader, "match_title"),
                    MatchContent = Int(reader, "match_content"),
                    MatchAuthor = Int(reader, "match_author"),
                    MatchFeedTitle = Int(reader, "match_feed_title"),
                    CreatedAt = Long(reader, "created_at"),
                    UpdatedAt = NullableLong(reader, "updated_at")
                });
            }
        }

        using (var command = connection.CreateCommand())
        {
            command.CommandText = "SELECT * FROM web_scraping_rules ORDER BY created_at ASC, name COLLATE NOCASE ASC";
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                document.WebScrapingRules.Add(ReadWebScrapingRuleBackup(reader));
            }
        }

        return document;
    }

    public async Task<int> ImportSubscriptionSyncAsync(SubscriptionSyncDocument document)
    {
        if (document.Categories is null || document.Feeds is null)
        {
            throw new InvalidOperationException("同步数据缺少 categories / feeds。");
        }

        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            using var transaction = connection.BeginTransaction();
            var now = Clock.NowMs();
            var changed = 0;
            foreach (var category in document.Categories)
            {
                var name = Truncate(category.Name?.Trim() ?? "", 100);
                if (string.IsNullOrWhiteSpace(name))
                {
                    continue;
                }

                var categoryId = FindCategoryIdByName(connection, name);
                if (categoryId is null)
                {
                    ExecuteNonQuery(
                        connection,
                        "INSERT INTO categories(name, description, position, created_at, updated_at) VALUES($name, $description, $position, $created_at, $updated_at)",
                        ("$name", name),
                        ("$description", BlankToNull(category.Description)),
                        ("$position", category.Position),
                        ("$created_at", category.CreatedAt <= 0 ? now : category.CreatedAt),
                        ("$updated_at", now));
                }
                else
                {
                    ExecuteNonQuery(
                        connection,
                        "UPDATE categories SET description = $description, position = $position, updated_at = $updated_at WHERE id = $id",
                        ("$description", BlankToNull(category.Description)),
                        ("$position", category.Position),
                        ("$updated_at", now),
                        ("$id", categoryId.Value));
                }

                changed++;
            }

            foreach (var feed in document.Feeds)
            {
                var url = feed.Url?.Trim() ?? "";
                if (string.IsNullOrWhiteSpace(url))
                {
                    continue;
                }

                int? categoryId = null;
                if (feed.CategoryId is not null)
                {
                    var categoryName = CategoryNameByExportId(document.Categories, feed.CategoryId.Value);
                    if (!string.IsNullOrWhiteSpace(categoryName))
                    {
                        categoryId = GetOrCreateCategory(connection, categoryName.Trim(), now);
                    }
                }

                var existingFeedId = FindFeedIdByUrl(connection, url);
                var title = Truncate(FirstNonEmpty(feed.Title, url, "Untitled Feed"), 255);
                var interval = feed.FetchInterval <= 0 ? 3600 : feed.FetchInterval;
                var translationMode = NormalizeTranslationMode(feed.TranslationMode ?? (feed.TranslateEnabled == 1 ? "ai" : "off"));
                if (existingFeedId is null)
                {
                    ExecuteNonQuery(
                        connection,
                        """
                        INSERT INTO feeds(category_id, url, title, description, site_url, icon_url, fetch_interval, last_fetched_at,
                        is_active, translate_enabled, translation_mode, translation_language, position, created_at, updated_at)
                        VALUES($category_id, $url, $title, $description, $site_url, $icon_url, $fetch_interval, 0,
                        $is_active, $translate_enabled, $translation_mode, $translation_language, $position, $created_at, $updated_at)
                        """,
                        ("$category_id", categoryId),
                        ("$url", url),
                        ("$title", title),
                        ("$description", BlankToNull(feed.Description)),
                        ("$site_url", BlankToNull(feed.SiteUrl)),
                        ("$icon_url", BlankToNull(feed.IconUrl)),
                        ("$fetch_interval", interval),
                        ("$is_active", feed.IsActive == 0 ? 0 : 1),
                        ("$translate_enabled", TranslationEnabled(translationMode) ? 1 : 0),
                        ("$translation_mode", translationMode),
                        ("$translation_language", NormalizeLanguage(feed.TranslationLanguage)),
                        ("$position", feed.Position),
                        ("$created_at", feed.CreatedAt <= 0 ? now : feed.CreatedAt),
                        ("$updated_at", now));
                }
                else
                {
                    ExecuteNonQuery(
                        connection,
                        """
                        UPDATE feeds SET category_id = $category_id, title = $title, description = $description,
                        site_url = $site_url, icon_url = $icon_url, fetch_interval = $fetch_interval,
                        is_active = $is_active, translate_enabled = $translate_enabled, translation_mode = $translation_mode, translation_language = $translation_language,
                        position = $position, updated_at = $updated_at WHERE id = $id
                        """,
                        ("$category_id", categoryId),
                        ("$title", title),
                        ("$description", BlankToNull(feed.Description)),
                        ("$site_url", BlankToNull(feed.SiteUrl)),
                        ("$icon_url", BlankToNull(feed.IconUrl)),
                        ("$fetch_interval", interval),
                        ("$is_active", feed.IsActive == 0 ? 0 : 1),
                        ("$translate_enabled", TranslationEnabled(translationMode) ? 1 : 0),
                        ("$translation_mode", translationMode),
                        ("$translation_language", NormalizeLanguage(feed.TranslationLanguage)),
                        ("$position", feed.Position),
                        ("$updated_at", now),
                        ("$id", existingFeedId.Value));
                }

                changed++;
            }

            foreach (var keyword in document.KeywordSubscriptions ?? [])
            {
                var keywordText = Truncate(keyword.Keyword?.Trim() ?? "", 200);
                if (string.IsNullOrWhiteSpace(keywordText))
                {
                    continue;
                }

                var existingKeywordId = FindKeywordIdByKeyword(connection, keywordText);
                var name = Truncate(FirstNonEmpty(keyword.Name, keywordText), 100);
                if (existingKeywordId is null)
                {
                    ExecuteNonQuery(
                        connection,
                        """
                        INSERT INTO keyword_subscriptions(name, keyword, is_active, match_title, match_content, match_author,
                        match_feed_title, created_at, updated_at)
                        VALUES($name, $keyword, $is_active, $match_title, $match_content, $match_author,
                        $match_feed_title, $created_at, $updated_at)
                        """,
                        ("$name", name),
                        ("$keyword", keywordText),
                        ("$is_active", keyword.IsActive),
                        ("$match_title", keyword.MatchTitle),
                        ("$match_content", keyword.MatchContent),
                        ("$match_author", keyword.MatchAuthor),
                        ("$match_feed_title", keyword.MatchFeedTitle),
                        ("$created_at", keyword.CreatedAt <= 0 ? now : keyword.CreatedAt),
                        ("$updated_at", now));
                }
                else
                {
                    ExecuteNonQuery(
                        connection,
                        """
                        UPDATE keyword_subscriptions SET name = $name, is_active = $is_active, match_title = $match_title,
                        match_content = $match_content, match_author = $match_author, match_feed_title = $match_feed_title,
                        updated_at = $updated_at WHERE id = $id
                        """,
                        ("$name", name),
                        ("$is_active", keyword.IsActive),
                        ("$match_title", keyword.MatchTitle),
                        ("$match_content", keyword.MatchContent),
                        ("$match_author", keyword.MatchAuthor),
                        ("$match_feed_title", keyword.MatchFeedTitle),
                        ("$updated_at", now),
                        ("$id", existingKeywordId.Value));
                }

                changed++;
            }

            foreach (var rule in document.WebScrapingRules ?? [])
            {
                var listUrl = rule.ListUrl?.Trim() ?? "";
                if (string.IsNullOrWhiteSpace(listUrl))
                {
                    continue;
                }

                int? feedId = null;
                if (rule.FeedId is not null)
                {
                    var feedUrl = FeedUrlByExportId(document.Feeds, rule.FeedId.Value);
                    if (!string.IsNullOrWhiteSpace(feedUrl))
                    {
                        feedId = FindFeedIdByUrl(connection, feedUrl.Trim());
                    }
                }

                var existingRuleId = FindWebScrapingRuleIdByListUrl(connection, listUrl);
                if (existingRuleId is null)
                {
                    ExecuteNonQuery(
                        connection,
                        """
                        INSERT INTO web_scraping_rules(feed_id, name, type, list_url, base_url, item_selector, title_selector,
                        link_selector, summary_selector, content_selector, author_selector, date_selector, cover_selector,
                        next_page_selector, page_url_template, max_pages, request_headers, date_format, encoding, enabled,
                        created_at, updated_at)
                        VALUES($feed_id, $name, $type, $list_url, $base_url, $item_selector, $title_selector,
                        $link_selector, $summary_selector, $content_selector, $author_selector, $date_selector, $cover_selector,
                        $next_page_selector, $page_url_template, $max_pages, $request_headers, $date_format, $encoding, $enabled,
                        $created_at, $updated_at)
                        """,
                        WebScrapingRuleParameters(rule, feedId, rule.CreatedAt <= 0 ? now : rule.CreatedAt, now));
                }
                else
                {
                    ExecuteNonQuery(
                        connection,
                        """
                        UPDATE web_scraping_rules SET feed_id = $feed_id, name = $name, type = $type, list_url = $list_url,
                        base_url = $base_url, item_selector = $item_selector, title_selector = $title_selector,
                        link_selector = $link_selector, summary_selector = $summary_selector, content_selector = $content_selector,
                        author_selector = $author_selector, date_selector = $date_selector, cover_selector = $cover_selector,
                        next_page_selector = $next_page_selector, page_url_template = $page_url_template, max_pages = $max_pages,
                        request_headers = $request_headers, date_format = $date_format, encoding = $encoding, enabled = $enabled,
                        updated_at = $updated_at WHERE id = $id
                        """,
                        WebScrapingRuleParameters(rule, feedId, null, now).Append(("$id", existingRuleId.Value)).ToArray());
                }

                changed++;
            }

            transaction.Commit();
            return changed;
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public async Task RestoreBackupAsync(BackupDocument document)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            using var transaction = connection.BeginTransaction();
            ExecuteNonQuery(connection, "DELETE FROM articles");
            ExecuteNonQuery(connection, "DELETE FROM web_scraping_rules");
            ExecuteNonQuery(connection, "DELETE FROM feeds");
            ExecuteNonQuery(connection, "DELETE FROM categories");
            foreach (var category in document.Categories)
            {
                ExecuteNonQuery(
                    connection,
                    "INSERT INTO categories(id, name, description, position, created_at, updated_at) VALUES($id, $name, $description, $position, $created_at, $updated_at)",
                    ("$id", category.Id),
                    ("$name", category.Name),
                    ("$description", category.Description),
                    ("$position", category.Position),
                    ("$created_at", category.CreatedAt),
                    ("$updated_at", category.UpdatedAt));
            }

            foreach (var feed in document.Feeds)
            {
                var translationMode = NormalizeTranslationMode(feed.TranslationMode ?? (feed.TranslateEnabled ? "ai" : "off"));
                ExecuteNonQuery(
                    connection,
                    """
                    INSERT INTO feeds(id, category_id, url, title, description, site_url, icon_url, fetch_interval, last_fetched_at,
                    last_error, error_count, is_active, translate_enabled, translation_mode, translation_language, position, created_at, updated_at)
                    VALUES($id, $category_id, $url, $title, $description, $site_url, $icon_url, $fetch_interval, $last_fetched_at,
                    $last_error, $error_count, $is_active, $translate_enabled, $translation_mode, $translation_language, $position, $created_at, $updated_at)
                    """,
                    ("$id", feed.Id),
                    ("$category_id", feed.CategoryId),
                    ("$url", feed.Url),
                    ("$title", feed.Title),
                    ("$description", feed.Description),
                    ("$site_url", feed.SiteUrl),
                    ("$icon_url", feed.IconUrl),
                    ("$fetch_interval", feed.FetchInterval),
                    ("$last_fetched_at", feed.LastFetchedAt),
                    ("$last_error", feed.LastError),
                    ("$error_count", feed.ErrorCount),
                    ("$is_active", feed.IsActive ? 1 : 0),
                    ("$translate_enabled", TranslationEnabled(translationMode) ? 1 : 0),
                    ("$translation_mode", translationMode),
                    ("$translation_language", NormalizeLanguage(feed.TranslationLanguage)),
                    ("$position", feed.Position),
                    ("$created_at", feed.CreatedAt),
                    ("$updated_at", feed.UpdatedAt));
            }

            foreach (var rule in document.WebScrapingRules ?? [])
            {
                ExecuteNonQuery(
                    connection,
                    """
                    INSERT INTO web_scraping_rules(id, feed_id, name, type, list_url, base_url, item_selector, title_selector,
                    link_selector, summary_selector, content_selector, author_selector, date_selector, cover_selector,
                    next_page_selector, page_url_template, max_pages, request_headers, date_format, encoding, enabled,
                    created_at, updated_at)
                    VALUES($id, $feed_id, $name, $type, $list_url, $base_url, $item_selector, $title_selector,
                    $link_selector, $summary_selector, $content_selector, $author_selector, $date_selector, $cover_selector,
                    $next_page_selector, $page_url_template, $max_pages, $request_headers, $date_format, $encoding, $enabled,
                    $created_at, $updated_at)
                    """,
                    WebScrapingRuleParameters(rule, rule.FeedId, rule.CreatedAt, rule.UpdatedAt).Prepend(("$id", rule.Id)).ToArray());
            }

            foreach (var article in document.Articles)
            {
                ExecuteNonQuery(
                    connection,
                    """
                    INSERT INTO articles(id, feed_id, guid, link, title, content, original_title, original_content,
                    translation_language, translation_status, translation_error, author, published_at, created_at,
                    is_read, is_favorite, read_at, favorited_at)
                    VALUES($id, $feed_id, $guid, $link, $title, $content, $original_title, $original_content,
                    $translation_language, $translation_status, $translation_error, $author, $published_at, $created_at,
                    $is_read, $is_favorite, $read_at, $favorited_at)
                    """,
                    ("$id", article.Id),
                    ("$feed_id", article.FeedId),
                    ("$guid", article.Guid),
                    ("$link", article.Link),
                    ("$title", article.Title),
                    ("$content", article.Content),
                    ("$original_title", article.OriginalTitle),
                    ("$original_content", article.OriginalContent),
                    ("$translation_language", article.TranslationLanguage),
                    ("$translation_status", article.TranslationStatus),
                    ("$translation_error", article.TranslationError),
                    ("$author", article.Author),
                    ("$published_at", article.PublishedAt),
                    ("$created_at", article.CreatedAt),
                    ("$is_read", article.IsRead ? 1 : 0),
                    ("$is_favorite", article.IsFavorite ? 1 : 0),
                    ("$read_at", article.ReadAt),
                    ("$favorited_at", article.FavoritedAt));
            }

            transaction.Commit();
        }
        finally
        {
            _writeLock.Release();
        }
    }

    public string ExportOpml()
    {
        var feeds = Feeds();
        var grouped = feeds.GroupBy(feed => string.IsNullOrWhiteSpace(feed.CategoryName) ? "未分类" : feed.CategoryName!);
        var body = new XElement("body");
        foreach (var group in grouped)
        {
            var category = new XElement("outline", new XAttribute("text", group.Key), new XAttribute("title", group.Key));
            foreach (var feed in group)
            {
                category.Add(
                    new XElement(
                        "outline",
                        new XAttribute("type", "rss"),
                        new XAttribute("text", feed.Title),
                        new XAttribute("title", feed.Title),
                        new XAttribute("xmlUrl", feed.Url),
                        new XAttribute("htmlUrl", feed.SiteUrl ?? "")));
            }

            body.Add(category);
        }

        var document = new XDocument(
            new XDeclaration("1.0", "utf-8", null),
            new XElement(
                "opml",
                new XAttribute("version", "2.0"),
                new XElement("head", new XElement("title", "MRSS Subscriptions")),
                body));
        return document.ToString();
    }

    public async Task<int> ImportOpmlAsync(string content)
    {
        await _writeLock.WaitAsync();
        try
        {
            var document = XDocument.Parse(content);
            var outlines = document.Descendants("outline");
            var imported = 0;
            using var connection = Connect();
            using var transaction = connection.BeginTransaction();
            foreach (var outline in outlines)
            {
                var xmlUrl = (string?)outline.Attribute("xmlUrl");
                if (string.IsNullOrWhiteSpace(xmlUrl))
                {
                    continue;
                }

                if (Scalar(connection, "SELECT id FROM feeds WHERE url = $url", ("$url", xmlUrl)) is not null)
                {
                    continue;
                }

                var categoryName = outline.Parent?.Name.LocalName == "outline" ? (string?)outline.Parent.Attribute("text") : null;
                int? categoryId = null;
                if (!string.IsNullOrWhiteSpace(categoryName))
                {
                    var existing = Scalar(connection, "SELECT id FROM categories WHERE name = $name", ("$name", categoryName));
                    if (existing is null)
                    {
                        using var categoryCommand = connection.CreateCommand();
                        categoryCommand.CommandText = "INSERT INTO categories(name, created_at) VALUES($name, $created_at); SELECT last_insert_rowid();";
                        categoryCommand.Parameters.AddWithValue("$name", categoryName);
                        categoryCommand.Parameters.AddWithValue("$created_at", Clock.NowMs());
                        categoryId = Convert.ToInt32(categoryCommand.ExecuteScalar());
                    }
                    else
                    {
                        categoryId = Convert.ToInt32(existing);
                    }
                }

                ExecuteNonQuery(
                    connection,
                    "INSERT INTO feeds(category_id, url, title, site_url, fetch_interval, is_active, created_at) VALUES($category_id, $url, $title, $site_url, 3600, 1, $created_at)",
                    ("$category_id", categoryId),
                    ("$url", xmlUrl),
                    ("$title", (string?)outline.Attribute("title") ?? (string?)outline.Attribute("text") ?? xmlUrl),
                    ("$site_url", (string?)outline.Attribute("htmlUrl")),
                    ("$created_at", Clock.NowMs()));
                imported++;
            }

            transaction.Commit();
            return imported;
        }
        finally
        {
            _writeLock.Release();
        }
    }

    private async Task<int> SaveRefreshAsync(int feedId, ParsedFeed parsed)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            using var transaction = connection.BeginTransaction();
            var ts = Clock.NowMs();
            ExecuteNonQuery(
                connection,
                """
                UPDATE feeds SET title = $title, description = $description, site_url = $site_url, icon_url = $icon_url,
                last_fetched_at = $fetched_at, last_error = NULL, error_count = 0, updated_at = $updated_at WHERE id = $id
                """,
                ("$title", parsed.Title),
                ("$description", parsed.Description),
                ("$site_url", parsed.SiteUrl),
                ("$icon_url", parsed.IconUrl),
                ("$fetched_at", ts),
                ("$updated_at", ts),
                ("$id", feedId));
            var inserted = SaveArticles(connection, feedId, parsed);
            transaction.Commit();
            return inserted;
        }
        finally
        {
            _writeLock.Release();
        }
    }

    private async Task SaveRefreshErrorAsync(int feedId, string error)
    {
        await _writeLock.WaitAsync();
        try
        {
            using var connection = Connect();
            ExecuteNonQuery(connection, "UPDATE feeds SET last_error = $error, last_fetched_at = $fetched_at, error_count = error_count + 1, updated_at = $updated_at WHERE id = $id", ("$error", error), ("$fetched_at", Clock.NowMs()), ("$updated_at", Clock.NowMs()), ("$id", feedId));
        }
        finally
        {
            _writeLock.Release();
        }
    }

    private static int SaveArticles(SqliteConnection connection, int feedId, ParsedFeed parsed)
    {
        var inserted = 0;
        foreach (var article in parsed.Articles)
        {
            using var command = connection.CreateCommand();
            command.CommandText =
                """
                INSERT OR IGNORE INTO articles(feed_id, guid, link, title, content, author, published_at, created_at)
                VALUES($feed_id, $guid, $link, $title, $content, $author, $published_at, $created_at)
                """;
            command.Parameters.AddWithValue("$feed_id", feedId);
            command.Parameters.AddWithValue("$guid", article.Guid);
            command.Parameters.AddWithValue("$link", DbValue(article.Link));
            command.Parameters.AddWithValue("$title", string.IsNullOrWhiteSpace(article.Title) ? "Untitled" : article.Title);
            command.Parameters.AddWithValue("$content", DbValue(article.Content));
            command.Parameters.AddWithValue("$author", DbValue(article.Author));
            command.Parameters.AddWithValue("$published_at", article.PublishedAt);
            command.Parameters.AddWithValue("$created_at", article.CreatedAt);
            inserted += command.ExecuteNonQuery();
        }

        return inserted;
    }

    private static void AddDateFilter(ArticleQuery query, List<string> where, List<(string Name, object? Value)> parameters)
    {
        DateTime? start = query.DateFilter switch
        {
            "today" => DateTime.Today,
            "yesterday" => DateTime.Today.AddDays(-1),
            "7d" => DateTime.Today.AddDays(-6),
            _ => null
        };
        DateTime? end = query.DateFilter == "yesterday" ? DateTime.Today.AddMilliseconds(-1) : null;
        if (start is not null)
        {
            where.Add("CASE WHEN a.published_at = 0 THEN a.created_at ELSE a.published_at END >= $date_start");
            parameters.Add(("$date_start", new DateTimeOffset(start.Value).ToUnixTimeMilliseconds()));
        }

        if (end is not null)
        {
            where.Add("CASE WHEN a.published_at = 0 THEN a.created_at ELSE a.published_at END <= $date_end");
            parameters.Add(("$date_end", new DateTimeOffset(end.Value).ToUnixTimeMilliseconds()));
        }
    }

    private static Feed ReadFeed(SqliteDataReader reader)
    {
        return new Feed
        {
            Id = Int(reader, "id"),
            CategoryId = NullableInt(reader, "category_id"),
            Url = Text(reader, "url"),
            Title = Text(reader, "title"),
            Description = NullableText(reader, "description"),
            SiteUrl = NullableText(reader, "site_url"),
            IconUrl = NullableText(reader, "icon_url"),
            FetchInterval = Int(reader, "fetch_interval"),
            LastFetchedAt = Long(reader, "last_fetched_at"),
            LastError = NullableText(reader, "last_error"),
            ErrorCount = Int(reader, "error_count"),
            IsActive = Int(reader, "is_active") == 1,
            TranslateEnabled = Int(reader, "translate_enabled") == 1,
            TranslationMode = NormalizeTranslationMode(NullableText(reader, "translation_mode")),
            TranslationLanguage = NormalizeLanguage(NullableText(reader, "translation_language")),
            CategoryName = NullableText(reader, "category_name"),
            ArticleCount = Int(reader, "article_count"),
            UnreadCount = Int(reader, "unread_count")
        };
    }

    private static Article ReadArticle(SqliteDataReader reader)
    {
        return new Article
        {
            Id = Int(reader, "id"),
            FeedId = Int(reader, "feed_id"),
            Guid = Text(reader, "guid"),
            Link = NullableText(reader, "link"),
            Title = Text(reader, "title"),
            Content = NullableText(reader, "content"),
            OriginalTitle = NullableText(reader, "original_title"),
            OriginalContent = NullableText(reader, "original_content"),
            TranslationLanguage = NullableText(reader, "translation_language"),
            TranslationStatus = NullableText(reader, "translation_status"),
            TranslationError = NullableText(reader, "translation_error"),
            Author = NullableText(reader, "author"),
            PublishedAt = Long(reader, "published_at"),
            CreatedAt = Long(reader, "created_at"),
            IsRead = Int(reader, "is_read") == 1,
            IsFavorite = Int(reader, "is_favorite") == 1,
            ReadAt = Long(reader, "read_at"),
            FavoritedAt = Long(reader, "favorited_at"),
            FeedTitle = Text(reader, "feed_title"),
            FeedIconUrl = NullableText(reader, "feed_icon_url")
        };
    }

    private static WebScrapingRule ReadWebScrapingRule(SqliteDataReader reader)
    {
        return new WebScrapingRule
        {
            Id = Int(reader, "id"),
            FeedId = NullableInt(reader, "feed_id"),
            Name = Text(reader, "name"),
            Type = NormalizeWebScrapingRuleType(NullableText(reader, "type")),
            ListUrl = Text(reader, "list_url"),
            BaseUrl = NullableText(reader, "base_url"),
            ItemSelector = Text(reader, "item_selector"),
            TitleSelector = NullableText(reader, "title_selector"),
            LinkSelector = NullableText(reader, "link_selector"),
            SummarySelector = NullableText(reader, "summary_selector"),
            ContentSelector = NullableText(reader, "content_selector"),
            AuthorSelector = NullableText(reader, "author_selector"),
            DateSelector = NullableText(reader, "date_selector"),
            CoverSelector = NullableText(reader, "cover_selector"),
            NextPageSelector = NullableText(reader, "next_page_selector"),
            PageUrlTemplate = NullableText(reader, "page_url_template"),
            MaxPages = ClampMaxPages(Int(reader, "max_pages")),
            RequestHeaders = NullableText(reader, "request_headers"),
            DateFormat = NullableText(reader, "date_format"),
            Encoding = NullableText(reader, "encoding"),
            Enabled = Int(reader, "enabled") != 0,
            CreatedAt = Long(reader, "created_at"),
            UpdatedAt = NullableLong(reader, "updated_at")
        };
    }

    private static WebScrapingRuleBackup ReadWebScrapingRuleBackup(SqliteDataReader reader)
    {
        return new WebScrapingRuleBackup
        {
            Id = Int(reader, "id"),
            FeedId = NullableInt(reader, "feed_id"),
            Name = Text(reader, "name"),
            Type = NormalizeWebScrapingRuleType(NullableText(reader, "type")),
            ListUrl = Text(reader, "list_url"),
            BaseUrl = NullableText(reader, "base_url"),
            ItemSelector = Text(reader, "item_selector"),
            TitleSelector = NullableText(reader, "title_selector"),
            LinkSelector = NullableText(reader, "link_selector"),
            SummarySelector = NullableText(reader, "summary_selector"),
            ContentSelector = NullableText(reader, "content_selector"),
            AuthorSelector = NullableText(reader, "author_selector"),
            DateSelector = NullableText(reader, "date_selector"),
            CoverSelector = NullableText(reader, "cover_selector"),
            NextPageSelector = NullableText(reader, "next_page_selector"),
            PageUrlTemplate = NullableText(reader, "page_url_template"),
            MaxPages = ClampMaxPages(Int(reader, "max_pages")),
            RequestHeaders = NullableText(reader, "request_headers"),
            DateFormat = NullableText(reader, "date_format"),
            Encoding = NullableText(reader, "encoding"),
            Enabled = Int(reader, "enabled") == 0 ? 0 : 1,
            CreatedAt = Long(reader, "created_at"),
            UpdatedAt = NullableLong(reader, "updated_at")
        };
    }

    private static AiChannel ReadAiChannel(SqliteDataReader reader)
    {
        return new AiChannel
        {
            Id = Int(reader, "id"),
            Name = Text(reader, "name"),
            Provider = NormalizeAiProvider(Text(reader, "provider"), NullableText(reader, "base_url")),
            BaseUrl = NullableText(reader, "base_url") ?? "",
            ApiKey = NullableText(reader, "api_key") ?? "",
            Model = NullableText(reader, "model") ?? "",
            IsDefault = Int(reader, "is_default") == 1,
            CreatedAt = Long(reader, "created_at"),
            UpdatedAt = NullableLong(reader, "updated_at")
        };
    }

    private static string NormalizeAiProvider(string? provider, string? baseUrl = null)
    {
        if (provider == "openai" && !string.IsNullOrWhiteSpace(baseUrl) && !baseUrl.Trim().TrimEnd('/').Equals("https://api.openai.com/v1", StringComparison.OrdinalIgnoreCase))
        {
            return "openai_compatible";
        }

        return provider switch
        {
            "gemini" => "gemini",
            "qwen" => "qwen",
            "doubao" => "doubao",
            "deepseek" => "deepseek",
            "kimi" => "kimi",
            "zhipu" => "zhipu",
            "openai_compatible" => "openai_compatible",
            _ => "openai"
        };
    }

    private static int? FindCategoryIdByName(SqliteConnection connection, string name)
    {
        var value = Scalar(connection, "SELECT id FROM categories WHERE name = $name", ("$name", name));
        return value is null ? null : Convert.ToInt32(value);
    }

    private static int? FindFeedIdByUrl(SqliteConnection connection, string url)
    {
        var value = Scalar(connection, "SELECT id FROM feeds WHERE url = $url", ("$url", url));
        return value is null ? null : Convert.ToInt32(value);
    }

    private static int? FindKeywordIdByKeyword(SqliteConnection connection, string keyword)
    {
        var value = Scalar(connection, "SELECT id FROM keyword_subscriptions WHERE keyword = $keyword", ("$keyword", keyword));
        return value is null ? null : Convert.ToInt32(value);
    }

    private static int? FindWebScrapingRuleIdByListUrl(SqliteConnection connection, string listUrl)
    {
        var value = Scalar(connection, "SELECT id FROM web_scraping_rules WHERE list_url = $list_url", ("$list_url", listUrl));
        return value is null ? null : Convert.ToInt32(value);
    }

    private static int GetOrCreateCategory(SqliteConnection connection, string name, long now)
    {
        var existing = FindCategoryIdByName(connection, name);
        if (existing is not null)
        {
            return existing.Value;
        }

        using var command = connection.CreateCommand();
        command.CommandText = "INSERT INTO categories(name, created_at, updated_at) VALUES($name, $created_at, $updated_at); SELECT last_insert_rowid();";
        command.Parameters.AddWithValue("$name", Truncate(name, 100));
        command.Parameters.AddWithValue("$created_at", now);
        command.Parameters.AddWithValue("$updated_at", now);
        return Convert.ToInt32(command.ExecuteScalar());
    }

    private static string? CategoryNameByExportId(IEnumerable<SubscriptionCategorySync> categories, int exportId)
    {
        return categories.FirstOrDefault(category => category.Id == exportId)?.Name;
    }

    private static string? FeedUrlByExportId(IEnumerable<SubscriptionFeedSync> feeds, int exportId)
    {
        return feeds.FirstOrDefault(feed => feed.Id == exportId)?.Url;
    }

    private static object? Scalar(SqliteConnection connection, string sql, params (string Name, object? Value)[] parameters)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        AddParameters(command, parameters);
        var value = command.ExecuteScalar();
        return value is DBNull ? null : value;
    }

    private static void ExecuteNonQuery(SqliteConnection connection, string sql, params (string Name, object? Value)[] parameters)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        AddParameters(command, parameters);
        command.ExecuteNonQuery();
    }

    private static void AddParameters(SqliteCommand command, IEnumerable<(string Name, object? Value)> parameters)
    {
        foreach (var parameter in parameters)
        {
            command.Parameters.AddWithValue(parameter.Name, DbValue(parameter.Value));
        }
    }

    private static void AddWebScrapingRuleParameters(SqliteCommand command, WebScrapingRule rule, long? createdAt, long updatedAt)
    {
        AddParameters(command, WebScrapingRuleParameters(rule, createdAt, updatedAt));
    }

    private static (string Name, object? Value)[] WebScrapingRuleParameters(WebScrapingRule rule, long? createdAt, long updatedAt)
    {
        return
        [
            ("$feed_id", rule.FeedId),
            ("$name", Truncate(FirstNonEmpty(rule.Name, rule.ListUrl, "网页订阅"), 255)),
            ("$type", NormalizeWebScrapingRuleType(rule.Type)),
            ("$list_url", Truncate(FirstNonEmpty(rule.ListUrl, ""), 2048)),
            ("$base_url", TruncateNullable(rule.BaseUrl, 2048)),
            ("$item_selector", Truncate(FirstNonEmpty(rule.ItemSelector, ""), 1000)),
            ("$title_selector", TruncateNullable(rule.TitleSelector, 1000)),
            ("$link_selector", TruncateNullable(rule.LinkSelector, 1000)),
            ("$summary_selector", TruncateNullable(rule.SummarySelector, 1000)),
            ("$content_selector", TruncateNullable(rule.ContentSelector, 1000)),
            ("$author_selector", TruncateNullable(rule.AuthorSelector, 1000)),
            ("$date_selector", TruncateNullable(rule.DateSelector, 1000)),
            ("$cover_selector", TruncateNullable(rule.CoverSelector, 1000)),
            ("$next_page_selector", TruncateNullable(rule.NextPageSelector, 1000)),
            ("$page_url_template", TruncateNullable(rule.PageUrlTemplate, 2048)),
            ("$max_pages", ClampMaxPages(rule.MaxPages)),
            ("$request_headers", BlankToNull(rule.RequestHeaders)),
            ("$date_format", TruncateNullable(rule.DateFormat, 200)),
            ("$encoding", TruncateNullable(rule.Encoding, 100)),
            ("$enabled", rule.Enabled ? 1 : 0),
            ("$created_at", createdAt),
            ("$updated_at", updatedAt)
        ];
    }

    private static (string Name, object? Value)[] WebScrapingRuleParameters(WebScrapingRuleBackup rule, int? feedId, long? createdAt, long? updatedAt)
    {
        return
        [
            ("$feed_id", feedId),
            ("$name", Truncate(FirstNonEmpty(rule.Name, rule.ListUrl, "网页订阅"), 255)),
            ("$type", NormalizeWebScrapingRuleType(rule.Type)),
            ("$list_url", Truncate(FirstNonEmpty(rule.ListUrl, ""), 2048)),
            ("$base_url", TruncateNullable(rule.BaseUrl, 2048)),
            ("$item_selector", Truncate(FirstNonEmpty(rule.ItemSelector, ""), 1000)),
            ("$title_selector", TruncateNullable(rule.TitleSelector, 1000)),
            ("$link_selector", TruncateNullable(rule.LinkSelector, 1000)),
            ("$summary_selector", TruncateNullable(rule.SummarySelector, 1000)),
            ("$content_selector", TruncateNullable(rule.ContentSelector, 1000)),
            ("$author_selector", TruncateNullable(rule.AuthorSelector, 1000)),
            ("$date_selector", TruncateNullable(rule.DateSelector, 1000)),
            ("$cover_selector", TruncateNullable(rule.CoverSelector, 1000)),
            ("$next_page_selector", TruncateNullable(rule.NextPageSelector, 1000)),
            ("$page_url_template", TruncateNullable(rule.PageUrlTemplate, 2048)),
            ("$max_pages", ClampMaxPages(rule.MaxPages)),
            ("$request_headers", BlankToNull(rule.RequestHeaders)),
            ("$date_format", TruncateNullable(rule.DateFormat, 200)),
            ("$encoding", TruncateNullable(rule.Encoding, 100)),
            ("$enabled", rule.Enabled == 0 ? 0 : 1),
            ("$created_at", createdAt),
            ("$updated_at", updatedAt)
        ];
    }

    private static object DbValue(object? value)
    {
        return value ?? DBNull.Value;
    }

    private static string Text(SqliteDataReader reader, string name)
    {
        var index = reader.GetOrdinal(name);
        return reader.IsDBNull(index) ? "" : reader.GetString(index);
    }

    private static string? NullableText(SqliteDataReader reader, string name)
    {
        var index = reader.GetOrdinal(name);
        return reader.IsDBNull(index) ? null : reader.GetString(index);
    }

    private static int Int(SqliteDataReader reader, string name)
    {
        var index = reader.GetOrdinal(name);
        return reader.IsDBNull(index) ? 0 : reader.GetInt32(index);
    }

    private static int? NullableInt(SqliteDataReader reader, string name)
    {
        var index = reader.GetOrdinal(name);
        return reader.IsDBNull(index) ? null : reader.GetInt32(index);
    }

    private static long Long(SqliteDataReader reader, string name)
    {
        var index = reader.GetOrdinal(name);
        return reader.IsDBNull(index) ? 0 : reader.GetInt64(index);
    }

    private static long? NullableLong(SqliteDataReader reader, string name)
    {
        var index = reader.GetOrdinal(name);
        return reader.IsDBNull(index) ? null : reader.GetInt64(index);
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Trim();
            }
        }

        return "";
    }

    private static string Truncate(string value, int maxLength)
    {
        return value.Length <= maxLength ? value : value[..maxLength];
    }

    private static string? TruncateNullable(string? value, int maxLength)
    {
        var normalized = BlankToNull(value);
        return normalized is null ? null : Truncate(normalized, maxLength);
    }

    private static string? BlankToNull(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    }

    private static string NormalizeLanguage(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "中文" : value.Trim();
    }

    private static string NormalizeTranslationMode(string? value)
    {
        return value?.Trim().ToLowerInvariant() switch
        {
            "ai" => "ai",
            "standard" => "standard",
            _ => "off"
        };
    }

    private static bool TranslationEnabled(string? mode)
    {
        var normalized = NormalizeTranslationMode(mode);
        return normalized is "ai" or "standard";
    }

    private static string NormalizeWebScrapingRuleType(string? value)
    {
        return value?.Trim().ToLowerInvariant() switch
        {
            "json" => "json",
            _ => "html"
        };
    }

    private static int ClampMaxPages(int value)
    {
        return Math.Clamp(value <= 0 ? 1 : value, 1, 20);
    }

    private static void EnsureColumn(SqliteConnection connection, string table, string column, string definition)
    {
        using var check = connection.CreateCommand();
        check.CommandText = $"PRAGMA table_info({table})";
        using var reader = check.ExecuteReader();
        while (reader.Read())
        {
            if (string.Equals(reader.GetString(1), column, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }
        }

        reader.Close();
        ExecuteNonQuery(connection, $"ALTER TABLE {table} ADD COLUMN {column} {definition}");
    }

    private static string FriendlyRefreshError(Exception ex)
    {
        var message = ex.Message;
        if (ex is HttpRequestException http && http.StatusCode is not null)
        {
            message = $"HTTP {(int)http.StatusCode} {http.StatusCode}";
        }

        if (message.Contains("does not match the end tag", StringComparison.OrdinalIgnoreCase)
            || message.Contains("Data at the root level is invalid", StringComparison.OrdinalIgnoreCase)
            || message.Contains("There are multiple root elements", StringComparison.OrdinalIgnoreCase))
        {
            return "订阅地址返回的内容不是有效 RSS/XML，可能被站点拦截、返回了网页验证页，或该源临时异常。";
        }

        if (message.Contains("NameResolutionFailure", StringComparison.OrdinalIgnoreCase)
            || message.Contains("No such host", StringComparison.OrdinalIgnoreCase))
        {
            return "无法解析域名，请检查网络、代理或订阅源地址。";
        }

        if (message.Contains("timed out", StringComparison.OrdinalIgnoreCase)
            || message.Contains("The operation was canceled", StringComparison.OrdinalIgnoreCase))
        {
            return "请求超时，请稍后重试或检查网络。";
        }

        return string.IsNullOrWhiteSpace(message) ? ex.GetType().Name : message;
    }
}

public sealed class ParsedFeed
{
    public string Url { get; set; } = "";
    public string Title { get; set; } = "";
    public string? Description { get; set; }
    public string? SiteUrl { get; set; }
    public string? IconUrl { get; set; }
    public List<ParsedArticle> Articles { get; set; } = [];
}

public sealed class ParsedArticle
{
    public string Guid { get; set; } = "";
    public string? Link { get; set; }
    public string Title { get; set; } = "";
    public string? Content { get; set; }
    public string? Author { get; set; }
    public long PublishedAt { get; set; }
    public long CreatedAt { get; set; }
}
