namespace MRSS.Native.Models;

public sealed class AppStats
{
    public int CategoryCount { get; set; }
    public int FeedCount { get; set; }
    public int ActiveFeedCount { get; set; }
    public int ArticleCount { get; set; }
    public int UnreadCount { get; set; }
    public int FavoriteCount { get; set; }
    public int TodayCount { get; set; }
    public int LastSevenDaysCount { get; set; }
    public long LatestArticleAt { get; set; }
}
