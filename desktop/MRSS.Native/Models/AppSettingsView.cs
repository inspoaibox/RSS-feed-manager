namespace MRSS.Native.Models;

public sealed class AppSettingsView
{
    public string GithubToken { get; set; } = "";
    public string GistId { get; set; } = "";
    public string GistFilename { get; set; } = "mrss-subscriptions.json";
    public int StartupRefreshMinutes { get; set; } = 60;
    public bool RefreshOnStartup { get; set; } = true;
    public string DefaultTranslationMode { get; set; } = "off";
    public string DefaultTranslationLanguage { get; set; } = "中文";
    public string StandardTranslationProvider { get; set; } = "microsoft";
    public string BaiduTranslateAppId { get; set; } = "";
    public string BaiduTranslateSecret { get; set; } = "";
    public string TencentTranslateSecretId { get; set; } = "";
    public string TencentTranslateSecretKey { get; set; } = "";
    public string TencentTranslateRegion { get; set; } = "ap-beijing";
    public string GoogleTranslateApiKey { get; set; } = "";
    public string MicrosoftTranslateKey { get; set; } = "";
    public string MicrosoftTranslateRegion { get; set; } = "global";
    public List<AiChannel> AiChannels { get; set; } = [];
}
