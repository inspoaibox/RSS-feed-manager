using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using MRSS.Native.Data;
using MRSS.Native.Models;

namespace MRSS.Native.Services;

public sealed class BackupService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    private readonly Repository _repository;
    private readonly HttpClient _httpClient = new();

    public BackupService(Repository repository)
    {
        _repository = repository;
    }

    public string ExportJson()
    {
        return JsonSerializer.Serialize(_repository.ExportBackup(), JsonOptions);
    }

    public string ExportSubscriptionSyncJson()
    {
        return JsonSerializer.Serialize(_repository.ExportSubscriptionSync(), JsonOptions);
    }

    public async Task ImportJsonAsync(string json)
    {
        var document = JsonSerializer.Deserialize<BackupDocument>(json, JsonOptions)
            ?? throw new InvalidOperationException("备份文件无法解析。");
        await _repository.RestoreBackupAsync(document);
    }

    public async Task<int> ImportSubscriptionSyncJsonAsync(string json)
    {
        var document = JsonSerializer.Deserialize<SubscriptionSyncDocument>(json, JsonOptions)
            ?? throw new InvalidOperationException("同步文件无法解析。");
        return await _repository.ImportSubscriptionSyncAsync(document);
    }

    public async Task<string> UploadGistAsync(string token, string gistId, string filename, CancellationToken cancellationToken = default)
    {
        var body = new
        {
            description = "MRSS subscriptions",
            @public = false,
            files = new Dictionary<string, object>
            {
                [filename] = new { content = ExportSubscriptionSyncJson() }
            }
        };
        using var request = new HttpRequestMessage(string.IsNullOrWhiteSpace(gistId) ? HttpMethod.Post : HttpMethod.Patch, string.IsNullOrWhiteSpace(gistId) ? "https://api.github.com/gists" : $"https://api.github.com/gists/{gistId}");
        request.Headers.UserAgent.ParseAdd("MRSS-Native");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Content = new StringContent(JsonSerializer.Serialize(body, JsonOptions), Encoding.UTF8, "application/json");
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureGithubSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        var id = document.RootElement.GetProperty("id").GetString() ?? gistId;
        await _repository.SetSettingAsync("github_token", token);
        await _repository.SetSettingAsync("gist_id", id);
        await _repository.SetSettingAsync("gist_filename", filename);
        return id;
    }

    public async Task<int> DownloadGistAsync(string token, string gistId, string filename, CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, $"https://api.github.com/gists/{gistId}");
        request.Headers.UserAgent.ParseAdd("MRSS-Native");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        using var response = await _httpClient.SendAsync(request, cancellationToken);
        var text = await response.Content.ReadAsStringAsync(cancellationToken);
        EnsureGithubSuccess(response, text);
        using var document = JsonDocument.Parse(text);
        var files = document.RootElement.GetProperty("files");
        if (!files.TryGetProperty(filename, out var file))
        {
            throw new InvalidOperationException("Gist 中没有找到指定文件。");
        }

        var content = file.GetProperty("content").GetString();
        if (string.IsNullOrWhiteSpace(content))
        {
            throw new InvalidOperationException("Gist 文件内容为空。");
        }

        var changed = await ImportSubscriptionSyncJsonAsync(content);
        await _repository.SetSettingAsync("github_token", token);
        await _repository.SetSettingAsync("gist_id", gistId);
        await _repository.SetSettingAsync("gist_filename", filename);
        return changed;
    }

    private static void EnsureGithubSuccess(HttpResponseMessage response, string text)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        throw new InvalidOperationException($"GitHub 请求失败 {(int)response.StatusCode}：{text}");
    }
}
