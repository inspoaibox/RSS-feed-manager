package com.mrss.app.network;

import com.mrss.app.model.AiChannel;
import com.mrss.app.model.ArticleTranslation;
import com.mrss.app.model.TranslationJob;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class AiClient {
    private static final int MODEL_CONNECT_TIMEOUT_MS = 20000;
    private static final int MODEL_READ_TIMEOUT_MS = 30000;
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    public interface ProgressListener {
        void onProgress(String stage);
    }

    public List<String> fetchModels(AiChannel channel) throws Exception {
        try {
            if ("gemini".equals(channel.provider)) {
                return fetchGeminiModels(channel);
            }
            return fetchOpenAiModels(channel);
        } catch (SocketTimeoutException e) {
            throw new IllegalStateException("拉取模型超时，请检查网络、代理或 API 地址。");
        }
    }

    public ArticleTranslation translate(AiChannel channel, TranslationJob job) throws Exception {
        return translate(channel, job, null);
    }

    public ArticleTranslation translate(AiChannel channel, TranslationJob job, ProgressListener listener) throws Exception {
        try {
            notify(listener, "准备请求");
            String targetLanguage = isBlank(job.targetLanguage) ? "中文" : job.targetLanguage;
            String sourceTitle = firstNonEmpty(job.title, "");
            String sourceText = firstNonEmpty(job.content, sourceTitle);
            ArticleTranslation translation = new ArticleTranslation();
            translation.title = sourceTitle;
            translation.content = isBlank(sourceText)
                    ? ""
                    : firstNonEmpty(translateText(channel, sourceText, targetLanguage, listener), sourceText);
            return translation;
        } catch (SocketTimeoutException e) {
            throw new IllegalStateException("AI 翻译网络超时，请检查网络/API 节点。");
        }
    }

    private List<String> fetchOpenAiModels(AiChannel channel) throws Exception {
        try {
            HttpURLConnection connection = open("GET", openAiBase(channel) + "/models", channel.apiKey, false, false);
            String text = read(connection);
            JSONArray data = new JSONObject(text).getJSONArray("data");
            List<String> models = new ArrayList<>();
            for (int i = 0; i < data.length(); i++) {
                String id = data.getJSONObject(i).optString("id");
                if (!isBlank(id)) {
                    models.add(id);
                }
            }
            Collections.sort(models);
            if (!models.isEmpty()) {
                return models;
            }
        } catch (Exception e) {
            List<String> fallback = fallbackModels(channel.provider);
            if (!fallback.isEmpty()) {
                return fallback;
            }
            throw e;
        }
        return fallbackModels(channel.provider);
    }

    private List<String> fetchGeminiModels(AiChannel channel) throws Exception {
        HttpURLConnection connection = open("GET", geminiUrl(channel, "/models"), channel.apiKey, true, false);
        String text = read(connection);
        JSONArray data = new JSONObject(text).getJSONArray("models");
        List<String> models = new ArrayList<>();
        for (int i = 0; i < data.length(); i++) {
            models.add(data.getJSONObject(i).optString("name").replace("models/", ""));
        }
        Collections.sort(models);
        return models;
    }

    private String translateText(AiChannel channel, String text, String targetLanguage, ProgressListener listener) throws Exception {
        if (isBlank(text)) {
            return "";
        }
        if ("gemini".equals(channel.provider)) {
            return translateGeminiText(channel, text, targetLanguage, listener);
        }
        return translateOpenAiText(channel, text, targetLanguage, listener);
    }

    private String translateOpenAiText(AiChannel channel, String text, String targetLanguage, ProgressListener listener) throws Exception {
        JSONObject body = new JSONObject();
        body.put("model", channel.model);
        body.put("temperature", 0.3);
        JSONArray messages = new JSONArray();
        messages.put(new JSONObject().put("role", "system").put("content", translationPrompt(targetLanguage)));
        messages.put(new JSONObject().put("role", "user").put("content", text));
        body.put("messages", messages);
        String responseText = postJson(openAiBase(channel) + "/chat/completions", channel.apiKey, false, body, listener);
        notify(listener, "解析响应");
        return new JSONObject(responseText).getJSONArray("choices").getJSONObject(0).getJSONObject("message").optString("content").trim();
    }

    private String translateGeminiText(AiChannel channel, String text, String targetLanguage, ProgressListener listener) throws Exception {
        String model = isBlank(channel.model) ? "gemini-1.5-flash" : channel.model;
        JSONObject body = new JSONObject();
        JSONArray contents = new JSONArray();
        JSONObject content = new JSONObject();
        content.put("parts", new JSONArray().put(new JSONObject().put("text", translationPrompt(targetLanguage) + "\n\n" + text)));
        contents.put(content);
        body.put("contents", contents);
        String responseText = postJson(geminiUrl(channel, "/models/" + model + ":generateContent"), channel.apiKey, true, body, listener);
        notify(listener, "解析响应");
        return new JSONObject(responseText).getJSONArray("candidates").getJSONObject(0)
                .getJSONObject("content").getJSONArray("parts").getJSONObject(0).optString("text").trim();
    }

    private String postJson(String url, String key, boolean gemini, JSONObject body, ProgressListener listener) throws Exception {
        OkHttpClient client = new OkHttpClient.Builder()
                .connectTimeout(0, TimeUnit.MILLISECONDS)
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .writeTimeout(0, TimeUnit.MILLISECONDS)
                .callTimeout(0, TimeUnit.MILLISECONDS)
                .build();
        Request.Builder builder = new Request.Builder()
                .url(url)
                .post(RequestBody.create(body.toString(), JSON))
                .header("Content-Type", "application/json; charset=utf-8");
        if (!gemini) {
            builder.header("Authorization", "Bearer " + cleanKey(key));
        }
        notify(listener, "发送请求");
        notify(listener, "等待 AI 响应");
        try (Response response = client.newCall(builder.build()).execute()) {
            notify(listener, "读取响应");
            String responseText = response.body() == null ? "" : response.body().string();
            if (!response.isSuccessful()) {
                throw new IllegalStateException("AI 请求失败 " + response.code() + "：" + errorMessage(responseText));
            }
            return responseText;
        }
    }

    private HttpURLConnection open(String method, String url, String key, boolean gemini, boolean translation) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(MODEL_CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(MODEL_READ_TIMEOUT_MS);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        if (gemini) {
            // Gemini REST uses ?key= for the official examples. Keep this branch free of
            // Authorization headers so a stale custom header cannot mask key errors.
        } else {
            connection.setRequestProperty("Authorization", "Bearer " + cleanKey(key));
        }
        return connection;
    }

    private void write(HttpURLConnection connection, String text) throws Exception {
        connection.setDoOutput(true);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }

    private String read(HttpURLConnection connection) throws Exception {
        int code = connection.getResponseCode();
        BufferedReader reader = new BufferedReader(new InputStreamReader(
                code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream(),
                StandardCharsets.UTF_8
        ));
        StringBuilder text = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            text.append(line);
        }
        if (code < 200 || code >= 300) {
            throw new IllegalStateException("AI 请求失败 " + code + "：" + errorMessage(text.toString()));
        }
        return text.toString();
    }

    private String translationPrompt(String language) {
        return "You are a translator. Translate the following text to "
                + (isBlank(language) ? "Chinese" : language)
                + ". Keep the original paragraph structure and formatting. Only output the translation, nothing else.";
    }

    private String openAiBase(AiChannel channel) {
        if ("openai_compatible".equals(channel.provider)) {
            if (isBlank(channel.baseUrl)) {
                throw new IllegalStateException("OpenAI 兼容渠道需要填写 Base URL");
            }
            return trimEnd(channel.baseUrl);
        }
        if ("qwen".equals(channel.provider)) {
            return "https://dashscope.aliyuncs.com/compatible-mode/v1";
        }
        if ("doubao".equals(channel.provider)) {
            return "https://ark.cn-beijing.volces.com/api/v3";
        }
        if ("deepseek".equals(channel.provider)) {
            return "https://api.deepseek.com";
        }
        if ("kimi".equals(channel.provider)) {
            return "https://api.moonshot.cn/v1";
        }
        if ("zhipu".equals(channel.provider)) {
            return "https://open.bigmodel.cn/api/paas/v4";
        }
        return "https://api.openai.com/v1";
    }

    private List<String> fallbackModels(String provider) {
        List<String> models = new ArrayList<>();
        if ("qwen".equals(provider)) {
            models.add("qwen-turbo");
            models.add("qwen-plus");
            models.add("qwen-max");
        } else if ("doubao".equals(provider)) {
            models.add("请填写火山方舟接入点 ID");
        } else if ("deepseek".equals(provider)) {
            models.add("deepseek-chat");
            models.add("deepseek-reasoner");
        } else if ("kimi".equals(provider)) {
            models.add("moonshot-v1-8k");
            models.add("moonshot-v1-32k");
            models.add("moonshot-v1-128k");
        } else if ("zhipu".equals(provider)) {
            models.add("glm-4-flash");
            models.add("glm-4-plus");
        }
        return models;
    }

    private String geminiBase(AiChannel channel) {
        return "https://generativelanguage.googleapis.com/v1beta";
    }

    private String geminiUrl(AiChannel channel, String path) throws Exception {
        return geminiBase(channel) + path + "?key=" + URLEncoder.encode(cleanKey(channel.apiKey), "UTF-8");
    }

    private String trimEnd(String value) {
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private String firstNonEmpty(String value, String fallback) {
        return isBlank(value) ? fallback : value;
    }

    private void notify(ProgressListener listener, String stage) {
        if (listener != null) {
            listener.onProgress(stage);
        }
    }

    private String cleanKey(String value) {
        if (value == null) {
            return "";
        }
        String key = value.trim();
        while ((key.startsWith("\"") && key.endsWith("\"")) || (key.startsWith("'") && key.endsWith("'"))) {
            key = key.substring(1, key.length() - 1).trim();
        }
        return key;
    }

    private String errorMessage(String text) {
        if (isBlank(text)) {
            return "服务器没有返回错误详情";
        }
        try {
            JSONObject object = new JSONObject(text);
            if (object.has("error")) {
                Object error = object.get("error");
                if (error instanceof JSONObject) {
                    String message = ((JSONObject) error).optString("message");
                    if (!isBlank(message)) {
                        return message;
                    }
                }
                if (error instanceof String && !isBlank((String) error)) {
                    return (String) error;
                }
            }
        } catch (Exception ignored) {
        }
        return text.length() > 600 ? text.substring(0, 600) + "..." : text;
    }
}
