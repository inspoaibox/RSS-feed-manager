namespace MRSS.Native.Models;

public sealed class RefreshResult
{
    public int Candidates { get; set; }
    public int Success { get; set; }
    public int Failed { get; set; }
    public int Inserted { get; set; }
    public List<RefreshFailure> Failures { get; } = [];

    public bool HasFailures => Failures.Count > 0;

    public override string ToString()
    {
        return Candidates == 0
            ? "没有需要刷新的订阅"
            : $"成功 {Success} 个，失败 {Failed} 个，新增 {Inserted} 篇";
    }
}

public sealed class RefreshFailure
{
    public int FeedId { get; set; }
    public string FeedTitle { get; set; } = "";
    public string Url { get; set; } = "";
    public string Error { get; set; } = "";

    public string DisplayText => $"{FeedTitle}\n{Url}\n{Error}";
}
