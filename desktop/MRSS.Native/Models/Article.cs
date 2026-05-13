using System.Text.RegularExpressions;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using MRSS.Native.Services;

namespace MRSS.Native.Models;

public sealed partial class Article : INotifyPropertyChanged
{
    private bool _isRead;
    private bool _isFavorite;

    public int Id { get; set; }
    public int FeedId { get; set; }
    public string Guid { get; set; } = "";
    public string? Link { get; set; }
    public string Title { get; set; } = "";
    public string? Content { get; set; }
    public string? OriginalTitle { get; set; }
    public string? OriginalContent { get; set; }
    public string? TranslationLanguage { get; set; }
    public string? TranslationStatus { get; set; }
    public string? TranslationError { get; set; }
    public bool ShowOriginal { get; set; }
    public string? Author { get; set; }
    public long PublishedAt { get; set; }
    public long CreatedAt { get; set; }
    public bool IsRead
    {
        get => _isRead;
        set
        {
            if (_isRead == value)
            {
                return;
            }

            _isRead = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(IsUnread));
            OnPropertyChanged(nameof(StatusText));
            OnPropertyChanged(nameof(UnreadIndicator));
        }
    }

    public bool IsFavorite
    {
        get => _isFavorite;
        set
        {
            if (_isFavorite == value)
            {
                return;
            }

            _isFavorite = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(DisplayTitle));
        }
    }
    public long ReadAt { get; set; }
    public long FavoritedAt { get; set; }
    public string FeedTitle { get; set; } = "";
    public string? FeedIconUrl { get; set; }
    public string? FeedIconPath { get; set; }
    public string FeedIconText => FeedIconService.IconText(FeedTitle);
    public string FeedIconColor => FeedIconService.IconColor(FeedTitle);
    public bool HasFeedIconPath => !string.IsNullOrWhiteSpace(FeedIconPath);
    public bool HasNoFeedIconPath => !HasFeedIconPath;
    public bool HasTranslation => !string.IsNullOrWhiteSpace(OriginalContent) || !string.IsNullOrWhiteSpace(OriginalTitle);
    public string TranslationBadge => HasTranslation ? $"译文 · {TranslationLanguage}" : "";

    public string ReaderTitle => ShowOriginal && !string.IsNullOrWhiteSpace(OriginalTitle) ? OriginalTitle! : Title;
    public string ReaderContent => ShowOriginal && !string.IsNullOrWhiteSpace(OriginalContent) ? OriginalContent! : Content ?? "";
    public string DisplayTitle => IsFavorite ? "★ " + Title : Title;
    public string DisplayTime => TimeText(PublishedAt == 0 ? CreatedAt : PublishedAt);
    public string Summary => Compact(Content, 170);
    public string PlainContent => StripMarkup(Content);
    public bool IsUnread => !IsRead;
    public string StatusText => IsRead ? "已读" : "未读";
    public string UnreadIndicator => IsRead ? "" : "●";

    public event PropertyChangedEventHandler? PropertyChanged;

    public static string TimeText(long value)
    {
        if (value <= 0)
        {
            return "-";
        }

        return DateTimeOffset.FromUnixTimeMilliseconds(value).LocalDateTime.ToString("yyyy/MM/dd HH:mm");
    }

    public static string Compact(string? value, int length)
    {
        var text = StripMarkup(value);
        return text.Length <= length ? text : text[..Math.Max(0, length - 1)] + "...";
    }

    public static string StripMarkup(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "";
        }

        var text = ScriptStyleRegex().Replace(value, " ");
        text = TagRegex().Replace(text, " ");
        text = System.Net.WebUtility.HtmlDecode(text);
        return SpaceRegex().Replace(text, " ").Trim();
    }

    [GeneratedRegex("(?is)<(script|style).*?>.*?</\\1>")]
    private static partial Regex ScriptStyleRegex();

    [GeneratedRegex("(?s)<[^>]+>")]
    private static partial Regex TagRegex();

    [GeneratedRegex("\\s+")]
    private static partial Regex SpaceRegex();

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
