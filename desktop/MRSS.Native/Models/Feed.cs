namespace MRSS.Native.Models;

public sealed class Feed
{
    public int Id { get; set; }
    public int? CategoryId { get; set; }
    public string Url { get; set; } = "";
    public string Title { get; set; } = "";
    public string? Description { get; set; }
    public string? SiteUrl { get; set; }
    public string? IconUrl { get; set; }
    public int FetchInterval { get; set; } = 3600;
    public long LastFetchedAt { get; set; }
    public string? LastError { get; set; }
    public int ErrorCount { get; set; }
    public bool IsActive { get; set; } = true;
    public bool TranslateEnabled { get; set; }
    public string TranslationMode { get; set; } = "off";
    public string TranslationLanguage { get; set; } = "中文";
    public string? CategoryName { get; set; }
    public int ArticleCount { get; set; }
    public int UnreadCount { get; set; }
}
