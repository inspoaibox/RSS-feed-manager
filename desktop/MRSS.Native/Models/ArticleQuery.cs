namespace MRSS.Native.Models;

public sealed class ArticleQuery
{
    public int Limit { get; set; } = 80;
    public int Offset { get; set; }
    public string Search { get; set; } = "";
    public bool UnreadOnly { get; set; }
    public bool FavoriteOnly { get; set; }
    public bool Descending { get; set; } = true;
    public string Sort { get; set; } = "published";
    public string DateFilter { get; set; } = "all";
    public int? FeedId { get; set; }
    public int? CategoryId { get; set; }
    public bool UncategorizedOnly { get; set; }
}
