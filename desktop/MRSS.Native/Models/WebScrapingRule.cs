namespace MRSS.Native.Models;

public sealed class WebScrapingRule
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
    public bool Enabled { get; set; } = true;
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }
}
