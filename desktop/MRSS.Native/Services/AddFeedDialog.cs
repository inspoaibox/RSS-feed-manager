using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using MRSS.Native.Models;

namespace MRSS.Native.Services;

public sealed class AddFeedResult
{
    public string Url { get; init; } = "";
    public int? CategoryId { get; init; }
    public int FetchIntervalMinutes { get; init; }
    public bool TranslateEnabled { get; init; }
    public string TranslationLanguage { get; init; } = "中文";
}

public static class AddFeedDialog
{
    public static AddFeedResult? Show(Window owner, IReadOnlyList<Category> categories, int? defaultCategoryId, string defaultLanguage)
    {
        var window = new Window
        {
            Owner = owner,
            Title = "添加订阅",
            Width = 520,
            MinWidth = 480,
            SizeToContent = SizeToContent.Height,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            ResizeMode = ResizeMode.NoResize,
            Background = System.Windows.Media.Brushes.White,
            ShowInTaskbar = false
        };

        var root = new Grid { Margin = new Thickness(20) };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var title = new TextBlock
        {
            Text = "添加订阅",
            FontSize = 20,
            FontWeight = FontWeights.Bold,
            Margin = new Thickness(0, 0, 0, 14)
        };
        Grid.SetRow(title, 0);
        root.Children.Add(title);

        var url = new TextBox { Height = 36 };
        AddField(root, 1, "RSS / Atom 链接", url);

        var categoryBox = new ComboBox { Height = 36, DisplayMemberPath = nameof(CategoryOption.Name) };
        var options = new List<CategoryOption> { new(null, "未分类") };
        options.AddRange(categories.Select(category => new CategoryOption(category.Id, category.Name)));
        categoryBox.ItemsSource = options;
        categoryBox.SelectedItem = options.FirstOrDefault(item => item.Id == defaultCategoryId) ?? options[0];
        AddField(root, 2, "分类", categoryBox);

        var intervalGrid = new Grid();
        intervalGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
        intervalGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var interval = new TextBox { Text = "60", Height = 36, VerticalContentAlignment = VerticalAlignment.Center };
        intervalGrid.Children.Add(interval);
        var unit = new TextBlock
        {
            Text = "分钟",
            Foreground = (System.Windows.Media.Brush)Application.Current.Resources["MutedBrush"],
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(10, 0, 0, 0)
        };
        Grid.SetColumn(unit, 1);
        intervalGrid.Children.Add(unit);
        AddField(root, 3, "同步间隔", intervalGrid);

        var translateGrid = new Grid();
        translateGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        translateGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var translate = new CheckBox { Content = "自动 AI 翻译", VerticalAlignment = VerticalAlignment.Center };
        translateGrid.Children.Add(translate);
        var language = new TextBox { Text = string.IsNullOrWhiteSpace(defaultLanguage) ? "中文" : defaultLanguage.Trim(), Height = 36, Margin = new Thickness(16, 0, 0, 0) };
        Grid.SetColumn(language, 1);
        translateGrid.Children.Add(language);
        AddField(root, 4, "翻译", translateGrid);

        var buttons = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 8, 0, 0)
        };
        var cancel = new Button
        {
            Content = "取消",
            Width = 84,
            Height = 34,
            Margin = new Thickness(0, 0, 8, 0),
            Style = (Style)Application.Current.Resources["GhostButton"],
            IsCancel = true
        };
        cancel.Click += (_, _) => window.DialogResult = false;
        var ok = new Button { Content = "添加", Width = 84, Height = 34, IsDefault = true };
        ok.Click += (_, _) =>
        {
            var rawUrl = url.Text.Trim();
            if (!Uri.TryCreate(rawUrl, UriKind.Absolute, out var uri) || uri.Scheme is not ("http" or "https"))
            {
                MessageBox.Show(window, "请输入有效的 RSS/Atom 链接。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            if (!int.TryParse(interval.Text.Trim(), out var minutes) || minutes < 5 || minutes > 10080)
            {
                MessageBox.Show(window, "同步间隔请输入 5 到 10080 之间的分钟数。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }

            var selected = (CategoryOption?)categoryBox.SelectedItem;
            window.Tag = new AddFeedResult
            {
                Url = rawUrl,
                CategoryId = selected?.Id,
                FetchIntervalMinutes = minutes,
                TranslateEnabled = translate.IsChecked == true,
                TranslationLanguage = string.IsNullOrWhiteSpace(language.Text) ? "中文" : language.Text.Trim()
            };
            window.DialogResult = true;
        };
        buttons.Children.Add(cancel);
        buttons.Children.Add(ok);
        Grid.SetRow(buttons, 5);
        root.Children.Add(buttons);

        root.InputBindings.Add(new KeyBinding(new RelayCommand(() => window.DialogResult = false), Key.Escape, ModifierKeys.None));
        window.Content = root;
        window.Loaded += (_, _) => url.Focus();
        return window.ShowDialog() == true ? (AddFeedResult?)window.Tag : null;
    }

    private static void AddField(Grid root, int row, string label, FrameworkElement control)
    {
        var box = new StackPanel { Margin = new Thickness(0, 0, 0, 12) };
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

    private sealed record CategoryOption(int? Id, string Name);
}
