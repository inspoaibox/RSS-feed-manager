namespace MRSS.Native.Models;

public sealed class TranslationJob
{
    public int ArticleId { get; set; }
    public int FeedId { get; set; }
    public string TranslationMode { get; set; } = "ai";
    public string TargetLanguage { get; set; } = "中文";
    public string Title { get; set; } = "";
    public string Content { get; set; } = "";
    public string? Link { get; set; }
}

public sealed class ArticleTranslation
{
    public string Title { get; set; } = "";
    public string Content { get; set; } = "";
}
