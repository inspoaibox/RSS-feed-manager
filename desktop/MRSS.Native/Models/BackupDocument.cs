using System.Text.Json.Serialization;

namespace MRSS.Native.Models;

public sealed class BackupDocument
{
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; } = 1;

    [JsonPropertyName("exported_at")]
    public long ExportedAt { get; set; }

    [JsonPropertyName("categories")]
    public List<CategoryBackup> Categories { get; set; } = [];

    [JsonPropertyName("feeds")]
    public List<FeedBackup> Feeds { get; set; } = [];

    [JsonPropertyName("web_scraping_rules")]
    public List<WebScrapingRuleBackup> WebScrapingRules { get; set; } = [];

    [JsonPropertyName("articles")]
    public List<ArticleBackup> Articles { get; set; } = [];
}

public sealed class SubscriptionSyncDocument
{
    [JsonPropertyName("schema_version")]
    public int SchemaVersion { get; set; } = 1;

    [JsonPropertyName("type")]
    public string Type { get; set; } = "mrss_subscriptions";

    [JsonPropertyName("exported_at")]
    public long ExportedAt { get; set; }

    [JsonPropertyName("categories")]
    public List<SubscriptionCategorySync> Categories { get; set; } = [];

    [JsonPropertyName("feeds")]
    public List<SubscriptionFeedSync> Feeds { get; set; } = [];

    [JsonPropertyName("keyword_subscriptions")]
    public List<KeywordSubscriptionBackup> KeywordSubscriptions { get; set; } = [];

    [JsonPropertyName("web_scraping_rules")]
    public List<WebScrapingRuleBackup> WebScrapingRules { get; set; } = [];
}

public sealed class CategoryBackup
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string? Description { get; set; }
    public int Position { get; set; }
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }
}

public sealed class SubscriptionCategorySync
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string? Description { get; set; }
    public int Position { get; set; }
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }
}

public sealed class SubscriptionFeedSync
{
    public int Id { get; set; }
    public int? CategoryId { get; set; }
    public string Url { get; set; } = "";
    public string Title { get; set; } = "";
    public string? Description { get; set; }
    public string? SiteUrl { get; set; }
    public string? IconUrl { get; set; }
    public int FetchInterval { get; set; } = 3600;
    public int IsActive { get; set; } = 1;
    public int TranslateEnabled { get; set; }
    public string? TranslationMode { get; set; }
    public string? TranslationLanguage { get; set; }
    public int Position { get; set; }
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }
}

public sealed class FeedBackup
{
    public int Id { get; set; }
    public int? CategoryId { get; set; }
    public string Url { get; set; } = "";
    public string Title { get; set; } = "";
    public string? Description { get; set; }
    public string? SiteUrl { get; set; }
    public string? IconUrl { get; set; }
    public int FetchInterval { get; set; }
    public long LastFetchedAt { get; set; }
    public string? LastError { get; set; }
    public int ErrorCount { get; set; }
    public bool IsActive { get; set; }
    public bool TranslateEnabled { get; set; }
    public string? TranslationMode { get; set; }
    public string? TranslationLanguage { get; set; }
    public int Position { get; set; }
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }
}

public sealed class ArticleBackup
{
    public int Id { get; set; }
    public int FeedId { get; set; }
    public string Guid { get; set; } = "";
    public string? Link { get; set; }
    public string Title { get; set; } = "";
    public string? Content { get; set; }
    public string? OriginalTitle { get; set; }
    public string? OriginalContent { get; set; }
    public string? TranslationLanguage { get; set; }
    public string? TranslationStatus { get; set; }
    public string? TranslationError { get; set; }
    public string? Author { get; set; }
    public long PublishedAt { get; set; }
    public long CreatedAt { get; set; }
    public bool IsRead { get; set; }
    public bool IsFavorite { get; set; }
    public long ReadAt { get; set; }
    public long FavoritedAt { get; set; }
}

public sealed class KeywordSubscriptionBackup
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Keyword { get; set; } = "";
    public int IsActive { get; set; } = 1;
    public int MatchTitle { get; set; } = 1;
    public int MatchContent { get; set; } = 1;
    public int MatchAuthor { get; set; }
    public int MatchFeedTitle { get; set; } = 1;
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }
}

public sealed class WebScrapingRuleBackup
{
    public int Id { get; set; }
    public int? FeedId { get; set; }
    public string Name { get; set; } = "";
    public string Type { get; set; } = "html";
    public string ListUrl { get; set; } = "";
    public string? BaseUrl { get; set; }
    public string ItemSelector { get; set; } = "";
    public string? TitleSelector { get; set; }
    public string? LinkSelector { get; set; }
    public string? SummarySelector { get; set; }
    public string? ContentSelector { get; set; }
    public string? AuthorSelector { get; set; }
    public string? DateSelector { get; set; }
    public string? CoverSelector { get; set; }
    public string? NextPageSelector { get; set; }
    public string? PageUrlTemplate { get; set; }
    public int MaxPages { get; set; } = 1;
    public string? RequestHeaders { get; set; }
    public string? DateFormat { get; set; }
    public string? Encoding { get; set; }
    public int Enabled { get; set; } = 1;
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }
}
