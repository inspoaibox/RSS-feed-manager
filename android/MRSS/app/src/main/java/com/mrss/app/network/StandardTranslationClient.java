package com.mrss.app.network;

import com.mrss.app.model.ArticleTranslation;
import com.mrss.app.model.StandardTranslationSettings;
import com.mrss.app.model.TranslationJob;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class StandardTranslationClient {
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private static final MediaType FORM = MediaType.get("application/x-www-form-urlencoded; charset=utf-8");
    private static final Pattern HTML_TAG = Pattern.compile("(?s)<[^>]+>");
    private final OkHttpClient client = new OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(45, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .callTimeout(60, TimeUnit.SECONDS)
            .build();

    public ArticleTranslation translate(StandardTranslationSettings settings, TranslationJob job) throws Exception {
        if (settings == null) {
            throw new IllegalStateException("常规翻译设置不存在");
        }
        ArticleTranslation result = new ArticleTranslation();
        result.title = translatePlain(settings, firstNonEmpty(job.title, ""), job.targetLanguage);
        result.content = translateKeepingFormat(settings, firstNonEmpty(job.content, ""), job.targetLanguage);
        return result;
    }

    private String translateKeepingFormat(StandardTranslationSettings settings, String content, String targetLanguage) throws Exception {
        if (isBlank(content)) {
            return "";
        }
        List<String> textParts = new ArrayList<>();
        List<String> tags = new ArrayList<>();
        Matcher matcher = HTML_TAG.matcher(content);
        int last = 0;
        while (matcher.find()) {
            textParts.add(content.substring(last, matcher.start()));
            tags.add(matcher.group());
            last = matcher.end();
        }
        textParts.add(content.substring(last));
        if (tags.isEmpty()) {
            return translatePlain(settings, content, targetLanguage);
        }
        StringBuilder translated = new StringBuilder();
        for (int i = 0; i < textParts.size(); i++) {
            translated.append(translatePlain(settings, textParts.get(i), targetLanguage));
            if (i < tags.size()) {
                translated.append(tags.get(i));
            }
        }
        return translated.toString();
    }

    private String translatePlain(StandardTranslationSettings settings, String text, String targetLanguage) throws Exception {
        if (isBlank(text) || text.trim().matches("^[\\s\\p{Punct}]+$")) {
            return text;
        }
        String provider = normalizeProvider(settings.provider);
        if ("baidu".equals(provider)) {
            return translateBaidu(settings, text, targetLanguage);
        }
        if ("tencent".equals(provider)) {
            return translateTencent(settings, text, targetLanguage);
        }
        if ("google".equals(provider)) {
            return translateGoogle(settings, text, targetLanguage);
        }
        return translateMicrosoft(settings, text, targetLanguage);
    }

    private String translateBaidu(StandardTranslationSettings settings, String text, String targetLanguage) throws Exception {
        require(settings.baiduAppId, "请填写百度翻译 App ID");
        require(settings.baiduSecret, "请填写百度翻译密钥");
        String salt = String.valueOf(System.currentTimeMillis());
        String to = languageCode(targetLanguage, "baidu");
        String sign = md5(settings.baiduAppId + text + salt + settings.baiduSecret);
        String body = "q=" + encode(text)
                + "&from=auto"
                + "&to=" + encode(to)
                + "&appid=" + encode(settings.baiduAppId)
                + "&salt=" + encode(salt)
                + "&sign=" + encode(sign);
        String response = post("https://fanyi-api.baidu.com/api/trans/vip/translate", body, FORM, null);
        JSONObject object = new JSONObject(response);
        if (object.has("error_code")) {
            throw new IllegalStateException("百度翻译失败 " + object.optString("error_code") + "：" + object.optString("error_msg"));
        }
        JSONArray array = object.getJSONArray("trans_result");
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < array.length(); i++) {
            if (i > 0) {
                builder.append('\n');
            }
            builder.append(array.getJSONObject(i).optString("dst"));
        }
        return builder.toString();
    }

    private String translateMicrosoft(StandardTranslationSettings settings, String text, String targetLanguage) throws Exception {
        require(settings.microsoftKey, "请填写微软翻译 Key");
        String to = languageCode(targetLanguage, "microsoft");
        JSONArray body = new JSONArray().put(new JSONObject().put("Text", text));
        Request.Builder builder = new Request.Builder()
                .url("https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to=" + encode(to))
                .post(RequestBody.create(body.toString(), JSON))
                .header("Content-Type", "application/json; charset=utf-8")
                .header("Ocp-Apim-Subscription-Key", settings.microsoftKey.trim());
        if (!isBlank(settings.microsoftRegion) && !"global".equalsIgnoreCase(settings.microsoftRegion.trim())) {
            builder.header("Ocp-Apim-Subscription-Region", settings.microsoftRegion.trim());
        }
        String response = execute(builder.build());
        return new JSONArray(response).getJSONObject(0).getJSONArray("translations").getJSONObject(0).optString("text");
    }

    private String translateGoogle(StandardTranslationSettings settings, String text, String targetLanguage) throws Exception {
        require(settings.googleApiKey, "请填写 Google 翻译 API Key");
        JSONObject body = new JSONObject()
                .put("q", new JSONArray().put(text))
                .put("target", languageCode(targetLanguage, "google"))
                .put("format", "text");
        String response = post("https://translation.googleapis.com/language/translate/v2?key=" + encode(settings.googleApiKey), body.toString(), JSON, null);
        return new JSONObject(response).getJSONObject("data").getJSONArray("translations").getJSONObject(0).optString("translatedText");
    }

    private String translateTencent(StandardTranslationSettings settings, String text, String targetLanguage) throws Exception {
        require(settings.tencentSecretId, "请填写腾讯云 SecretId");
        require(settings.tencentSecretKey, "请填写腾讯云 SecretKey");
        String host = "tmt.tencentcloudapi.com";
        String service = "tmt";
        long timestamp = System.currentTimeMillis() / 1000L;
        String payload = new JSONObject()
                .put("SourceText", text)
                .put("Source", "auto")
                .put("Target", languageCode(targetLanguage, "tencent"))
                .put("ProjectId", 0)
                .toString();
        String authorization = tencentAuthorization(settings.tencentSecretId.trim(), settings.tencentSecretKey.trim(), host, service, timestamp, payload);
        Request request = new Request.Builder()
                .url("https://" + host)
                .post(RequestBody.create(payload, JSON))
                .header("Authorization", authorization)
                .header("Content-Type", "application/json; charset=utf-8")
                .header("Host", host)
                .header("X-TC-Action", "TextTranslate")
                .header("X-TC-Version", "2018-03-21")
                .header("X-TC-Region", isBlank(settings.tencentRegion) ? "ap-beijing" : settings.tencentRegion.trim())
                .header("X-TC-Timestamp", String.valueOf(timestamp))
                .build();
        String response = execute(request);
        JSONObject object = new JSONObject(response).getJSONObject("Response");
        if (object.has("Error")) {
            JSONObject error = object.getJSONObject("Error");
            throw new IllegalStateException("腾讯翻译失败 " + error.optString("Code") + "：" + error.optString("Message"));
        }
        return object.optString("TargetText");
    }

    private String tencentAuthorization(String secretId, String secretKey, String host, String service, long timestamp, String payload) throws Exception {
        String algorithm = "TC3-HMAC-SHA256";
        String date = utcDate(timestamp);
        String canonicalHeaders = "content-type:application/json; charset=utf-8\nhost:" + host + "\n";
        String signedHeaders = "content-type;host";
        String canonicalRequest = "POST\n/\n\n" + canonicalHeaders + "\n" + signedHeaders + "\n" + sha256Hex(payload);
        String credentialScope = date + "/" + service + "/tc3_request";
        String stringToSign = algorithm + "\n" + timestamp + "\n" + credentialScope + "\n" + sha256Hex(canonicalRequest);
        byte[] secretDate = hmac256(("TC3" + secretKey).getBytes(StandardCharsets.UTF_8), date);
        byte[] secretService = hmac256(secretDate, service);
        byte[] secretSigning = hmac256(secretService, "tc3_request");
        String signature = bytesToHex(hmac256(secretSigning, stringToSign));
        return algorithm + " Credential=" + secretId + "/" + credentialScope + ", SignedHeaders=" + signedHeaders + ", Signature=" + signature;
    }

    private String post(String url, String body, MediaType mediaType, Request.Builder headers) throws Exception {
        Request.Builder builder = headers == null ? new Request.Builder() : headers;
        return execute(builder.url(url).post(RequestBody.create(body, mediaType)).build());
    }

    private String execute(Request request) throws Exception {
        try (Response response = client.newCall(request).execute()) {
            String text = response.body() == null ? "" : response.body().string();
            if (!response.isSuccessful()) {
                throw new IllegalStateException("翻译请求失败 " + response.code() + "：" + (isBlank(text) ? "服务器没有返回错误详情" : text));
            }
            return text;
        }
    }

    private String languageCode(String language, String provider) {
        String value = isBlank(language) ? "中文" : language.trim().toLowerCase(Locale.ROOT);
        boolean chinese = value.contains("中文") || value.contains("chinese") || value.equals("zh") || value.equals("zh-cn") || value.equals("zh-hans");
        boolean traditionalChinese = value.contains("繁体") || value.equals("zh-tw") || value.equals("zh-hant");
        boolean english = value.contains("英文") || value.contains("英语") || value.contains("english") || value.equals("en");
        boolean japanese = value.contains("日文") || value.contains("日语") || value.contains("japanese") || value.equals("ja") || value.equals("jp");
        boolean korean = value.contains("韩文") || value.contains("韩语") || value.contains("korean") || value.equals("ko");
        boolean french = value.contains("法文") || value.contains("法语") || value.contains("french") || value.equals("fr");
        boolean spanish = value.contains("西班牙") || value.contains("spanish") || value.equals("es");
        boolean russian = value.contains("俄文") || value.contains("俄语") || value.contains("russian") || value.equals("ru");
        boolean german = value.contains("德文") || value.contains("德语") || value.contains("german") || value.equals("de");
        if ("baidu".equals(provider)) {
            if (traditionalChinese) return "cht";
            if (chinese) return "zh";
            if (english) return "en";
            if (japanese) return "jp";
            if (korean) return "kor";
            if (french) return "fra";
            if (spanish) return "spa";
            if (russian) return "ru";
            if (german) return "de";
        }
        if ("google".equals(provider)) {
            if (traditionalChinese) return "zh-TW";
            if (chinese) return "zh-CN";
        }
        if ("microsoft".equals(provider)) {
            if (traditionalChinese) return "zh-Hant";
            if (chinese) return "zh-Hans";
        }
        if ("tencent".equals(provider)) {
            if (traditionalChinese) return "zh-TW";
            if (chinese) return "zh";
        }
        if (chinese) return "zh";
        if (english) return "en";
        if (japanese) return "ja";
        if (korean) return "ko";
        if (french) return "fr";
        if (spanish) return "es";
        if (russian) return "ru";
        if (german) return "de";
        return language.trim();
    }

    private String normalizeProvider(String provider) {
        if (isBlank(provider)) {
            return "microsoft";
        }
        String value = provider.trim().toLowerCase(Locale.ROOT);
        if ("baidu".equals(value) || "tencent".equals(value) || "google".equals(value)) {
            return value;
        }
        return "microsoft";
    }

    private void require(String value, String message) {
        if (isBlank(value)) {
            throw new IllegalStateException(message);
        }
    }

    private String encode(String value) throws Exception {
        return URLEncoder.encode(value == null ? "" : value, "UTF-8");
    }

    private String firstNonEmpty(String value, String fallback) {
        return isBlank(value) ? fallback : value;
    }

    private boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private String md5(String value) throws Exception {
        MessageDigest md = MessageDigest.getInstance("MD5");
        return bytesToHex(md.digest(value.getBytes(StandardCharsets.UTF_8)));
    }

    private String sha256Hex(String value) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        return bytesToHex(md.digest(value.getBytes(StandardCharsets.UTF_8)));
    }

    private byte[] hmac256(byte[] key, String value) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        return mac.doFinal(value.getBytes(StandardCharsets.UTF_8));
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder builder = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            builder.append(String.format(Locale.ROOT, "%02x", b & 0xff));
        }
        return builder.toString();
    }

    private String utcDate(long timestamp) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        return format.format(new Date(timestamp * 1000L));
    }
}
