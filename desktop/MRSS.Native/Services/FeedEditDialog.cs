using System.Windows;
using System.Windows.Controls;
using MRSS.Native.Models;

namespace MRSS.Native.Services;

public sealed class FeedEditResult
{
    public string Title { get; init; } = "";
    public int? CategoryId { get; init; }
    public int FetchIntervalMinutes { get; init; }
    public bool IsActive { get; init; }
    public bool TranslateEnabled { get; init; }
    public string TranslationLanguage { get; init; } = "中文";
}

public static class FeedEditDialog
{
    public static FeedEditResult? Show(Window owner, Feed feed, IReadOnlyList<Category> categories)
    {
        var window = new Window
        {
            Owner = owner,
            Title = "编辑订阅",
            Width = 480,
            MinHeight = 360,
            SizeToContent = SizeToContent.Height,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            ResizeMode = ResizeMode.CanResize,
            Background = System.Windows.Media.Brushes.White,
            ShowInTaskbar = false
        };

        var root = new Grid { Margin = new Thickness(18) };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var title = new TextBox { Text = feed.Title, Height = 36 };
        AddField(root, 0, "订阅名称", title);

        var url = new TextBox { Text = feed.Url, Height = 36, IsReadOnly = true };
        AddField(root, 1, "RSS 链接（不可在此修改）", url);

        var categoryBox = new ComboBox { Height = 36, DisplayMemberPath = "Name" };
        var options = new List<Category> { new() { Id = 0, Name = "未分类" } };
        options.AddRange(categories);
        categoryBox.ItemsSource = options;
        categoryBox.SelectedItem = options.FirstOrDefault(item => feed.CategoryId is null ? item.Id == 0 : item.Id == feed.CategoryId.Value) ?? options[0];
        AddField(root, 2, "分类", categoryBox);

        var interval = new TextBox { Text = Math.Max(5, feed.FetchInterval / 60).ToString(), Height = 36 };
        AddField(root, 3, "同步间隔（分钟）", interval);

        var active = new CheckBox { Content = "启用这个订阅源", IsChecked = feed.IsActive, Margin = new Thickness(0, 2, 0, 2) };
        Grid.SetRow(active, 4);
        root.Children.Add(active);

        var translateGrid = new Grid();
        translateGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        translateGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var translate = new CheckBox { Content = "自动 AI 翻译", IsChecked = feed.TranslateEnabled, VerticalAlignment = VerticalAlignment.Center };
        translateGrid.Children.Add(translate);
        var language = new TextBox { Text = string.IsNullOrWhiteSpace(feed.TranslationLanguage) ? "中文" : feed.TranslationLanguage, Height = 36, Margin = new Thickness(16, 0, 0, 0) };
        Grid.SetColumn(language, 1);
        translateGrid.Children.Add(language);
        AddField(root, 5, "翻译", translateGrid);

        var buttons = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 10, 0, 0)
        };
        var cancel = new Button { Content = "取消", Width = 82, Height = 34, Margin = new Thickness(0, 0, 8, 0), Style = (Style)Application.Current.Resources["GhostButton"] };
        cancel.Click += (_, _) => window.DialogResult = false;
        var ok = new Button { Content = "保存", Width = 82, Height = 34, IsDefault = true };
        ok.Click += (_, _) =>
        {
            if (string.IsNullOrWhiteSpace(title.Text))
            {
                MessageBox.Show(window, "订阅名称不能为空。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            if (!int.TryParse(interval.Text.Trim(), out var minutes) || minutes < 5 || minutes > 10080)
            {
                MessageBox.Show(window, "同步间隔请输入 5 到 10080 之间的分钟数。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            var selected = (Category)categoryBox.SelectedItem;
            window.Tag = new FeedEditResult
            {
                Title = title.Text.Trim(),
                CategoryId = selected.Id <= 0 ? null : selected.Id,
                FetchIntervalMinutes = minutes,
                IsActive = active.IsChecked == true,
                TranslateEnabled = translate.IsChecked == true,
                TranslationLanguage = string.IsNullOrWhiteSpace(language.Text) ? "中文" : language.Text.Trim()
            };
            window.DialogResult = true;
        };
        buttons.Children.Add(cancel);
        buttons.Children.Add(ok);
        Grid.SetRow(buttons, 6);
        root.Children.Add(buttons);

        window.Content = root;
        window.Loaded += (_, _) => title.Focus();
        return window.ShowDialog() == true ? (FeedEditResult?)window.Tag : null;
    }

    private static void AddField(Grid root, int row, string label, FrameworkElement control)
    {
        var box = new StackPanel { Margin = new Thickness(0, 0, 0, 8) };
        box.Children.Add(new TextBlock
        {
            Text = label,
            FontSize = 13,
            FontWeight = FontWeights.SemiBold,
            Margin = new Thickness(0, 0, 0, 6)
        });
        box.Children.Add(control);
        Grid.SetRow(box, row);
        root.Children.Add(box);
    }
}
