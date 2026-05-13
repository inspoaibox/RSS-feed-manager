using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using MRSS.Native.Models;

namespace MRSS.Native.Services;

public sealed class AiClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private static readonly string[] GeminiFallbackModels = ["gemini-pro", "gemini-pro-vision", "gemini-1.5-flash", "gemini-1.5-pro"];
    private static readonly Dictionary<string, string[]> OpenAiFallbackModels = new(StringComparer.OrdinalIgnoreCase)
    {
        ["qwen"] = ["qwen-turbo", "qwen-plus", "qwen-max"],
        ["doubao"] = ["请填写火山方舟接入点 ID"],
        ["deepseek"] = ["deepseek-chat", "deepseek-reasoner"],
        ["kimi"] = ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        ["zhipu"] = ["glm-4-flash", "glm-4-plus"]
    };
    private readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(60) };

    public async Task<List<string>> FetchModelsAsync(AiChannel channel, CancellationToken cancellationToken = default)
    {
        return channel.Provider == "gemini"
            ? await FetchGeminiModelsAsync(channel, cancellationToken)
            : await FetchOpenAiModelsAsync(channel, cancellationToken);
    }

    public async Task<ArticleTranslation> TranslateAsync(AiChannel channel, TranslationJob job, CancellationToken cancellationToken = default)
    {
        return channel.Provider == "gemini"
            ? await TranslateGeminiAsync(channel, job, cancellationToken)
            : await TranslateOpenAiAsync(channel, job, cancellationToken);
    }

    private async Task<List<string>> FetchOpenAiModelsAsync(AiChannel channel, CancellationToken cancellationToken)
    {
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, CombineUrl(OpenAiBaseUrl(channel), "models"));
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", CleanApiKey(channel.ApiKey));
            using var response = await _httpClient.SendAsync(request, cancellationToken);
            var text = await response.Content.ReadAsStringAsync(cancellationToken);
            EnsureSuccess(response, text);
            using var document = JsonDocument.Parse(text);
            var models = document.RootElement.GetProperty("data")
                .EnumerateArray()
                .Select(item => item.GetProperty("id").GetString())
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Select(item => item!)
                .Where(IsUsableOpenAiChatModel)
                .OrderBy(item => item, StringComparer.OrdinalIgnoreCase)
                .ToList();
            if (models.Count > 0)
            {
                return models;
            }
        }
        catch when (OpenAiFallbackModels.ContainsKey(channel.Provider))
        {
            return OpenAiFallbackModels[channel.Provider].ToList();
        }

        return OpenAiFallbackModels.TryGetValue(channel.Provider, out var fallback) ? fallback.ToList() : [];
    }

    private async Task<List<string>> FetchGeminiModelsAsync(AiChannel channel, CancellationToken cancellationToken)
    {
        try
        {
            var url = $"{CombineUrl(GeminiBaseUrl(channel), "models")}?key={Uri.EscapeDataString(CleanApiKey(channel.ApiKey))}";
            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            using var response = await _httpClient.SendAsync(request, cancellationToken);
            var text = await response.Content.ReadAsStringAsync(cancellationToken);
            EnsureSuccess(response, text);
            using var document = JsonDocument.Parse(text);
            var models = document.RootElement.GetProperty("models")
                .EnumerateArray()
                .Select(item => item.GetProperty("name").GetString()?.Replace("models/", "", StringComparison.OrdinalIgnoreCase))
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .Select(item => item!)
                .Where(item => !item.Contains("embedding", StringComparison.OrdinalIgnoreCase))
                .OrderBy(item => item, StringComparer.OrdinalIgnoreCase)
                .ToList();

            return models.Count > 0 ? models : GeminiFallbackModels.ToList();
        }
        catch
        {
            return GeminiFallbackModels.ToList();
        }
    }

    private async Task<ArticleTranslation> TranslateOpenAiAsync(AiChannel channel, TranslationJob job, CancellationToken cancellationToken)
    {
        var payload = new
        {
            model = channel.Model,
            temperature = 0.2,
            messages = new object[]
            {
                new { role = "system", content = SystemPrompt(job.TargetLanguage) },
                new { role = "user", content = UserPrompt(job) }
            }
        };
        using var request = new HttpRequestMessage(HttpMethod.Post, CombineUrl(OpenAiBaseUrl(channel), "chat/completions"));
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", CleanApiKey(channel.ApiKey));
        request.Content = new StringContent(JsonSerializer.Serialize(payload, JsonOptions), Encoding.UTF8, "application/json");
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        var content = document.RootElement.GetProperty("choices")[0].GetProperty("message").GetProperty("content").GetString() ?? "";
        return ParseTranslation(content, job);
    }

    private async Task<ArticleTranslation> TranslateGeminiAsync(AiChannel channel, TranslationJob job, CancellationToken cancellationToken)
    {
        var model = string.IsNullOrWhiteSpace(channel.Model) ? "gemini-1.5-flash" : channel.Model;
        var payload = new
        {
            contents = new[]
            {
                new
                {
                    parts = new[] { new { text = SystemPrompt(job.TargetLanguage) + "\n\n" + UserPrompt(job) } }
                }
            },
            generationConfig = new { temperature = 0.2 }
        };
        var url = $"{CombineUrl(GeminiBaseUrl(channel), $"models/{model}:generateContent")}?key={Uri.EscapeDataString(CleanApiKey(channel.ApiKey))}";
        using var request = new HttpRequestMessage(HttpMethod.Post, url);
        request.Content = new StringContent(JsonSerializer.Serialize(payload, JsonOptions), Encoding.UTF8, "application/json");
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        var content = document.RootElement.GetProperty("candidates")[0].GetProperty("content").GetProperty("parts")[0].GetProperty("text").GetString() ?? "";
        return ParseTranslation(content, job);
    }

    private static ArticleTranslation ParseTranslation(string text, TranslationJob fallback)
    {
        var cleaned = text.Trim();
        if (cleaned.StartsWith("```", StringComparison.Ordinal))
        {
            var firstLine = cleaned.IndexOf('\n');
            var lastFence = cleaned.LastIndexOf("```", StringComparison.Ordinal);
            if (firstLine >= 0 && lastFence > firstLine)
            {
                cleaned = cleaned[(firstLine + 1)..lastFence].Trim();
            }
        }

        try
        {
            using var document = JsonDocument.Parse(cleaned);
            return new ArticleTranslation
            {
                Title = document.RootElement.GetProperty("title").GetString() ?? fallback.Title,
                Content = document.RootElement.GetProperty("content").GetString() ?? fallback.Content
            };
        }
        catch
        {
            return new ArticleTranslation { Title = fallback.Title, Content = cleaned };
        }
    }

    private static string SystemPrompt(string language)
    {
        return $"你是 RSS 文章翻译器。把输入翻译为{language}，保持原有 HTML/Markdown 结构、链接、代码块、列表和段落格式。不要总结，不要添加解释，只返回 JSON：{{\"title\":\"...\",\"content\":\"...\"}}。";
    }

    private static string UserPrompt(TranslationJob job)
    {
        return $"标题：{job.Title}\n链接：{job.Link}\n正文：\n{job.Content}";
    }

    private static string OpenAiBaseUrl(AiChannel channel)
    {
        if (channel.Provider == "openai_compatible")
        {
            if (string.IsNullOrWhiteSpace(channel.BaseUrl))
            {
                throw new InvalidOperationException("OpenAI 兼容渠道需要填写 Base URL。");
            }

            return channel.BaseUrl.Trim().TrimEnd('/');
        }

        return channel.Provider switch
        {
            "qwen" => "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "doubao" => "https://ark.cn-beijing.volces.com/api/v3",
            "deepseek" => "https://api.deepseek.com",
            "kimi" => "https://api.moonshot.cn/v1",
            "zhipu" => "https://open.bigmodel.cn/api/paas/v4",
            _ => "https://api.openai.com/v1"
        };
    }

    private static string GeminiBaseUrl(AiChannel channel)
    {
        return "https://generativelanguage.googleapis.com/v1beta";
    }

    private static string CombineUrl(string baseUrl, string path)
    {
        return $"{baseUrl.TrimEnd('/')}/{path.TrimStart('/')}";
    }

    private static bool IsUsableOpenAiChatModel(string model)
    {
        var lower = model.ToLowerInvariant();
        string[] skipKeywords = ["embedding", "whisper", "tts", "dall-e", "moderation"];
        return !skipKeywords.Any(lower.Contains);
    }

    private static void EnsureSuccess(HttpResponseMessage response, string text)
    {
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException($"AI 请求失败 {(int)response.StatusCode}：{ExtractErrorMessage(text)}");
        }
    }

    private static string CleanApiKey(string apiKey)
    {
        return apiKey.Trim().Trim('"', '\'');
    }

    private static string ExtractErrorMessage(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return "服务器没有返回错误详情。";
        }

        try
        {
            using var document = JsonDocument.Parse(text);
            if (document.RootElement.TryGetProperty("error", out var error))
            {
                if (error.ValueKind == JsonValueKind.Object && error.TryGetProperty("message", out var message))
                {
                    return message.GetString() ?? text;
                }

                if (error.ValueKind == JsonValueKind.String)
                {
                    return error.GetString() ?? text;
                }
            }
        }
        catch
        {
        }

        return text.Length > 600 ? text[..600] + "..." : text;
    }
}
