package com.mrss.app.model;

import java.util.ArrayList;
import java.util.List;

public class AiChannel {
    public long id;
    public String name;
    public String provider;
    public String baseUrl;
    public String apiKey;
    public String model;
    public List<String> models = new ArrayList<>();
    public boolean isDefault;

    public AiChannel() {
        provider = "openai";
        baseUrl = "";
    }

    @Override
    public String toString() {
        String type;
        if ("gemini".equals(provider)) {
            type = "Gemini 官方";
        } else if ("qwen".equals(provider)) {
            type = "通义千问";
        } else if ("doubao".equals(provider)) {
            type = "豆包";
        } else if ("deepseek".equals(provider)) {
            type = "DeepSeek";
        } else if ("kimi".equals(provider)) {
            type = "Kimi";
        } else if ("zhipu".equals(provider)) {
            type = "智谱";
        } else if ("openai_compatible".equals(provider)) {
            type = "OpenAI 兼容";
        } else {
            type = "OpenAI 官方";
        }
        return (name == null || name.trim().isEmpty() ? "AI 渠道" : name) + " · " + type + (isDefault ? " · 默认" : "");
    }
}
