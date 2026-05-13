namespace MRSS.Native.Models;

public sealed class ArticlePage
{
    public int Total { get; set; }
    public List<Article> Items { get; set; } = [];
}
