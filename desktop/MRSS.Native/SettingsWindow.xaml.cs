using System.Windows;
using System.Windows.Controls;
using MRSS.Native.Models;
using MRSS.Native.Services;

namespace MRSS.Native;

public partial class SettingsWindow : Window
{
    private readonly AiClient _aiClient;
    private bool _loadingChannel;

    public SettingsWindow(Window owner, AppSettingsView settings, List<AiChannel> channels, AiClient aiClient)
    {
        InitializeComponent();
        Owner = owner;
        Settings = settings;
        Settings.AiChannels = channels;
        _aiClient = aiClient;
        DataContext = Settings;
        Loaded += (_, _) =>
        {
            TokenBox.Password = Settings.GithubToken;
            BaiduSecretBox.Password = Settings.BaiduTranslateSecret;
            TencentSecretKeyBox.Password = Settings.TencentTranslateSecretKey;
            SelectComboByTag(DefaultTranslationModeBox, Settings.DefaultTranslationMode, "off");
            SelectComboByTag(StandardProviderBox, Settings.StandardTranslationProvider, "microsoft");
            AiChannelList.ItemsSource = Settings.AiChannels;
            if (Settings.AiChannels.Count > 0)
            {
                AiChannelList.SelectedIndex = 0;
            }
            else
            {
                SelectProvider("openai");
                UpdateProviderUi();
            }
        };
    }

    public AppSettingsView Settings { get; }

    private void TokenBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        Settings.GithubToken = TokenBox.Password;
    }

    private void BaiduSecretBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        Settings.BaiduTranslateSecret = BaiduSecretBox.Password;
    }

    private void TencentSecretKeyBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        Settings.TencentTranslateSecretKey = TencentSecretKeyBox.Password;
    }

    private void AddAiChannel_Click(object sender, RoutedEventArgs e)
    {
        var channel = new AiChannel
        {
            Name = "OpenAI 官方",
            Provider = "openai",
            BaseUrl = "",
            IsDefault = Settings.AiChannels.Count == 0
        };
        Settings.AiChannels.Add(channel);
        AiChannelList.Items.Refresh();
        AiChannelList.SelectedItem = channel;
    }

    private void DeleteAiChannel_Click(object sender, RoutedEventArgs e)
    {
        if (AiChannelList.SelectedItem is not AiChannel channel)
        {
            return;
        }

        Settings.AiChannels.Remove(channel);
        if (channel.IsDefault && Settings.AiChannels.Count > 0)
        {
            Settings.AiChannels[0].IsDefault = true;
        }

        AiChannelList.Items.Refresh();
        AiChannelList.SelectedIndex = Settings.AiChannels.Count > 0 ? 0 : -1;
    }

    private void DefaultAiChannel_Click(object sender, RoutedEventArgs e)
    {
        if (AiChannelList.SelectedItem is not AiChannel channel)
        {
            return;
        }

        foreach (var item in Settings.AiChannels)
        {
            item.IsDefault = ReferenceEquals(item, channel);
        }

        AiChannelList.Items.Refresh();
    }

    private async void FetchModels_Click(object sender, RoutedEventArgs e)
    {
        AiModelStatus.Text = "准备拉取模型...";
        var channel = EnsureCurrentChannelFromForm(createIfMissing: true);
        if (channel is null)
        {
            AiModelStatus.Text = "请先新增渠道，或在右侧填写渠道名称和 API Key。";
            MessageBox.Show(this, "请先新增渠道，或在右侧填写渠道名称和 API Key。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        if (string.IsNullOrWhiteSpace(channel.Name))
        {
            AiModelStatus.Text = "请先填写渠道名称。";
            MessageBox.Show(this, "请先填写渠道名称。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        if (string.IsNullOrWhiteSpace(channel.ApiKey))
        {
            AiModelStatus.Text = "请先填写 API Key。";
            MessageBox.Show(this, "请先填写 API Key。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        if (channel.RequiresBaseUrl && string.IsNullOrWhiteSpace(channel.BaseUrl))
        {
            AiModelStatus.Text = "OpenAI 兼容渠道需要填写 Base URL。";
            MessageBox.Show(this, "OpenAI 兼容渠道需要填写 Base URL。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        try
        {
            FetchModels_Click_ButtonState(false);
            AiModelStatus.Text = "正在拉取模型...";
            var models = await _aiClient.FetchModelsAsync(channel);
            AiModelBox.ItemsSource = models;
            if (models.Count == 0)
            {
                AiModelStatus.Text = "拉取完成，但没有返回可用模型。";
                MessageBox.Show(this, "拉取完成，但没有返回可用模型。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            if (string.IsNullOrWhiteSpace(channel.Model) || !models.Contains(channel.Model))
            {
                channel.Model = models[0];
                AiModelBox.Text = channel.Model;
            }

            AiModelStatus.Text = $"拉取成功：{models.Count} 个模型，当前选择 {channel.Model}。";
            MessageBox.Show(this, $"已拉取 {models.Count} 个模型。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            AiModelStatus.Text = $"拉取失败：{ex.Message}";
            MessageBox.Show(this, ex.Message, "拉取模型失败", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
        finally
        {
            FetchModels_Click_ButtonState(true);
        }
    }

    private void AiChannelList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (AiChannelList.SelectedItem is not AiChannel channel)
        {
            _loadingChannel = true;
            AiNameBox.Text = "";
            AiBaseUrlBox.Text = "";
            AiKeyBox.Password = "";
            AiModelBox.Text = "";
            AiModelStatus.Text = "";
            UpdateProviderUi();
            _loadingChannel = false;
            return;
        }

        _loadingChannel = true;
        AiNameBox.Text = channel.Name;
        SelectProvider(channel.Provider);
        AiBaseUrlBox.Text = channel.BaseUrl;
        AiKeyBox.Password = channel.ApiKey;
        AiModelBox.Text = channel.Model;
        AiModelStatus.Text = string.IsNullOrWhiteSpace(channel.Model) ? "还没有选择模型，填写 Key 后点击拉取。" : $"当前模型：{channel.Model}";
        UpdateProviderUi();
        _loadingChannel = false;
    }

    private void AiFieldChanged(object sender, EventArgs e)
    {
        SaveCurrentChannel();
    }

    private void AiProviderBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateProviderUi();
        SaveCurrentChannel();
    }

    private void AiKeyBox_PasswordChanged(object sender, RoutedEventArgs e)
    {
        SaveCurrentChannel();
    }

    private void SaveCurrentChannel()
    {
        if (_loadingChannel || AiChannelList.SelectedItem is not AiChannel channel)
        {
            return;
        }

        ApplyFormToChannel(channel);
    }

    private AiChannel? EnsureCurrentChannelFromForm(bool createIfMissing)
    {
        if (AiChannelList.SelectedItem is AiChannel selected)
        {
            ApplyFormToChannel(selected);
            return selected;
        }

        if (!createIfMissing || !HasChannelFormInput())
        {
            return null;
        }

        var channel = new AiChannel
        {
            IsDefault = Settings.AiChannels.All(item => !item.IsDefault)
        };
        ApplyFormToChannel(channel);
        Settings.AiChannels.Add(channel);
        AiChannelList.Items.Refresh();
        AiChannelList.SelectedItem = channel;
        AiModelStatus.Text = "已自动把右侧配置保存为新渠道，正在拉取模型...";
        return channel;
    }

    private void ApplyFormToChannel(AiChannel channel)
    {
        var provider = SelectedProvider();
        channel.Provider = provider;
        channel.Name = string.IsNullOrWhiteSpace(AiNameBox.Text) ? DefaultChannelName(provider) : AiNameBox.Text.Trim();
        channel.BaseUrl = channel.RequiresBaseUrl ? AiBaseUrlBox.Text.Trim() : "";
        channel.ApiKey = AiKeyBox.Password.Trim();
        channel.Model = AiModelBox.Text.Trim();
    }

    private bool HasChannelFormInput()
    {
        return !string.IsNullOrWhiteSpace(AiNameBox.Text)
               || !string.IsNullOrWhiteSpace(AiKeyBox.Password)
               || !string.IsNullOrWhiteSpace(AiBaseUrlBox.Text)
               || !string.IsNullOrWhiteSpace(AiModelBox.Text);
    }

    private static string DefaultChannelName(string provider)
    {
        return provider switch
        {
            "gemini" => "Gemini 官方",
            "qwen" => "通义千问",
            "doubao" => "豆包",
            "deepseek" => "DeepSeek",
            "kimi" => "Kimi",
            "zhipu" => "智谱",
            "openai_compatible" => "OpenAI 兼容",
            _ => "OpenAI 官方"
        };
    }

    private string SelectedProvider()
    {
        if (AiProviderBox.SelectedItem is ComboBoxItem item && item.Tag is string provider)
        {
            return provider;
        }

        return "openai";
    }

    private void UpdateProviderUi()
    {
        var provider = SelectedProvider();
        var needsBaseUrl = provider == "openai_compatible";
        AiBaseUrlLabel.Visibility = needsBaseUrl ? Visibility.Visible : Visibility.Collapsed;
        AiBaseUrlBox.Visibility = needsBaseUrl ? Visibility.Visible : Visibility.Collapsed;
        if (!needsBaseUrl)
        {
            AiBaseUrlBox.Text = "";
        }

        AiProviderHint.Text = provider switch
        {
            "gemini" => "Gemini 官方渠道使用 Google 官方地址，只需要填写 Gemini API Key，然后点击拉取模型。",
            "qwen" => "通义千问使用阿里云 DashScope OpenAI 兼容地址，只需要填写 DashScope API Key。",
            "doubao" => "豆包使用火山方舟 OpenAI 兼容地址。模型通常是方舟控制台创建的接入点 ID，可直接填到模型框。",
            "deepseek" => "DeepSeek 官方渠道已内置 API 地址，只需要填写 DeepSeek API Key。",
            "kimi" => "Kimi 使用 Moonshot 官方 OpenAI 兼容地址，只需要填写 Moonshot API Key。",
            "zhipu" => "智谱使用 BigModel 官方 OpenAI 兼容地址，只需要填写智谱 API Key。",
            "openai_compatible" => "OpenAI 兼容渠道用于第三方中转站，需要填写完整 Base URL，例如 https://example.com/v1，再填写 Key 拉取模型。",
            _ => "OpenAI 官方渠道内置 https://api.openai.com/v1，只需要填写 OpenAI API Key，然后点击拉取模型。"
        };
    }

    private void FetchModels_Click_ButtonState(bool enabled)
    {
        Cursor = enabled ? null : System.Windows.Input.Cursors.Wait;
        FetchModelsButton.IsEnabled = enabled;
        FetchModelsButton.Content = enabled ? "拉取" : "拉取中";
    }

    private void SelectProvider(string provider)
    {
        SelectComboByTag(AiProviderBox, provider, "openai");
    }

    private static void SelectComboByTag(ComboBox comboBox, string? value, string fallback)
    {
        foreach (ComboBoxItem item in comboBox.Items)
        {
            if (item.Tag is string tag && tag.Equals(value, StringComparison.OrdinalIgnoreCase))
            {
                comboBox.SelectedItem = item;
                return;
            }
        }

        foreach (ComboBoxItem item in comboBox.Items)
        {
            if (item.Tag is string tag && tag.Equals(fallback, StringComparison.OrdinalIgnoreCase))
            {
                comboBox.SelectedItem = item;
                return;
            }
        }

        comboBox.SelectedIndex = comboBox.Items.Count > 0 ? 0 : -1;
    }

    private static string SelectedTag(ComboBox comboBox, string fallback)
    {
        return comboBox.SelectedItem is ComboBoxItem item && item.Tag is string tag ? tag : fallback;
    }

    private void Cancel_Click(object sender, RoutedEventArgs e)
    {
        DialogResult = false;
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        if (AiChannelList.SelectedItem is not AiChannel && HasChannelFormInput())
        {
            EnsureCurrentChannelFromForm(createIfMissing: true);
        }
        else
        {
            SaveCurrentChannel();
        }

        if (Settings.StartupRefreshMinutes < 5 || Settings.StartupRefreshMinutes > 10080)
        {
            MessageBox.Show(this, "后台刷新间隔请输入 5 到 10080 分钟。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        if (string.IsNullOrWhiteSpace(Settings.GistFilename))
        {
            MessageBox.Show(this, "Gist 文件名不能为空。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        foreach (var channel in Settings.AiChannels)
        {
            if (string.IsNullOrWhiteSpace(channel.Name))
            {
                MessageBox.Show(this, "AI 渠道名称不能为空。", "MRSS", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
        }

        Settings.DefaultTranslationMode = SelectedTag(DefaultTranslationModeBox, "off");
        Settings.StandardTranslationProvider = SelectedTag(StandardProviderBox, "microsoft");
        DialogResult = true;
    }
}
