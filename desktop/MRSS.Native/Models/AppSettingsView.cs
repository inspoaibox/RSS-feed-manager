namespace MRSS.Native.Models;

public sealed class AppSettingsView
{
    public string GithubToken { get; set; } = "";
    public string GistId { get; set; } = "";
    public string GistFilename { get; set; } = "mrss-subscriptions.json";
    public int StartupRefreshMinutes { get; set; } = 60;
    public bool RefreshOnStartup { get; set; } = true;
    public string DefaultTranslationLanguage { get; set; } = "中文";
    public List<AiChannel> AiChannels { get; set; } = [];
}
