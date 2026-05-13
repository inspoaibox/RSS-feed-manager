namespace MRSS.Native.Models;

public sealed class Category
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public int FeedCount { get; set; }
    public int UnreadCount { get; set; }
}
