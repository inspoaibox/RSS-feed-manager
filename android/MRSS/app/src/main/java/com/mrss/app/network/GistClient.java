package com.mrss.app.network;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class GistClient {
    public String upload(String token, String gistId, String filename, String content) throws Exception {
        JSONObject file = new JSONObject();
        file.put("content", content);

        JSONObject files = new JSONObject();
        files.put(filename, file);

        JSONObject body = new JSONObject();
        body.put("description", "MRSS subscriptions");
        body.put("public", false);
        body.put("files", files);

        String endpoint = (gistId == null || gistId.trim().isEmpty())
                ? "https://api.github.com/gists"
                : "https://api.github.com/gists/" + gistId.trim();
        String method = (gistId == null || gistId.trim().isEmpty()) ? "POST" : "PATCH";
        JSONObject response = new JSONObject(request(method, endpoint, token, body.toString()));
        return response.optString("id", gistId == null ? "" : gistId);
    }

    public String download(String token, String gistId, String filename) throws Exception {
        if (gistId == null || gistId.trim().isEmpty()) {
            throw new IllegalArgumentException("Gist ID 不能为空");
        }
        JSONObject response = new JSONObject(request("GET", "https://api.github.com/gists/" + gistId.trim(), token, null));
        JSONObject files = response.getJSONObject("files");
        if (!files.has(filename)) {
            throw new IllegalArgumentException("Gist 中没有找到文件：" + filename);
        }
        return files.getJSONObject(filename).getString("content");
    }

    private String request(String method, String endpoint, String token, String body) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(30000);
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("User-Agent", "MRSS-Android");
        connection.setRequestProperty("Authorization", "Bearer " + token);
        if (body != null) {
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream output = connection.getOutputStream()) {
                output.write(body.getBytes(StandardCharsets.UTF_8));
            }
        }
        int code = connection.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? connection.getInputStream() : connection.getErrorStream();
        String text = readAll(stream);
        if (code < 200 || code >= 300) {
            throw new IllegalStateException("GitHub 请求失败 " + code + "：" + text);
        }
        return text;
    }

    private static String readAll(InputStream stream) throws Exception {
        if (stream == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line).append('\n');
            }
        }
        return builder.toString();
    }
}
