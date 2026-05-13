namespace MRSS.Native.Models;

public sealed class AiChannel
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Provider { get; set; } = "openai";
    public string BaseUrl { get; set; } = "";
    public string ApiKey { get; set; } = "";
    public string Model { get; set; } = "";
    public bool IsDefault { get; set; }
    public long CreatedAt { get; set; }
    public long? UpdatedAt { get; set; }

    public string ProviderLabel => Provider switch
    {
        "openai" => "OpenAI 官方",
        "gemini" => "Gemini 官方",
        "qwen" => "通义千问",
        "doubao" => "豆包",
        "deepseek" => "DeepSeek",
        "kimi" => "Kimi",
        "zhipu" => "智谱",
        "openai_compatible" => "OpenAI 兼容",
        _ => "OpenAI 官方"
    };

    public bool RequiresBaseUrl => Provider == "openai_compatible";

    public override string ToString() => $"{Name} · {ProviderLabel}" + (IsDefault ? " · 默认" : "");
}
