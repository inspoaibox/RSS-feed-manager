namespace MRSS.Native.Models;

public sealed class StandardTranslationSettings
{
    public string Provider { get; set; } = "microsoft";
    public string BaiduAppId { get; set; } = "";
    public string BaiduSecret { get; set; } = "";
    public string TencentSecretId { get; set; } = "";
    public string TencentSecretKey { get; set; } = "";
    public string TencentRegion { get; set; } = "ap-beijing";
    public string GoogleApiKey { get; set; } = "";
    public string MicrosoftKey { get; set; } = "";
    public string MicrosoftRegion { get; set; } = "global";
}
