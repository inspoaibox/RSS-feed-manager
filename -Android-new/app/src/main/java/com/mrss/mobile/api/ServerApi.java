package com.mrss.mobile.api;

import com.mrss.mobile.data.AppSettings;
import com.mrss.mobile.model.Article;
import com.mrss.mobile.model.ArticleState;
import com.mrss.mobile.model.Category;
import com.mrss.mobile.model.Feed;
import com.mrss.mobile.model.PendingAction;
import com.mrss.mobile.model.SyncResult;
import com.mrss.mobile.model.User;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.TimeUnit;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class ServerApi {
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");

    private final AppSettings settings;
    private final OkHttpClient client;

    public ServerApi(AppSettings settings) {
        this.settings = settings;
        this.client = new OkHttpClient.Builder()
                .connectTimeout(20, TimeUnit.SECONDS)
                .readTimeout(45, TimeUnit.SECONDS)
                .writeTimeout(30, TimeUnit.SECONDS)
                .build();
    }

    public User login(String baseUrl, String username, String password) throws ApiException {
        settings.setBaseUrl(baseUrl);
        JSONObject body = new JSONObject();
        try {
            body.put("username", username);
            body.put("password", password);
            JSONObject response = request("POST", "/auth/login", body, false);
            settings.saveTokens(response.optString("access_token", ""), response.optString("refresh_token", ""));
            JSONObject userJson = response.optJSONObject("user");
            User user = parseUser(userJson == null ? new JSONObject() : userJson);
            settings.setUsername(user.username);
            return user;
        } catch (JSONException e) {
            throw new ApiException("登录响应解析失败", e);
        }
    }

    public void refreshToken() throws ApiException {
        String refreshToken = settings.getRefreshToken();
        if (refreshToken.trim().isEmpty()) {
            throw new ApiException(401, "请重新登录");
        }
        JSONObject body = new JSONObject();
        try {
            body.put("refresh_token", refreshToken);
            JSONObject response = request("POST", "/auth/refresh", body, false);
            settings.saveTokens(response.optString("access_token", ""), response.optString("refresh_token", refreshToken));
        } catch (JSONException e) {
            throw new ApiException("刷新登录状态失败", e);
        }
    }

    public SyncResult sync(String since, int offset, int limit) throws ApiException {
        StringBuilder path = new StringBuilder("/mobile/sync?limit=").append(limit).append("&offset=").append(offset);
        if (since != null && !since.trim().isEmpty()) {
            path.append("&since=").append(urlEncode(since));
        }
        JSONObject response = requestWithRefresh("GET", path.toString(), null);
        try {
            SyncResult result = new SyncResult();
            result.serverTime = JsonUtils.optString(response, "server_time");
            result.hasMore = response.optBoolean("has_more", false);
            if (!response.isNull("next_offset")) {
                result.nextOffset = response.optInt("next_offset");
            }

            JSONArray categories = response.optJSONArray("categories");
            if (categories != null) {
                for (int i = 0; i < categories.length(); i++) {
                    result.categories.add(parseCategory(categories.getJSONObject(i)));
                }
            }

            JSONArray feeds = response.optJSONArray("feeds");
            if (feeds != null) {
                for (int i = 0; i < feeds.length(); i++) {
                    result.feeds.add(parseFeed(feeds.getJSONObject(i)));
                }
            }

            JSONArray articles = response.optJSONArray("articles");
            if (articles != null) {
                for (int i = 0; i < articles.length(); i++) {
                    result.articles.add(parseArticle(articles.getJSONObject(i)));
                }
            }

            JSONArray states = response.optJSONArray("states");
            if (states != null) {
                for (int i = 0; i < states.length(); i++) {
                    result.states.add(parseArticleState(states.getJSONObject(i)));
                }
            }

            return result;
        } catch (JSONException e) {
            throw new ApiException("同步响应解析失败", e);
        }
    }

    public void uploadActions(List<PendingAction> actions) throws ApiException {
        if (actions == null || actions.isEmpty()) {
            return;
        }
        JSONObject body = new JSONObject();
        JSONArray array = new JSONArray();
        try {
            for (PendingAction action : actions) {
                JSONObject item = new JSONObject();
                item.put("client_action_id", action.clientActionId);
                item.put("type", action.type);
                item.put("article_id", action.articleId);
                if (action.value != null) {
                    item.put("value", action.value.booleanValue());
                }
                array.put(item);
            }
            body.put("actions", array);
            requestWithRefresh("POST", "/mobile/actions", body);
        } catch (JSONException e) {
            throw new ApiException("上传离线操作失败", e);
        }
    }

    public Article translateArticle(long articleId) throws ApiException {
        JSONObject response = requestWithRefresh("POST", "/articles/" + articleId + "/translate?target_language=zh-CN", new JSONObject());
        Article article = new Article();
        article.id = articleId;
        article.translation = JsonUtils.optString(response, "translation");
        return article;
    }

    public Article summarizeArticle(long articleId) throws ApiException {
        JSONObject response = requestWithRefresh("POST", "/articles/" + articleId + "/summarize", new JSONObject());
        Article article = new Article();
        article.id = articleId;
        article.summary = JsonUtils.optString(response, "summary");
        return article;
    }

    private JSONObject requestWithRefresh(String method, String path, JSONObject body) throws ApiException {
        try {
            return request(method, path, body, true);
        } catch (ApiException e) {
            if (e.statusCode != 401) {
                throw e;
            }
            refreshToken();
            return request(method, path, body, true);
        }
    }

    private JSONObject request(String method, String path, JSONObject body, boolean auth) throws ApiException {
        String baseUrl = AppSettings.normalizeBaseUrl(settings.getBaseUrl());
        if (baseUrl.trim().isEmpty()) {
            throw new ApiException(0, "请先填写服务端地址");
        }
        String url = baseUrl + "/api/v1" + path;
        RequestBody requestBody = body == null ? null : RequestBody.create(body.toString(), JSON);
        Request.Builder builder = new Request.Builder().url(url);
        if (auth) {
            String token = settings.getAccessToken();
            if (!token.trim().isEmpty()) {
                builder.header("Authorization", "Bearer " + token);
            }
        }
        if ("GET".equals(method)) {
            builder.get();
        } else if ("POST".equals(method)) {
            builder.post(requestBody == null ? RequestBody.create(new byte[0], null) : requestBody);
        } else if ("PUT".equals(method)) {
            builder.put(requestBody == null ? RequestBody.create(new byte[0], null) : requestBody);
        } else {
            throw new ApiException(0, "Unsupported method: " + method);
        }

        try (Response response = client.newCall(builder.build()).execute()) {
            String responseBody = response.body() == null ? "" : response.body().string();
            if (!response.isSuccessful()) {
                throw new ApiException(response.code(), extractError(path, response.code(), responseBody, response.message()));
            }
            if (responseBody.trim().isEmpty()) {
                return new JSONObject();
            }
            return JsonUtils.parseObject(responseBody);
        } catch (IOException e) {
            throw new ApiException("网络请求失败: " + e.getMessage(), e);
        } catch (JSONException e) {
            throw new ApiException("服务端返回格式无效", e);
        }
    }

    private String extractError(String path, int statusCode, String body, String fallback) {
        if (statusCode == 404 && path.startsWith("/mobile/")) {
            return "移动同步接口不存在。请确认服务端已部署最新代码并重启；服务端地址只填域名/IP，不要带 /api 或 /api/v1。";
        }
        try {
            JSONObject object = JsonUtils.parseObject(body);
            if (JsonUtils.hasNonEmpty(object, "detail")) {
                Object detail = object.get("detail");
                return String.valueOf(detail);
            }
        } catch (Exception ignored) {
        }
        return fallback == null || fallback.trim().isEmpty() ? "请求失败" : fallback;
    }

    private User parseUser(JSONObject object) {
        User user = new User();
        user.id = object.optLong("id");
        user.username = object.optString("username", "");
        user.email = object.optString("email", "");
        user.active = object.optBoolean("is_active", true);
        user.admin = object.optBoolean("is_admin", false);
        return user;
    }

    private Category parseCategory(JSONObject object) {
        Category category = new Category();
        category.id = object.optLong("id");
        category.name = object.optString("name", "");
        category.description = JsonUtils.optString(object, "description");
        category.position = object.optInt("position");
        category.feedCount = object.optInt("feed_count");
        category.unreadCount = object.optInt("unread_count");
        return category;
    }

    private Feed parseFeed(JSONObject object) {
        Feed feed = new Feed();
        feed.id = object.optLong("id");
        feed.url = object.optString("url", "");
        feed.title = object.optString("title", "");
        feed.description = JsonUtils.optString(object, "description");
        feed.siteUrl = JsonUtils.optString(object, "site_url");
        feed.iconUrl = JsonUtils.optString(object, "icon_url");
        feed.categoryId = JsonUtils.optLongObject(object, "category_id");
        feed.fetchInterval = object.optInt("fetch_interval");
        feed.lastFetchedAt = JsonUtils.optString(object, "last_fetched_at");
        feed.autoTranslate = object.optBoolean("auto_translate");
        feed.autoSummarize = object.optBoolean("auto_summarize");
        feed.targetLanguage = JsonUtils.optString(object, "target_language");
        feed.translateMethod = object.optString("translate_method", "none");
        feed.active = object.optBoolean("is_active", true);
        feed.usePlaywright = object.optBoolean("use_playwright");
        feed.position = object.optInt("position");
        feed.unreadCount = object.optInt("unread_count");
        feed.articleCount = object.optInt("article_count");
        return feed;
    }

    private Article parseArticle(JSONObject object) {
        Article article = new Article();
        article.id = object.optLong("id");
        article.feedId = object.optLong("feed_id");
        article.feedTitle = JsonUtils.optString(object, "feed_title");
        article.title = object.optString("title", "");
        article.link = JsonUtils.optString(object, "link");
        article.content = JsonUtils.optString(object, "content");
        article.fullContent = JsonUtils.optString(object, "full_content");
        article.summary = JsonUtils.optString(object, "summary");
        article.translation = JsonUtils.optString(object, "translation");
        article.author = JsonUtils.optString(object, "author");
        article.publishedAt = JsonUtils.optString(object, "published_at");
        article.createdAt = JsonUtils.optString(object, "created_at");
        article.updatedAt = JsonUtils.optString(object, "updated_at");
        article.read = object.optBoolean("is_read");
        article.favorite = object.optBoolean("is_favorite");
        article.readAt = JsonUtils.optString(object, "read_at");
        return article;
    }

    private ArticleState parseArticleState(JSONObject object) {
        ArticleState state = new ArticleState();
        state.articleId = object.optLong("article_id");
        state.read = object.optBoolean("is_read");
        state.favorite = object.optBoolean("is_favorite");
        state.readAt = JsonUtils.optString(object, "read_at");
        return state;
    }

    private String urlEncode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
