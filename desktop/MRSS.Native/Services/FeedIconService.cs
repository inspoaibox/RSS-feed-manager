using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using MRSS.Native.Models;

namespace MRSS.Native.Services;

public sealed partial class FeedIconService
{
    private static readonly HttpClient HttpClient = CreateHttpClient();
    private readonly string _cacheDirectory;

    public FeedIconService(string cacheDirectory)
    {
        _cacheDirectory = cacheDirectory;
        Directory.CreateDirectory(_cacheDirectory);
    }

    public string? CachedIconPath(Feed feed)
    {
        foreach (var extension in new[] { ".png", ".jpg", ".jpeg", ".ico" })
        {
            var path = Path.Combine(_cacheDirectory, CacheKey(feed) + extension);
            if (File.Exists(path))
            {
                return path;
            }
        }

        return null;
    }

    public async Task<bool> EnsureCachedAsync(Feed feed, CancellationToken cancellationToken)
    {
        if (CachedIconPath(feed) is not null)
        {
            return false;
        }

        foreach (var candidate in CandidateUrls(feed))
        {
            if (await TryDownloadAsync(feed, candidate, cancellationToken))
            {
                return true;
            }
        }

        return false;
    }

    public static string IconText(string title)
    {
        var trimmed = (title ?? "").Trim();
        if (trimmed.Length == 0)
        {
            return "?";
        }

        foreach (var rune in trimmed.EnumerateRunes())
        {
            if (RuneIsLetterOrDigit(rune))
            {
                return rune.ToString().ToUpperInvariant();
            }
        }

        return trimmed[..1].ToUpperInvariant();
    }

    public static string IconColor(string value)
    {
        var colors = new[]
        {
            "#0F766E", "#2563EB", "#7C3AED", "#BE123C",
            "#B45309", "#047857", "#4338CA", "#0369A1"
        };
        var hash = 0;
        foreach (var ch in value ?? "")
        {
            hash = unchecked(hash * 31 + ch);
        }

        return colors[Math.Abs(hash) % colors.Length];
    }

    private async Task<bool> TryDownloadAsync(Feed feed, string url, CancellationToken cancellationToken)
    {
        try
        {
            using var response = await HttpClient.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return false;
            }

            var contentType = response.Content.Headers.ContentType?.MediaType?.ToLowerInvariant() ?? "";
            var extension = ExtensionFromContentType(contentType);
            if (extension is null && !LooksLikeImageUrl(url))
            {
                return false;
            }

            extension ??= ExtensionFromUrl(url);
            await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
            using var memory = new MemoryStream();
            await stream.CopyToAsync(memory, cancellationToken);
            if (memory.Length < 32 || memory.Length > 1024 * 1024)
            {
                return false;
            }

            var path = Path.Combine(_cacheDirectory, CacheKey(feed) + extension);
            await File.WriteAllBytesAsync(path, memory.ToArray(), cancellationToken);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static IEnumerable<string> CandidateUrls(Feed feed)
    {
        if (!string.IsNullOrWhiteSpace(feed.IconUrl) && Uri.TryCreate(feed.IconUrl, UriKind.Absolute, out var iconUri))
        {
            yield return iconUri.ToString();
        }

        var site = FirstValidUri(feed.SiteUrl, feed.Url);
        if (site is null)
        {
            yield break;
        }

        yield return new Uri(site, "/favicon.ico").ToString();
        yield return new Uri(site, "/favicon.png").ToString();
        yield return $"https://www.google.com/s2/favicons?domain={site.Host}&sz=64";
    }

    private static Uri? FirstValidUri(params string?[] values)
    {
        foreach (var value in values)
        {
            if (Uri.TryCreate(value, UriKind.Absolute, out var uri))
            {
                return uri;
            }
        }

        return null;
    }

    private static string CacheKey(Feed feed)
    {
        var source = string.IsNullOrWhiteSpace(feed.Url) ? feed.Id.ToString() : feed.Url.Trim().ToLowerInvariant();
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(source));
        return Convert.ToHexString(bytes)[..24].ToLowerInvariant();
    }

    private static string? ExtensionFromContentType(string contentType)
    {
        return contentType switch
        {
            "image/png" => ".png",
            "image/jpeg" => ".jpg",
            "image/x-icon" or "image/vnd.microsoft.icon" => ".ico",
            _ => null
        };
    }

    private static string ExtensionFromUrl(string url)
    {
        var path = Uri.TryCreate(url, UriKind.Absolute, out var uri) ? uri.AbsolutePath : url;
        var extension = Path.GetExtension(path).ToLowerInvariant();
        return extension is ".png" or ".jpg" or ".jpeg" or ".ico" ? extension : ".ico";
    }

    private static bool LooksLikeImageUrl(string url)
    {
        return ImageUrlRegex().IsMatch(url);
    }

    private static bool RuneIsLetterOrDigit(Rune rune)
    {
        return Rune.GetUnicodeCategory(rune) is
            System.Globalization.UnicodeCategory.UppercaseLetter or
            System.Globalization.UnicodeCategory.LowercaseLetter or
            System.Globalization.UnicodeCategory.TitlecaseLetter or
            System.Globalization.UnicodeCategory.ModifierLetter or
            System.Globalization.UnicodeCategory.OtherLetter or
            System.Globalization.UnicodeCategory.DecimalDigitNumber;
    }

    private static HttpClient CreateHttpClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromSeconds(8) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0 MRSS/0.2");
        return client;
    }

    [GeneratedRegex("\\.(png|jpe?g|ico)(\\?|$)", RegexOptions.IgnoreCase)]
    private static partial Regex ImageUrlRegex();
}
