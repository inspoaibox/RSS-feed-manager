using CodeHollow.FeedReader;
using MRSS.Native.Data;
using System.Net.Http;

namespace MRSS.Native.Services;

public sealed class FeedParser
{
    private static readonly HttpClient HttpClient = CreateHttpClient();

    public async Task<ParsedFeed> ParseAsync(string url, CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.UserAgent.ParseAdd("Mozilla/5.0 (Windows NT 10.0; Win64; x64) MRSS/0.2");
        request.Headers.Accept.ParseAdd("application/rss+xml");
        request.Headers.Accept.ParseAdd("application/atom+xml");
        request.Headers.Accept.ParseAdd("application/xml");
        request.Headers.Accept.ParseAdd("text/xml");
        request.Headers.Accept.ParseAdd("*/*");

        using var response = await HttpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
        response.EnsureSuccessStatusCode();
        var xml = await response.Content.ReadAsStringAsync(cancellationToken);
        if (LooksLikeHtml(xml))
        {
            throw new InvalidOperationException("订阅地址返回了网页内容，不是有效 RSS/XML。");
        }

        var feed = FeedReader.ReadFromString(xml);
        var parsed = new ParsedFeed
        {
            Url = url,
            Title = string.IsNullOrWhiteSpace(feed.Title) ? url : feed.Title,
            Description = feed.Description,
            SiteUrl = feed.Link,
            IconUrl = feed.ImageUrl
        };

        foreach (var item in feed.Items)
        {
            var link = string.IsNullOrWhiteSpace(item.Link) ? null : item.Link;
            var guid = FirstNonEmpty(item.Id, item.Link, item.Title);
            if (string.IsNullOrWhiteSpace(guid))
            {
                guid = Guid.NewGuid().ToString("N");
            }

            var published = item.PublishingDate?.ToUniversalTime();
            parsed.Articles.Add(new ParsedArticle
            {
                Guid = guid,
                Link = link,
                Title = string.IsNullOrWhiteSpace(item.Title) ? "Untitled" : item.Title,
                Content = FirstNonEmpty(item.Content, item.Description),
                Author = string.IsNullOrWhiteSpace(item.Author) ? null : item.Author,
                PublishedAt = published is null ? 0 : new DateTimeOffset(published.Value).ToUnixTimeMilliseconds(),
                CreatedAt = Clock.NowMs()
            });
        }

        return parsed;
    }

    private static HttpClient CreateHttpClient()
    {
        var client = new HttpClient
        {
            Timeout = TimeSpan.FromSeconds(30)
        };
        return client;
    }

    private static bool LooksLikeHtml(string value)
    {
        var text = value.TrimStart();
        return text.StartsWith("<!doctype html", StringComparison.OrdinalIgnoreCase)
            || text.StartsWith("<html", StringComparison.OrdinalIgnoreCase);
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
}
