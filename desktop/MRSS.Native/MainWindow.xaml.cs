using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Threading;
using Microsoft.Win32;
using MRSS.Native.Data;
using MRSS.Native.Models;
using MRSS.Native.Services;

namespace MRSS.Native;

public partial class MainWindow : Window, INotifyPropertyChanged
{
    private readonly Repository _repository = new(AppPaths.DatabasePath);
    private readonly FeedParser _feedParser = new();
    private readonly FeedIconService _feedIconService = new(AppPaths.IconCacheDirectory);
    private readonly AiClient _aiClient = new();
    private readonly StandardTranslationClient _standardTranslationClient = new();
    private readonly BackupService _backupService;
    private readonly CancellationTokenSource _stop = new();
    private List<Category> _categories = [];
    private List<Feed> _feeds = [];
    private AppStats _stats = new();
    private readonly HashSet<string> _expandedNavKeys = [];
    private int _offset;
    private int _totalCount;
    private bool _isBusy;
    private bool _isArticleLoading;
    private int _articleLoadVersion;
    private string _statusText = "就绪";
    private string _scopeTitle = "全部文章";
    private string _countText = "";
    private string _articleStatusText = "";
    private string _searchText = "";
    private bool _unreadOnly;
    private bool _favoriteOnly;
    private bool _descending = true;
    private string _sortLabel = "发布时间";
    private string _dateLabel = "全部日期";
    private NavItem? _selectedNavItem;
    private Article? _selectedArticle;
    private List<RefreshFailure> _lastRefreshFailures = [];
    private bool _suppressScopeChanged;
    private bool _iconRefreshRunning;
    private bool _translationRunning;
    private string _activeFilterPopup = "";

    public MainWindow()
    {
        InitializeComponent();
        _backupService = new BackupService(_repository);
        DataContext = this;
        InitializeCommands();
        Loaded += async (_, _) =>
        {
            StatusText = "正在读取本地数据...";
            await ReloadSummaryAsync(suppressScopeChanged: true);
            await LoadArticlesAsync(false);
            StatusText = "就绪";
            _ = SchedulerLoopAsync(_stop.Token);
            _ = Dispatcher.BeginInvoke(new Action(() => _ = StartupRefreshAsync()), DispatcherPriority.Background);
        };
        Closing += (_, _) => _stop.Cancel();
    }

    public ObservableCollection<NavItem> NavItems { get; } = [];
    public ObservableCollection<Article> Articles { get; } = [];

    public string StatusText
    {
        get => _statusText;
        set => SetField(ref _statusText, value);
    }

    public string ScopeTitle
    {
        get => _scopeTitle;
        set => SetField(ref _scopeTitle, value);
    }

    public string CountText
    {
        get => _countText;
        set => SetField(ref _countText, value);
    }

    public string ArticleStatusText
    {
        get => _articleStatusText;
        set => SetField(ref _articleStatusText, value);
    }

    public string SearchText
    {
        get => _searchText;
        set => SetField(ref _searchText, value);
    }

    public bool UnreadOnly
    {
        get => _unreadOnly;
        set => SetField(ref _unreadOnly, value);
    }

    public bool FavoriteOnly
    {
        get => _favoriteOnly;
        set => SetField(ref _favoriteOnly, value);
    }

    public bool Descending
    {
        get => _descending;
        set => SetField(ref _descending, value);
    }

    public string SortLabel
    {
        get => _sortLabel;
        set => SetField(ref _sortLabel, value);
    }

    public string DateLabel
    {
        get => _dateLabel;
        set => SetField(ref _dateLabel, value);
    }

    public NavItem? SelectedNavItem
    {
        get => _selectedNavItem;
        set
        {
            if (SetField(ref _selectedNavItem, value))
            {
                NotifySelectedNav();
                if (!_suppressScopeChanged)
                {
                    _ = OnScopeChangedAsync();
                }
                else
                {
                    UpdateHeader();
                }
            }
        }
    }

    public Article? SelectedArticle
    {
        get => _selectedArticle;
        set
        {
            if (SetField(ref _selectedArticle, value))
            {
                _ = OnArticleSelectedAsync(value);
            }
        }
    }

    public string ReaderTitle => SelectedArticle?.ReaderTitle ?? "选择一篇文章";
    public string ReaderMeta => SelectedArticle is null ? "文章内容会在这里显示。" : $"{SelectedArticle.FeedTitle} · {SelectedArticle.DisplayTime}" + (string.IsNullOrWhiteSpace(SelectedArticle.Author) ? "" : $" · {SelectedArticle.Author}") + (SelectedArticle.HasTranslation ? $" · {SelectedArticle.TranslationBadge}" : "");
    public FlowDocument ReaderDocument => ArticleDocumentRenderer.Create(SelectedArticle);
    public string FavoriteButtonText => SelectedArticle?.IsFavorite == true ? "取消收藏" : "收藏";
    public string OriginalButtonText => SelectedArticle?.ShowOriginal == true ? "看译文" : "看原文";
    public bool HasTranslatedArticle => SelectedArticle?.HasTranslation == true;
    public bool HasArticles => Articles.Count > 0;
    public bool HasNoArticles => Articles.Count == 0;
    public bool HasSelectedArticle => SelectedArticle is not null;
    public bool HasNoSelectedArticle => SelectedArticle is null;
    public string SelectedNavTitle => SelectedNavItem?.Title ?? "全部文章";
    public string SelectedNavDetail => SelectedNavItem switch
    {
        { Kind: NavKind.All } => "全部本地文章",
        { Kind: NavKind.Category } => "分类，可以重命名或删除",
        { Kind: NavKind.Feed } => "订阅源，可以编辑分类、间隔或停用",
        { Kind: NavKind.Uncategorized } => "没有归入分类的订阅",
        _ => "选择左侧分类或订阅源"
    };
    public string EditNavButtonText => SelectedNavItem?.Kind == NavKind.Feed ? "编辑订阅" : "重命名";

    public ICommand AddFeedCommand { get; private set; } = null!;
    public ICommand AddCategoryCommand { get; private set; } = null!;
    public ICommand ApplyFiltersCommand { get; private set; } = null!;
    public ICommand RefreshCommand { get; private set; } = null!;
    public ICommand MarkAllReadCommand { get; private set; } = null!;
    public ICommand LoadMoreCommand { get; private set; } = null!;
    public ICommand OpenArticleCommand { get; private set; } = null!;
    public ICommand ToggleFavoriteCommand { get; private set; } = null!;
    public ICommand MarkUnreadCommand { get; private set; } = null!;
    public ICommand ToggleOriginalCommand { get; private set; } = null!;
    public ICommand EditNavCommand { get; private set; } = null!;
    public ICommand RenameNavCommand { get; private set; } = null!;
    public ICommand DeleteNavCommand { get; private set; } = null!;
    public ICommand SettingsCommand { get; private set; } = null!;
    public ICommand ShowRefreshFailuresCommand { get; private set; } = null!;
    public ICommand ToggleNavExpansionCommand { get; private set; } = null!;

    public event PropertyChangedEventHandler? PropertyChanged;

    private void InitializeCommands()
    {
        AddFeedCommand = new RelayCommand(async () => await AddFeedAsync(), () => !_isBusy);
        AddCategoryCommand = new RelayCommand(async () => await AddCategoryAsync(), () => !_isBusy);
        ApplyFiltersCommand = new RelayCommand(async () => await LoadArticlesAsync(false));
        RefreshCommand = new RelayCommand(async () => await RefreshCurrentAsync(), () => !_isBusy);
        MarkAllReadCommand = new RelayCommand(async () => await MarkAllReadAsync(), () => !_isBusy);
        LoadMoreCommand = new RelayCommand(async () => await LoadArticlesAsync(true), () => !_isArticleLoading && _offset < _totalCount);
        OpenArticleCommand = new RelayCommand(OpenArticle, () => SelectedArticle is not null);
        ToggleFavoriteCommand = new RelayCommand(async () => await ToggleFavoriteAsync(), () => SelectedArticle is not null);
        MarkUnreadCommand = new RelayCommand(async () => await MarkUnreadAsync(), () => SelectedArticle is not null);
        ToggleOriginalCommand = new RelayCommand(ToggleOriginal, () => SelectedArticle?.HasTranslation == true);
        EditNavCommand = new RelayCommand(async () => await EditSelectedNavAsync(), () => CanEditSelectedNav());
        RenameNavCommand = new RelayCommand(async () => await RenameSelectedNavAsync(), () => SelectedNavItem is not null && SelectedNavItem.Kind != NavKind.All && SelectedNavItem.Kind != NavKind.Uncategorized);
        DeleteNavCommand = new RelayCommand(async () => await DeleteSelectedNavAsync(), () => SelectedNavItem is not null && SelectedNavItem.Kind != NavKind.All && SelectedNavItem.Kind != NavKind.Uncategorized);
        SettingsCommand = new RelayCommand(async () => await OpenSettingsAsync(), () => !_isBusy);
        ShowRefreshFailuresCommand = new RelayCommand(ShowRefreshFailures, () => _lastRefreshFailures.Count > 0);
        ToggleNavExpansionCommand = new RelayCommand(ToggleNavExpansion);
    }

    private async Task ReloadSummaryAsync(string? selectKey = null, bool suppressScopeChanged = false)
    {
        _categories = await Task.Run(_repository.Categories);
        _feeds = await Task.Run(_repository.Feeds);
        _stats = await Task.Run(_repository.Stats);
        BuildNav(selectKey, suppressScopeChanged);
        UpdateHeader();
        _ = EnsureFeedIconsAsync();
    }

    private async Task EnsureFeedIconsAsync()
    {
        if (_iconRefreshRunning)
        {
            return;
        }

        _iconRefreshRunning = true;

        try
        {
            var changed = false;
            foreach (var feed in _feeds)
            {
                if (_stop.IsCancellationRequested)
                {
                    return;
                }

                changed |= await _feedIconService.EnsureCachedAsync(feed, _stop.Token);
            }

            if (changed)
            {
                await Dispatcher.InvokeAsync(() => BuildNav(SelectedNavItem?.Key, true));
            }
        }
        catch
        {
        }
        finally
        {
            _iconRefreshRunning = false;
        }
    }

    private void BuildNav(string? selectKey = null, bool suppressScopeChanged = false)
    {
        var currentKey = selectKey ?? SelectedNavItem?.Key ?? "all";
        EnsureExpandedForSelection(currentKey);
        var previousSuppress = _suppressScopeChanged;
        _suppressScopeChanged = suppressScopeChanged;
        NavItems.Clear();
        try
        {
            NavItems.Add(new NavItem { Kind = NavKind.All, Title = "全部文章", Subtitle = CountTextFor(_stats.UnreadCount), Level = 0, IconText = "全", IconColor = "#0F766E" });
            var feedsByCategory = _feeds.Where(feed => feed.CategoryId is not null).GroupBy(feed => feed.CategoryId!.Value).ToDictionary(group => group.Key, group => group.ToList());
            foreach (var category in _categories)
            {
                var categoryKey = NavKey(NavKind.Category, category.Id);
                var categoryExpanded = _expandedNavKeys.Contains(categoryKey);
                var childCount = feedsByCategory.TryGetValue(category.Id, out var categoryFeeds) ? categoryFeeds.Count : 0;
                NavItems.Add(new NavItem { Kind = NavKind.Category, Id = category.Id, Title = category.Name, Subtitle = $"{CountTextFor(category.UnreadCount)} · {childCount} 个订阅", Level = 0, IconText = FeedIconService.IconText(category.Name), IconColor = FeedIconService.IconColor(category.Name), HasChildren = childCount > 0, IsExpanded = categoryExpanded });
                if (childCount > 0)
                {
                    feedsByCategory.Remove(category.Id);
                }

                if (categoryExpanded && childCount > 0)
                {
                    foreach (var feed in categoryFeeds!)
                    {
                        NavItems.Add(NavItemForFeed(feed));
                    }
                }
            }

            var ungrouped = _feeds.Where(feed => feed.CategoryId is null).ToList();
            if (ungrouped.Count > 0)
            {
                var ungroupedKey = NavKey(NavKind.Uncategorized, null);
                var ungroupedExpanded = _expandedNavKeys.Contains(ungroupedKey);
                NavItems.Add(new NavItem { Kind = NavKind.Uncategorized, Title = "未分类", Subtitle = $"{ungrouped.Count} 个订阅", Level = 0, IconText = "未", IconColor = "#667085", HasChildren = true, IsExpanded = ungroupedExpanded });
                if (ungroupedExpanded)
                {
                    foreach (var feed in ungrouped)
                    {
                        NavItems.Add(NavItemForFeed(feed));
                    }
                }
            }

            SelectedNavItem = NavItems.FirstOrDefault(item => item.Key == currentKey) ?? NavItems.FirstOrDefault();
        }
        finally
        {
            _suppressScopeChanged = previousSuppress;
        }
    }

    private NavItem NavItemForFeed(Feed feed)
    {
        return new NavItem
        {
            Kind = NavKind.Feed,
            Id = feed.Id,
            Title = feed.Title,
            Subtitle = CountTextFor(feed.UnreadCount),
            Level = 1,
            IconPath = _feedIconService.CachedIconPath(feed),
            IconText = FeedIconService.IconText(feed.Title),
            IconColor = FeedIconService.IconColor(feed.Url)
        };
    }

    private void ToggleNavExpansion(object? parameter)
    {
        if (parameter is not NavItem { HasChildren: true } item)
        {
            return;
        }

        var key = item.Key;
        if (!_expandedNavKeys.Add(key))
        {
            _expandedNavKeys.Remove(key);
        }

        BuildNav(SelectedNavItem?.Key, true);
    }

    private void EnsureExpandedForSelection(string? key)
    {
        if (string.IsNullOrWhiteSpace(key) || !key.StartsWith("Feed:", StringComparison.Ordinal))
        {
            return;
        }

        var idText = key["Feed:".Length..];
        if (!int.TryParse(idText, out var feedId))
        {
            return;
        }

        var feed = _feeds.FirstOrDefault(item => item.Id == feedId);
        if (feed?.CategoryId is int categoryId)
        {
            _expandedNavKeys.Add(NavKey(NavKind.Category, categoryId));
        }
        else
        {
            _expandedNavKeys.Add(NavKey(NavKind.Uncategorized, null));
        }
    }

    private static string NavKey(NavKind kind, int? id)
    {
        return kind == NavKind.All ? "all" : $"{kind}:{id}";
    }

    private async Task OnScopeChangedAsync()
    {
        UpdateHeader();
        await LoadArticlesAsync(false);
    }

    private void UpdateHeader()
    {
        ScopeTitle = SelectedNavItem?.Title ?? "全部文章";
        CountText = $"{_stats.ArticleCount} 篇文章 · {_stats.UnreadCount} 未读 · {_stats.FavoriteCount} 收藏";
        NotifySelectedNav();
    }

    private async Task LoadArticlesAsync(bool append)
    {
        if (append && _isArticleLoading)
        {
            return;
        }

        var loadVersion = append ? _articleLoadVersion : Interlocked.Increment(ref _articleLoadVersion);
        _isArticleLoading = true;
        NotifyCommands();

        try
        {
            var query = BuildArticleQuery();
            query.Offset = append ? _offset : 0;
            var feedsById = _feeds.ToDictionary(item => item.Id);

            if (!append)
            {
                _offset = 0;
                SelectedArticle = null;
                Articles.Clear();
                ArticleStatusText = "正在读取本地文章...";
                OnPropertyChanged(nameof(HasArticles));
                OnPropertyChanged(nameof(HasNoArticles));
            }
            else
            {
                ArticleStatusText = $"正在加载更多... 已显示 {Articles.Count} / {_totalCount} 篇";
            }

            var page = await Task.Run(() => _repository.Articles(query));
            if (loadVersion != _articleLoadVersion)
            {
                return;
            }

            _totalCount = page.Total;
            if (!append)
            {
                Articles.Clear();
            }

            foreach (var article in page.Items)
            {
                if (feedsById.TryGetValue(article.FeedId, out var feed))
                {
                    article.FeedIconPath = _feedIconService.CachedIconPath(feed);
                }

                Articles.Add(article);
            }

            _offset = Articles.Count;
            ArticleStatusText = Articles.Count == 0 ? "暂无文章" : $"已显示 {Articles.Count} / {_totalCount} 篇";
            OnPropertyChanged(nameof(HasArticles));
            OnPropertyChanged(nameof(HasNoArticles));
        }
        catch (Exception ex) when (loadVersion == _articleLoadVersion)
        {
            ArticleStatusText = $"本地读取失败：{ex.Message}";
        }
        finally
        {
            if (loadVersion == _articleLoadVersion)
            {
                _isArticleLoading = false;
                NotifyCommands();
            }
        }
    }

    private ArticleQuery BuildArticleQuery()
    {
        var query = new ArticleQuery
        {
            Limit = 80,
            Search = SearchText,
            UnreadOnly = UnreadOnly,
            FavoriteOnly = FavoriteOnly,
            Descending = Descending,
            Sort = SortLabel switch
            {
                "创建时间" => "created",
                "标题" => "title",
                _ => "published"
            },
            DateFilter = DateLabel switch
            {
                "今天" => "today",
                "昨天" => "yesterday",
                "最近 7 天" => "7d",
                _ => "all"
            }
        };

        if (SelectedNavItem?.Kind == NavKind.Feed)
        {
            query.FeedId = SelectedNavItem.Id;
        }
        else if (SelectedNavItem?.Kind == NavKind.Category)
        {
            query.CategoryId = SelectedNavItem.Id;
        }
        else if (SelectedNavItem?.Kind == NavKind.Uncategorized)
        {
            query.UncategorizedOnly = true;
        }

        return query;
    }

    private async Task OnArticleSelectedAsync(Article? article)
    {
        NotifyReader();
        NotifyCommands();
        if (article is null || article.IsRead)
        {
            return;
        }

        article.IsRead = true;
        await _repository.MarkReadAsync(article.Id, true);
        await ReloadSummaryAsync(SelectedNavItem?.Key, true);
        NotifyReader();
    }

    private void ToggleOriginal()
    {
        if (SelectedArticle?.HasTranslation != true)
        {
            return;
        }

        SelectedArticle.ShowOriginal = !SelectedArticle.ShowOriginal;
        NotifyReader();
    }

    private async Task AddFeedAsync()
    {
        int? defaultCategoryId = SelectedNavItem?.Kind == NavKind.Category
            ? SelectedNavItem.Id
            : SelectedNavItem?.Kind == NavKind.Feed
                ? _feeds.FirstOrDefault(feed => feed.Id == SelectedNavItem.Id)?.CategoryId
                : null;
        var data = AddFeedDialog.Show(
            this,
            _categories,
            defaultCategoryId,
            _repository.GetSetting("default_translation_language", "中文"),
            _repository.GetSetting("default_translation_mode", "off"));
        if (data is null)
        {
            return;
        }

        SetBusy(true, "正在添加订阅并抓取文章...");
        try
        {
            var parsed = await _feedParser.ParseAsync(data.Url, _stop.Token);
            await _repository.AddFeedAsync(parsed, data.CategoryId, data.FetchIntervalMinutes * 60, data.TranslationMode, data.TranslationLanguage);
            _ = TranslatePendingArticlesAsync();
            await ReloadCurrentViewAsync();
            MessageBox.Show(this, "订阅已添加。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "添加订阅失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            SetBusy(false, "就绪");
        }
    }

    private async Task AddCategoryAsync()
    {
        var name = InputDialogs.AskText(this, "MRSS", "分类名称：");
        if (string.IsNullOrWhiteSpace(name))
        {
            return;
        }

        try
        {
            var id = await _repository.AddCategoryAsync(name.Trim());
            await ReloadSummaryAsync($"Category:{id}");
        }
        catch (Exception ex)
        {
            MessageBox.Show(this, ex.Message, "新建分类失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async Task RefreshCurrentAsync()
    {
        SetBusy(true, "正在刷新...");
        try
        {
            var result = await _repository.RefreshFeedsAsync(_feedParser.ParseAsync, SelectedNavItem?.Kind == NavKind.Feed ? SelectedNavItem.Id : null, SelectedNavItem?.Kind == NavKind.Category ? SelectedNavItem.Id : null, SelectedNavItem?.Kind == NavKind.Uncategorized, false, _stop.Token);
            if (result.Inserted > 0)
            {
                await TranslatePendingArticlesAsync();
            }
            SetRefreshFailures(result.Failures);
            await ReloadCurrentViewAsync();
            StatusText = $"刷新完成：{result}";
            if (result.HasFailures)
            {
                MessageBox.Show(this, FailureSummary(result), "刷新失败详情", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }
        finally
        {
            SetBusy(false, StatusText);
        }
    }

    private async Task StartupRefreshAsync()
    {
        if (_feeds.Count == 0)
        {
            return;
        }

        if (!GetBoolSetting("refresh_on_startup", true))
        {
            return;
        }

        StatusText = "启动后同步全部订阅中...";
        try
        {
            var result = await _repository.RefreshFeedsAsync(_feedParser.ParseAsync, dueOnly: false, cancellationToken: _stop.Token);
            if (result.Inserted > 0)
            {
                await TranslatePendingArticlesAsync();
            }
            SetRefreshFailures(result.Failures);
            await ReloadCurrentViewAsync();
            StatusText = $"启动同步完成：{result}";
        }
        catch
        {
            StatusText = "启动同步遇到错误，可稍后手动刷新。";
        }
        finally
        {
            NotifyCommands();
        }
    }

    private async Task SchedulerLoopAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                await Task.Delay(TimeSpan.FromMinutes(SchedulerIntervalMinutes()), cancellationToken);
                var result = await _repository.RefreshFeedsAsync(_feedParser.ParseAsync, dueOnly: true, cancellationToken: cancellationToken);
                if (result.Inserted > 0)
                {
                    await Dispatcher.InvokeAsync(async () => await TranslatePendingArticlesAsync());
                }
                SetRefreshFailures(result.Failures);
                if (result.Inserted > 0)
                {
                    await Dispatcher.InvokeAsync(async () =>
                    {
                        await ReloadCurrentViewAsync();
                        StatusText = $"后台同步新增 {result.Inserted} 篇文章";
                    });
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch
            {
            }
        }
    }

    private async Task MarkAllReadAsync()
    {
        var count = await _repository.MarkAllReadAsync(SelectedNavItem?.Kind == NavKind.Feed ? SelectedNavItem.Id : null, SelectedNavItem?.Kind == NavKind.Category ? SelectedNavItem.Id : null, SelectedNavItem?.Kind == NavKind.Uncategorized);
        await ReloadCurrentViewAsync();
        StatusText = $"已标记 {count} 篇为已读";
    }

    private async Task TranslatePendingArticlesAsync()
    {
        if (_translationRunning)
        {
            return;
        }

        _translationRunning = true;
        try
        {
            await TranslateAiPendingArticlesAsync();
            await TranslateStandardPendingArticlesAsync();
            await ReloadCurrentViewAsync();
        }
        finally
        {
            _translationRunning = false;
        }
    }

    private async Task TranslateAiPendingArticlesAsync()
    {
        var channel = _repository.DefaultAiChannel();
        if (channel is null || string.IsNullOrWhiteSpace(channel.ApiKey) || string.IsNullOrWhiteSpace(channel.Model))
        {
            return;
        }

        await TranslatePendingBatchAsync("ai", 8, job => _aiClient.TranslateAsync(channel, job, _stop.Token));
    }

    private async Task TranslateStandardPendingArticlesAsync()
    {
        var settings = StandardTranslationSettingsFromRepository();
        await TranslatePendingBatchAsync("standard", 10, job => _standardTranslationClient.TranslateAsync(settings, job, _stop.Token));
    }

    private async Task TranslatePendingBatchAsync(string translationMode, int batchSize, Func<TranslationJob, Task<ArticleTranslation>> translator)
    {
        while (!_stop.IsCancellationRequested)
        {
            var jobs = await Task.Run(() => _repository.PendingTranslationJobs(translationMode, batchSize));
            if (jobs.Count == 0)
            {
                break;
            }

            foreach (var job in jobs)
            {
                try
                {
                    var translation = await translator(job);
                    await _repository.SaveTranslationAsync(job.ArticleId, job.TargetLanguage, translation);
                }
                catch (Exception ex)
                {
                    await _repository.MarkTranslationFailedAsync(job.ArticleId, ex.Message);
                }
            }
        }
    }

    private void OpenArticle()
    {
        if (SelectedArticle?.Link is not { Length: > 0 } link)
        {
            MessageBox.Show(this, "这篇文章没有原文链接。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        Process.Start(new ProcessStartInfo(link) { UseShellExecute = true });
    }

    private async Task ToggleFavoriteAsync()
    {
        if (SelectedArticle is null)
        {
            return;
        }

        SelectedArticle.IsFavorite = await _repository.ToggleFavoriteAsync(SelectedArticle.Id);
        await ReloadSummaryAsync(SelectedNavItem?.Key, true);
        NotifyReader();
        await LoadArticlesAsync(false);
    }

    private async Task MarkUnreadAsync()
    {
        if (SelectedArticle is null)
        {
            return;
        }

        await _repository.MarkReadAsync(SelectedArticle.Id, false);
        SelectedArticle.IsRead = false;
        await ReloadSummaryAsync(SelectedNavItem?.Key, true);
        NotifyReader();
        await LoadArticlesAsync(false);
    }

    private async Task RenameSelectedNavAsync()
    {
        if (SelectedNavItem is null)
        {
            return;
        }

        if (SelectedNavItem.Kind == NavKind.Category)
        {
            var name = InputDialogs.AskText(this, "MRSS", "新的分类名称：", SelectedNavItem.Title);
            if (!string.IsNullOrWhiteSpace(name))
            {
                await _repository.UpdateCategoryAsync(SelectedNavItem.Id!.Value, name.Trim());
                await ReloadSummaryAsync(SelectedNavItem.Key);
            }
        }
        else if (SelectedNavItem.Kind == NavKind.Feed)
        {
            var feed = _feeds.FirstOrDefault(item => item.Id == SelectedNavItem.Id);
            if (feed is null)
            {
                return;
            }

            var title = InputDialogs.AskText(this, "MRSS", "新的订阅名称：", feed.Title);
            if (!string.IsNullOrWhiteSpace(title))
            {
                feed.Title = title.Trim();
                await _repository.UpdateFeedAsync(feed);
                await ReloadSummaryAsync(SelectedNavItem.Key);
            }
        }
    }

    private bool CanEditSelectedNav()
    {
        return SelectedNavItem is not null && SelectedNavItem.Kind != NavKind.All && SelectedNavItem.Kind != NavKind.Uncategorized;
    }

    private async Task EditSelectedNavAsync()
    {
        if (SelectedNavItem is null)
        {
            return;
        }

        if (SelectedNavItem.Kind == NavKind.Category)
        {
            await RenameSelectedNavAsync();
            return;
        }

        if (SelectedNavItem.Kind != NavKind.Feed)
        {
            return;
        }

        var feed = _feeds.FirstOrDefault(item => item.Id == SelectedNavItem.Id);
        if (feed is null)
        {
            MessageBox.Show(this, "没有找到这个订阅源。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        var result = FeedEditDialog.Show(this, feed, _categories);
        if (result is null)
        {
            return;
        }

        feed.Title = result.Title;
        feed.CategoryId = result.CategoryId;
        feed.FetchInterval = result.FetchIntervalMinutes * 60;
        feed.IsActive = result.IsActive;
        feed.TranslateEnabled = result.TranslateEnabled;
        feed.TranslationMode = result.TranslationMode;
        feed.TranslationLanguage = result.TranslationLanguage;
        await _repository.UpdateFeedAsync(feed);
        _ = TranslatePendingArticlesAsync();
        await ReloadCurrentViewAsync();
        StatusText = "订阅设置已保存";
    }

    private async Task DeleteSelectedNavAsync()
    {
        if (SelectedNavItem is null)
        {
            return;
        }

        if (SelectedNavItem.Kind == NavKind.Category)
        {
            if (MessageBox.Show(this, $"删除分类“{SelectedNavItem.Title}”？订阅会移到未分类。", "MRSS", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
            {
                await _repository.DeleteCategoryAsync(SelectedNavItem.Id!.Value);
                await ReloadCurrentViewAsync();
            }
        }
        else if (SelectedNavItem.Kind == NavKind.Feed)
        {
            if (MessageBox.Show(this, $"删除订阅“{SelectedNavItem.Title}”？对应文章也会删除。", "MRSS", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
            {
                await _repository.DeleteFeedAsync(SelectedNavItem.Id!.Value);
                await ReloadCurrentViewAsync();
            }
        }
    }

    private async Task ReloadCurrentViewAsync()
    {
        var key = SelectedNavItem?.Key;
        await ReloadSummaryAsync(key, true);
        await LoadArticlesAsync(false);
    }

    private async void MoreButton_Click(object sender, RoutedEventArgs e)
    {
        var menu = new ContextMenu();
        AddMenuItem(menu, "导出 JSON 备份", async () => await ExportBackupAsync());
        AddMenuItem(menu, "导入 JSON 备份", async () => await ImportBackupAsync());
        menu.Items.Add(new Separator());
        AddMenuItem(menu, "导出 OPML", ExportOpml);
        AddMenuItem(menu, "导入 OPML", async () => await ImportOpmlAsync());
        menu.Items.Add(new Separator());
        AddMenuItem(menu, "上传订阅到 GitHub Gist", async () => await UploadGistAsync());
        AddMenuItem(menu, "从 GitHub Gist 下载合并", async () => await DownloadGistAsync());
        menu.PlacementTarget = (Button)sender;
        menu.IsOpen = true;
        await Task.CompletedTask;
    }

    private void SortFilterButton_Click(object sender, RoutedEventArgs e)
    {
        ShowFilterPopup((Button)sender, "sort", ["发布时间", "创建时间", "标题"], SortLabel);
    }

    private void DateFilterButton_Click(object sender, RoutedEventArgs e)
    {
        ShowFilterPopup((Button)sender, "date", ["全部日期", "今天", "昨天", "最近 7 天"], DateLabel);
    }

    private void ShowFilterPopup(Button target, string kind, IReadOnlyList<string> options, string current)
    {
        _activeFilterPopup = kind;
        FilterPopup.PlacementTarget = target;
        FilterPopupList.SelectionChanged -= FilterPopupList_SelectionChanged;
        FilterPopupList.ItemsSource = options.Select(option => new FilterChoice { Label = option, IsSelected = option == current }).ToList();
        FilterPopupList.SelectedItem = FilterPopupList.Items.Cast<FilterChoice>().FirstOrDefault(item => item.IsSelected);
        FilterPopupList.SelectionChanged += FilterPopupList_SelectionChanged;
        FilterPopup.MinWidth = Math.Max(target.ActualWidth, 142);
        FilterPopup.IsOpen = true;
    }

    private async void FilterPopupList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (!FilterPopup.IsOpen || FilterPopupList.SelectedItem is not FilterChoice choice)
        {
            return;
        }

        FilterPopup.IsOpen = false;
        if (_activeFilterPopup == "sort")
        {
            if (SortLabel == choice.Label)
            {
                return;
            }

            SortLabel = choice.Label;
        }
        else if (_activeFilterPopup == "date")
        {
            if (DateLabel == choice.Label)
            {
                return;
            }

            DateLabel = choice.Label;
        }
        else
        {
            return;
        }

        await LoadArticlesAsync(false);
    }

    private static void AddMenuItem(ItemsControl menu, string header, Action action)
    {
        var item = new MenuItem { Header = header };
        item.Click += (_, _) => action();
        menu.Items.Add(item);
    }

    private static void AddMenuItem(ItemsControl menu, string header, Func<Task> action)
    {
        var item = new MenuItem { Header = header };
        item.Click += async (_, _) => await action();
        menu.Items.Add(item);
    }

    private async Task ExportBackupAsync()
    {
        var dialog = new SaveFileDialog { Title = "导出备份", Filter = "JSON (*.json)|*.json|All files (*.*)|*.*", FileName = "mrss-backup.json" };
        if (dialog.ShowDialog(this) == true)
        {
            await File.WriteAllTextAsync(dialog.FileName, _backupService.ExportJson());
            StatusText = $"备份已导出：{dialog.FileName}";
        }
    }

    private async Task ImportBackupAsync()
    {
        var dialog = new OpenFileDialog { Title = "导入备份", Filter = "JSON (*.json)|*.json|All files (*.*)|*.*" };
        if (dialog.ShowDialog(this) == true && MessageBox.Show(this, "导入会覆盖当前本地数据，继续？", "MRSS", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
        {
            await _backupService.ImportJsonAsync(await File.ReadAllTextAsync(dialog.FileName));
            await ReloadCurrentViewAsync();
        }
    }

    private void ExportOpml()
    {
        var dialog = new SaveFileDialog { Title = "导出 OPML", Filter = "OPML (*.opml;*.xml)|*.opml;*.xml|All files (*.*)|*.*", FileName = "mrss-subscriptions.opml" };
        if (dialog.ShowDialog(this) == true)
        {
            File.WriteAllText(dialog.FileName, _repository.ExportOpml());
            StatusText = $"OPML 已导出：{dialog.FileName}";
        }
    }

    private async Task ImportOpmlAsync()
    {
        var dialog = new OpenFileDialog { Title = "导入 OPML", Filter = "OPML (*.opml;*.xml)|*.opml;*.xml|All files (*.*)|*.*" };
        if (dialog.ShowDialog(this) == true)
        {
            var count = await _repository.ImportOpmlAsync(await File.ReadAllTextAsync(dialog.FileName));
            await ReloadCurrentViewAsync();
            MessageBox.Show(this, $"已导入 {count} 个订阅。可以点击刷新抓取文章。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
        }
    }

    private async Task UploadGistAsync()
    {
        var data = AskGistData(false);
        if (data is null)
        {
            return;
        }

        SetBusy(true, "正在上传到 GitHub Gist...");
        try
        {
            var id = await _backupService.UploadGistAsync(data.Value.Token, data.Value.GistId, data.Value.Filename, _stop.Token);
            MessageBox.Show(this, $"上传完成。\nGist ID：{id}", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        finally
        {
            SetBusy(false, "就绪");
        }
    }

    private async Task OpenSettingsAsync()
    {
        var settings = LoadSettings();
        var window = new SettingsWindow(this, settings, _repository.AiChannels(), _aiClient);
        if (window.ShowDialog() != true)
        {
            return;
        }

        await SaveSettingsAsync(settings);
        StatusText = "设置已保存";
    }

    private AppSettingsView LoadSettings()
    {
        return new AppSettingsView
        {
            GithubToken = _repository.GetSetting("github_token"),
            GistId = _repository.GetSetting("gist_id"),
            GistFilename = _repository.GetSetting("gist_filename", "mrss-subscriptions.json"),
            RefreshOnStartup = GetBoolSetting("refresh_on_startup", true),
            StartupRefreshMinutes = SchedulerIntervalMinutes(),
            DefaultTranslationMode = NormalizeTranslationMode(_repository.GetSetting("default_translation_mode", "off")),
            DefaultTranslationLanguage = _repository.GetSetting("default_translation_language", "中文"),
            StandardTranslationProvider = NormalizeStandardTranslationProvider(_repository.GetSetting("standard_translation_provider", "microsoft")),
            BaiduTranslateAppId = _repository.GetSetting("baidu_translate_app_id"),
            BaiduTranslateSecret = _repository.GetSetting("baidu_translate_secret"),
            TencentTranslateSecretId = _repository.GetSetting("tencent_translate_secret_id"),
            TencentTranslateSecretKey = _repository.GetSetting("tencent_translate_secret_key"),
            TencentTranslateRegion = _repository.GetSetting("tencent_translate_region", "ap-beijing"),
            GoogleTranslateApiKey = _repository.GetSetting("google_translate_api_key"),
            MicrosoftTranslateKey = _repository.GetSetting("microsoft_translate_key"),
            MicrosoftTranslateRegion = _repository.GetSetting("microsoft_translate_region", "global"),
            AiChannels = _repository.AiChannels()
        };
    }

    private async Task SaveSettingsAsync(AppSettingsView settings)
    {
        await _repository.SetSettingAsync("github_token", settings.GithubToken.Trim());
        await _repository.SetSettingAsync("gist_id", settings.GistId.Trim());
        await _repository.SetSettingAsync("gist_filename", settings.GistFilename.Trim());
        await _repository.SetSettingAsync("refresh_on_startup", settings.RefreshOnStartup ? "1" : "0");
        await _repository.SetSettingAsync("scheduler_interval_minutes", settings.StartupRefreshMinutes.ToString());
        await _repository.SetSettingAsync("default_translation_mode", NormalizeTranslationMode(settings.DefaultTranslationMode));
        await _repository.SetSettingAsync("default_translation_language", string.IsNullOrWhiteSpace(settings.DefaultTranslationLanguage) ? "中文" : settings.DefaultTranslationLanguage.Trim());
        await _repository.SetSettingAsync("standard_translation_provider", NormalizeStandardTranslationProvider(settings.StandardTranslationProvider));
        await _repository.SetSettingAsync("baidu_translate_app_id", settings.BaiduTranslateAppId.Trim());
        await _repository.SetSettingAsync("baidu_translate_secret", settings.BaiduTranslateSecret.Trim());
        await _repository.SetSettingAsync("tencent_translate_secret_id", settings.TencentTranslateSecretId.Trim());
        await _repository.SetSettingAsync("tencent_translate_secret_key", settings.TencentTranslateSecretKey.Trim());
        await _repository.SetSettingAsync("tencent_translate_region", string.IsNullOrWhiteSpace(settings.TencentTranslateRegion) ? "ap-beijing" : settings.TencentTranslateRegion.Trim());
        await _repository.SetSettingAsync("google_translate_api_key", settings.GoogleTranslateApiKey.Trim());
        await _repository.SetSettingAsync("microsoft_translate_key", settings.MicrosoftTranslateKey.Trim());
        await _repository.SetSettingAsync("microsoft_translate_region", string.IsNullOrWhiteSpace(settings.MicrosoftTranslateRegion) ? "global" : settings.MicrosoftTranslateRegion.Trim());
        await _repository.SaveAiChannelsAsync(settings.AiChannels);
    }

    private StandardTranslationSettings StandardTranslationSettingsFromRepository()
    {
        return new StandardTranslationSettings
        {
            Provider = NormalizeStandardTranslationProvider(_repository.GetSetting("standard_translation_provider", "microsoft")),
            BaiduAppId = _repository.GetSetting("baidu_translate_app_id"),
            BaiduSecret = _repository.GetSetting("baidu_translate_secret"),
            TencentSecretId = _repository.GetSetting("tencent_translate_secret_id"),
            TencentSecretKey = _repository.GetSetting("tencent_translate_secret_key"),
            TencentRegion = _repository.GetSetting("tencent_translate_region", "ap-beijing"),
            GoogleApiKey = _repository.GetSetting("google_translate_api_key"),
            MicrosoftKey = _repository.GetSetting("microsoft_translate_key"),
            MicrosoftRegion = _repository.GetSetting("microsoft_translate_region", "global")
        };
    }

    private static string NormalizeTranslationMode(string? value)
    {
        return value?.Trim().ToLowerInvariant() switch
        {
            "ai" => "ai",
            "standard" => "standard",
            _ => "off"
        };
    }

    private static string NormalizeStandardTranslationProvider(string? value)
    {
        return value?.Trim().ToLowerInvariant() switch
        {
            "baidu" => "baidu",
            "tencent" => "tencent",
            "google" => "google",
            _ => "microsoft"
        };
    }

    private bool GetBoolSetting(string key, bool defaultValue)
    {
        var raw = _repository.GetSetting(key, defaultValue ? "1" : "0");
        return raw is "1" || raw.Equals("true", StringComparison.OrdinalIgnoreCase) || raw.Equals("yes", StringComparison.OrdinalIgnoreCase);
    }

    private int SchedulerIntervalMinutes()
    {
        return int.TryParse(_repository.GetSetting("scheduler_interval_minutes", "60"), out var value)
            ? Math.Clamp(value, 5, 10080)
            : 60;
    }

    private async Task DownloadGistAsync()
    {
        var data = AskGistData(true);
        if (data is null)
        {
            return;
        }

        if (MessageBox.Show(this, "将从 Gist 下载并合并分类、订阅源和关键词订阅，不会删除本地文章。继续？", "MRSS", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
        {
            return;
        }

        SetBusy(true, "正在从 GitHub Gist 下载并合并订阅...");
        try
        {
            var changed = await _backupService.DownloadGistAsync(data.Value.Token, data.Value.GistId, data.Value.Filename, _stop.Token);
            await ReloadCurrentViewAsync();
            MessageBox.Show(this, $"已合并同步数据：{changed} 项。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        finally
        {
            SetBusy(false, "就绪");
        }
    }

    private (string Token, string GistId, string Filename)? AskGistData(bool needGistId)
    {
        var settings = LoadSettings();
        var token = settings.GithubToken;
        if (string.IsNullOrWhiteSpace(token))
        {
            token = InputDialogs.AskText(this, "MRSS", "GitHub Token（需要 gist 权限）：", "", true);
        }
        if (string.IsNullOrWhiteSpace(token))
        {
            MessageBox.Show(this, "请先在“设置”里填写 GitHub Token，或在这里临时输入。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
            return null;
        }

        var gistId = settings.GistId;
        if (needGistId && string.IsNullOrWhiteSpace(gistId))
        {
            gistId = InputDialogs.AskText(this, "MRSS", "Gist ID：", "");
        }
        if (needGistId && string.IsNullOrWhiteSpace(gistId))
        {
            MessageBox.Show(this, "恢复时必须填写 Gist ID。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return null;
        }

        var filename = string.IsNullOrWhiteSpace(settings.GistFilename) ? "mrss-subscriptions.json" : settings.GistFilename;
        if (string.IsNullOrWhiteSpace(filename))
        {
            return null;
        }

        return (token.Trim(), gistId?.Trim() ?? "", filename.Trim());
    }

    private void SetRefreshFailures(IEnumerable<RefreshFailure> failures)
    {
        _lastRefreshFailures = failures.ToList();
        NotifyCommands();
    }

    private void ShowRefreshFailures()
    {
        if (_lastRefreshFailures.Count == 0)
        {
            MessageBox.Show(this, "最近一次刷新没有失败项。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        MessageBox.Show(this, string.Join("\n\n", _lastRefreshFailures.Select(item => item.DisplayText)), "刷新失败详情", MessageBoxButton.OK, MessageBoxImage.Warning);
    }

    private static string FailureSummary(RefreshResult result)
    {
        var lines = result.Failures.Take(5).Select(item => item.DisplayText).ToList();
        if (result.Failures.Count > lines.Count)
        {
            lines.Add($"还有 {result.Failures.Count - lines.Count} 个失败项，可点“失败详情”查看。");
        }

        return string.Join("\n\n", lines);
    }

    private void SearchBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            _ = LoadArticlesAsync(false);
        }
    }

    private void ListBoxItem_PreviewMouseRightButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.OriginalSource is not DependencyObject source)
        {
            return;
        }

        var item = FindVisualParent<ListBoxItem>(source);
        if (item is null)
        {
            return;
        }

        item.Focus();
        item.IsSelected = true;
    }

    private void NavList_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (e.OriginalSource is not DependencyObject source)
        {
            return;
        }

        var item = FindVisualParent<ListBoxItem>(source);
        if (item?.DataContext is NavItem { HasChildren: true } navItem)
        {
            ToggleNavExpansion(navItem);
            e.Handled = true;
        }
    }

    private static T? FindVisualParent<T>(DependencyObject child) where T : DependencyObject
    {
        var current = child;
        while (current is not null)
        {
            if (current is T typed)
            {
                return typed;
            }

            current = System.Windows.Media.VisualTreeHelper.GetParent(current);
        }

        return null;
    }

    private static T? FindVisualChild<T>(DependencyObject parent) where T : DependencyObject
    {
        for (var i = 0; i < System.Windows.Media.VisualTreeHelper.GetChildrenCount(parent); i++)
        {
            var child = System.Windows.Media.VisualTreeHelper.GetChild(parent, i);
            if (child is T typed)
            {
                return typed;
            }

            var nested = FindVisualChild<T>(child);
            if (nested is not null)
            {
                return nested;
            }
        }

        return null;
    }

    private void SetBusy(bool busy, string status)
    {
        _isBusy = busy;
        StatusText = status;
        NotifyCommands();
    }

    private void NotifyCommands()
    {
        foreach (var command in new[] { AddFeedCommand, AddCategoryCommand, ApplyFiltersCommand, RefreshCommand, MarkAllReadCommand, LoadMoreCommand, OpenArticleCommand, ToggleFavoriteCommand, MarkUnreadCommand, ToggleOriginalCommand, EditNavCommand, RenameNavCommand, DeleteNavCommand, SettingsCommand, ShowRefreshFailuresCommand })
        {
            if (command is RelayCommand relay)
            {
                relay.NotifyCanExecuteChanged();
            }
        }
    }

    private void NotifyReader()
    {
        OnPropertyChanged(nameof(ReaderTitle));
        OnPropertyChanged(nameof(ReaderMeta));
        OnPropertyChanged(nameof(ReaderDocument));
        OnPropertyChanged(nameof(FavoriteButtonText));
        OnPropertyChanged(nameof(OriginalButtonText));
        OnPropertyChanged(nameof(HasTranslatedArticle));
        OnPropertyChanged(nameof(HasSelectedArticle));
        OnPropertyChanged(nameof(HasNoSelectedArticle));
        Dispatcher.BeginInvoke(() => FindVisualChild<ScrollViewer>(ReaderDocumentViewer)?.ScrollToHome(), DispatcherPriority.Background);
    }

    private void NotifySelectedNav()
    {
        OnPropertyChanged(nameof(SelectedNavTitle));
        OnPropertyChanged(nameof(SelectedNavDetail));
        OnPropertyChanged(nameof(EditNavButtonText));
        NotifyCommands();
    }

    private static string CountTextFor(int count)
    {
        return count == 0 ? "0 未读" : $"{count} 未读";
    }

    private bool SetField<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
        {
            return false;
        }

        field = value;
        OnPropertyChanged(propertyName);
        return true;
    }

    private void OnPropertyChanged([CallerMemberName] string? propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
