using System.Globalization;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using MRSS.Native.Models;

namespace MRSS.Native.Services;

public sealed class StandardTranslationClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private static readonly Regex HtmlTagRegex = new("(?s)<[^>]+>", RegexOptions.Compiled);
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(45) };

    public async Task<ArticleTranslation> TranslateAsync(StandardTranslationSettings settings, TranslationJob job, CancellationToken cancellationToken = default)
    {
        var title = await TranslateTextPreservingFormatAsync(settings, job.Title, job.TargetLanguage, cancellationToken);
        var content = await TranslateTextPreservingFormatAsync(settings, job.Content, job.TargetLanguage, cancellationToken);
        return new ArticleTranslation { Title = title, Content = content };
    }

    private async Task<string> TranslateTextPreservingFormatAsync(StandardTranslationSettings settings, string? source, string targetLanguage, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            return source ?? "";
        }

        if (!LooksLikeHtml(source))
        {
            return await TranslatePlainAsync(settings, source, targetLanguage, cancellationToken);
        }

        var builder = new StringBuilder(source.Length);
        var index = 0;
        foreach (Match match in HtmlTagRegex.Matches(source))
        {
            if (match.Index > index)
            {
                var text = source[index..match.Index];
                builder.Append(await TranslateTextPartAsync(settings, text, targetLanguage, cancellationToken));
            }

            builder.Append(match.Value);
            index = match.Index + match.Length;
        }

        if (index < source.Length)
        {
            builder.Append(await TranslateTextPartAsync(settings, source[index..], targetLanguage, cancellationToken));
        }

        return builder.ToString();
    }

    private async Task<string> TranslateTextPartAsync(StandardTranslationSettings settings, string text, string targetLanguage, CancellationToken cancellationToken)
    {
        return string.IsNullOrWhiteSpace(text)
            ? text
            : await TranslatePlainAsync(settings, text, targetLanguage, cancellationToken);
    }

    private Task<string> TranslatePlainAsync(StandardTranslationSettings settings, string source, string targetLanguage, CancellationToken cancellationToken)
    {
        return NormalizeProvider(settings.Provider) switch
        {
            "baidu" => TranslateBaiduAsync(settings, source, targetLanguage, cancellationToken),
            "tencent" => TranslateTencentAsync(settings, source, targetLanguage, cancellationToken),
            "google" => TranslateGoogleAsync(settings, source, targetLanguage, cancellationToken),
            _ => TranslateMicrosoftAsync(settings, source, targetLanguage, cancellationToken)
        };
    }

    private async Task<string> TranslateBaiduAsync(StandardTranslationSettings settings, string source, string targetLanguage, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(settings.BaiduAppId) || string.IsNullOrWhiteSpace(settings.BaiduSecret))
        {
            throw new InvalidOperationException("请先填写百度翻译 App ID 和密钥。");
        }

        var salt = RandomNumberGenerator.GetInt32(100000, 999999).ToString(CultureInfo.InvariantCulture);
        var sign = Md5Hex(settings.BaiduAppId + source + salt + settings.BaiduSecret);
        var form = new Dictionary<string, string>
        {
            ["q"] = source,
            ["from"] = "auto",
            ["to"] = LanguageForBaidu(targetLanguage),
            ["appid"] = settings.BaiduAppId.Trim(),
            ["salt"] = salt,
            ["sign"] = sign
        };
        using var response = await _httpClient.PostAsync("https://fanyi-api.baidu.com/api/trans/vip/translate", new FormUrlEncodedContent(form), cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        if (document.RootElement.TryGetProperty("error_msg", out var error))
        {
            throw new InvalidOperationException(error.GetString() ?? "百度翻译失败。");
        }

        return string.Join("", document.RootElement.GetProperty("trans_result").EnumerateArray().Select(item => item.GetProperty("dst").GetString() ?? ""));
    }

    private async Task<string> TranslateGoogleAsync(StandardTranslationSettings settings, string source, string targetLanguage, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(settings.GoogleApiKey))
        {
            throw new InvalidOperationException("请先填写 Google 翻译 API Key。");
        }

        var payload = new
        {
            q = source,
            target = LanguageForGoogle(targetLanguage),
            format = "text"
        };
        var uri = $"https://translation.googleapis.com/language/translate/v2?key={Uri.EscapeDataString(settings.GoogleApiKey.Trim())}";
        using var response = await _httpClient.PostAsync(uri, JsonContent(payload), cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        return document.RootElement.GetProperty("data").GetProperty("translations")[0].GetProperty("translatedText").GetString() ?? "";
    }

    private async Task<string> TranslateMicrosoftAsync(StandardTranslationSettings settings, string source, string targetLanguage, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(settings.MicrosoftKey))
        {
            throw new InvalidOperationException("请先填写微软翻译 Key。");
        }

        var payload = new[] { new { Text = source } };
        var uri = $"https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to={Uri.EscapeDataString(LanguageForMicrosoft(targetLanguage))}";
        using var request = new HttpRequestMessage(HttpMethod.Post, uri);
        request.Content = JsonContent(payload);
        request.Headers.TryAddWithoutValidation("Ocp-Apim-Subscription-Key", settings.MicrosoftKey.Trim());
        if (!string.IsNullOrWhiteSpace(settings.MicrosoftRegion) && !settings.MicrosoftRegion.Equals("global", StringComparison.OrdinalIgnoreCase))
        {
            request.Headers.TryAddWithoutValidation("Ocp-Apim-Subscription-Region", settings.MicrosoftRegion.Trim());
        }

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        return document.RootElement[0].GetProperty("translations")[0].GetProperty("text").GetString() ?? "";
    }

    private async Task<string> TranslateTencentAsync(StandardTranslationSettings settings, string source, string targetLanguage, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(settings.TencentSecretId) || string.IsNullOrWhiteSpace(settings.TencentSecretKey))
        {
            throw new InvalidOperationException("请先填写腾讯翻译 SecretId 和 SecretKey。");
        }

        const string host = "tmt.tencentcloudapi.com";
        const string service = "tmt";
        const string action = "TextTranslate";
        const string version = "2018-03-21";
        var region = string.IsNullOrWhiteSpace(settings.TencentRegion) ? "ap-beijing" : settings.TencentRegion.Trim();
        var timestamp = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        var date = DateTimeOffset.FromUnixTimeSeconds(timestamp).UtcDateTime.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        var payload = JsonSerializer.Serialize(new
        {
            SourceText = source,
            Source = "auto",
            Target = LanguageForTencent(targetLanguage),
            ProjectId = 0
        }, JsonOptions);

        var hashedPayload = Sha256Hex(payload);
        var canonicalHeaders = $"content-type:application/json; charset=utf-8\nhost:{host}\n";
        const string signedHeaders = "content-type;host";
        var canonicalRequest = $"POST\n/\n\n{canonicalHeaders}\n{signedHeaders}\n{hashedPayload}";
        var credentialScope = $"{date}/{service}/tc3_request";
        var stringToSign = $"TC3-HMAC-SHA256\n{timestamp}\n{credentialScope}\n{Sha256Hex(canonicalRequest)}";
        var secretDate = HmacSha256(Encoding.UTF8.GetBytes("TC3" + settings.TencentSecretKey.Trim()), date);
        var secretService = HmacSha256(secretDate, service);
        var secretSigning = HmacSha256(secretService, "tc3_request");
        var signature = ToHex(HmacSha256(secretSigning, stringToSign));
        var authorization = $"TC3-HMAC-SHA256 Credential={settings.TencentSecretId.Trim()}/{credentialScope}, SignedHeaders={signedHeaders}, Signature={signature}";

        using var request = new HttpRequestMessage(HttpMethod.Post, $"https://{host}");
        request.Content = new StringContent(payload, Encoding.UTF8, "application/json");
        request.Content.Headers.ContentType!.CharSet = "utf-8";
        request.Headers.TryAddWithoutValidation("Authorization", authorization);
        request.Headers.TryAddWithoutValidation("Host", host);
        request.Headers.TryAddWithoutValidation("X-TC-Action", action);
        request.Headers.TryAddWithoutValidation("X-TC-Timestamp", timestamp.ToString(CultureInfo.InvariantCulture));
        request.Headers.TryAddWithoutValidation("X-TC-Version", version);
        request.Headers.TryAddWithoutValidation("X-TC-Region", region);
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        var root = document.RootElement.GetProperty("Response");
        if (root.TryGetProperty("Error", out var error))
        {
            throw new InvalidOperationException(error.GetProperty("Message").GetString() ?? "腾讯翻译失败。");
        }

        return root.GetProperty("TargetText").GetString() ?? "";
    }

    private static bool LooksLikeHtml(string value)
    {
        return value.Contains('<') && value.Contains('>') && HtmlTagRegex.IsMatch(value);
    }

    private static StringContent JsonContent(object value)
    {
        return new StringContent(JsonSerializer.Serialize(value, JsonOptions), Encoding.UTF8, "application/json");
    }

    private static void EnsureSuccess(HttpResponseMessage response, string text)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        throw new InvalidOperationException($"翻译请求失败 HTTP {(int)response.StatusCode}：{text}");
    }

    private static string NormalizeProvider(string? provider)
    {
        return provider?.Trim().ToLowerInvariant() switch
        {
            "baidu" => "baidu",
            "tencent" => "tencent",
            "google" => "google",
            _ => "microsoft"
        };
    }

    private static string LanguageForBaidu(string language)
    {
        return NormalizeLanguage(language) switch
        {
            "en" => "en",
            "ja" => "jp",
            "ko" => "kor",
            "fr" => "fra",
            "es" => "spa",
            "ru" => "ru",
            "de" => "de",
            "zh-hant" => "cht",
            _ => "zh"
        };
    }

    private static string LanguageForTencent(string language)
    {
        return NormalizeLanguage(language) switch
        {
            "zh-hant" => "zh-TW",
            "zh" => "zh",
            var value => value
        };
    }

    private static string LanguageForGoogle(string language)
    {
        return NormalizeLanguage(language) switch
        {
            "zh-hant" => "zh-TW",
            "zh" => "zh-CN",
            var value => value
        };
    }

    private static string LanguageForMicrosoft(string language)
    {
        return NormalizeLanguage(language) switch
        {
            "zh-hant" => "zh-Hant",
            "zh" => "zh-Hans",
            var value => value
        };
    }

    private static string NormalizeLanguage(string language)
    {
        var value = language.Trim().ToLowerInvariant();
        return value switch
        {
            "中文" or "简体中文" or "chinese" or "zh-cn" or "zh_hans" or "zh-hans" => "zh",
            "繁体中文" or "zh-tw" or "zh_hant" or "zh-hant" => "zh-hant",
            "英文" or "英语" or "english" => "en",
            "日文" or "日语" or "japanese" => "ja",
            "韩文" or "韩语" or "korean" => "ko",
            "法文" or "法语" or "french" => "fr",
            "西班牙文" or "西班牙语" or "spanish" => "es",
            "俄文" or "俄语" or "russian" => "ru",
            "德文" or "德语" or "german" => "de",
            _ => string.IsNullOrWhiteSpace(value) ? "zh" : value
        };
    }

    private static string Md5Hex(string value)
    {
        return ToHex(MD5.HashData(Encoding.UTF8.GetBytes(value)));
    }

    private static string Sha256Hex(string value)
    {
        return ToHex(SHA256.HashData(Encoding.UTF8.GetBytes(value)));
    }

    private static byte[] HmacSha256(byte[] key, string value)
    {
        using var hmac = new HMACSHA256(key);
        return hmac.ComputeHash(Encoding.UTF8.GetBytes(value));
    }

    private static string ToHex(byte[] bytes)
    {
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}
