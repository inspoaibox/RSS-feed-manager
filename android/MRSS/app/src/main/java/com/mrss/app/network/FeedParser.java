package com.mrss.app.network;

import android.util.Xml;

import com.mrss.app.model.ParsedArticle;
import com.mrss.app.model.ParsedFeed;

import org.xmlpull.v1.XmlPullParser;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.Charset;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CodingErrorAction;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class FeedParser {
    private static final Pattern CHARSET_PATTERN = Pattern.compile("charset=([^;\\s]+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern XML_ENCODING_PATTERN = Pattern.compile("encoding=[\"']([^\"']+)[\"']", Pattern.CASE_INSENSITIVE);

    public ParsedFeed fetchAndParse(String url) throws Exception {
        String xml = fetch(url);
        return parse(xml);
    }

    private String fetch(String sourceUrl) throws Exception {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(sourceUrl);
            connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(20000);
            connection.setReadTimeout(30000);
            connection.setInstanceFollowRedirects(true);
            connection.setRequestProperty("User-Agent", "MRSS/0.1 Android RSS Reader");
            connection.setRequestProperty("Accept", "application/rss+xml, application/atom+xml, application/xml, text/xml, */*");
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                throw new IllegalStateException("HTTP " + code);
            }
            try (InputStream input = connection.getInputStream()) {
                return decode(readAllBytes(input), connection.getContentType());
            }
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private ParsedFeed parse(String xml) throws Exception {
        XmlPullParser parser = Xml.newPullParser();
        parser.setFeature(XmlPullParser.FEATURE_PROCESS_NAMESPACES, false);
        parser.setInput(new ByteArrayInputStream(xml.getBytes(StandardCharsets.UTF_8)), "UTF-8");

        ParsedFeed feed = new ParsedFeed();
        ParsedArticle currentArticle = null;
        String currentTag = null;
        boolean insideItem = false;
        boolean insideFeedHeader = true;
        boolean isAtom = false;

        int event = parser.getEventType();
        while (event != XmlPullParser.END_DOCUMENT) {
            if (event == XmlPullParser.START_TAG) {
                String name = parser.getName();
                currentTag = normalize(name);
                if ("feed".equals(currentTag)) {
                    isAtom = true;
                }
                if ("item".equals(currentTag) || ("entry".equals(currentTag) && isAtom)) {
                    insideItem = true;
                    insideFeedHeader = false;
                    currentArticle = new ParsedArticle();
                } else if ("link".equals(currentTag)) {
                    String href = parser.getAttributeValue(null, "href");
                    if (href != null) {
                        if (insideItem && currentArticle != null && isBlank(currentArticle.link)) {
                            currentArticle.link = href;
                        } else if (!insideItem && isBlank(feed.siteUrl)) {
                            feed.siteUrl = href;
                        }
                    }
                }
            } else if (event == XmlPullParser.TEXT || event == XmlPullParser.CDSECT) {
                String text = parser.getText();
                if (!isBlank(text) && currentTag != null) {
                    if (insideItem && currentArticle != null) {
                        applyArticleText(currentArticle, currentTag, text);
                    } else if (insideFeedHeader) {
                        applyFeedText(feed, currentTag, text);
                    }
                }
            } else if (event == XmlPullParser.END_TAG) {
                String name = normalize(parser.getName());
                if (("item".equals(name) || "entry".equals(name)) && currentArticle != null) {
                    normalizeArticle(currentArticle);
                    if (!isBlank(currentArticle.guid)) {
                        feed.articles.add(currentArticle);
                    }
                    currentArticle = null;
                    insideItem = false;
                }
                currentTag = null;
            }
            event = parser.next();
        }

        if (isBlank(feed.title)) {
            feed.title = "Untitled Feed";
        }
        return feed;
    }

    private void applyFeedText(ParsedFeed feed, String tag, String text) {
        String value = text.trim();
        switch (tag) {
            case "title":
                if (isBlank(feed.title)) {
                    feed.title = value;
                }
                break;
            case "description":
            case "subtitle":
                if (isBlank(feed.description)) {
                    feed.description = value;
                }
                break;
            case "link":
                if (isBlank(feed.siteUrl)) {
                    feed.siteUrl = value;
                }
                break;
            case "url":
                if (isBlank(feed.iconUrl)) {
                    feed.iconUrl = value;
                }
                break;
        }
    }

    private void applyArticleText(ParsedArticle article, String tag, String text) {
        String value = text.trim();
        switch (tag) {
            case "title":
                article.title = appendIfNeeded(article.title, value);
                break;
            case "guid":
            case "id":
                if (isBlank(article.guid)) {
                    article.guid = value;
                }
                break;
            case "link":
                if (isBlank(article.link)) {
                    article.link = value;
                }
                break;
            case "description":
            case "summary":
            case "content":
            case "encoded":
                article.content = appendIfNeeded(article.content, value);
                break;
            case "author":
            case "creator":
            case "name":
                if (isBlank(article.author)) {
                    article.author = value;
                }
                break;
            case "pubdate":
            case "published":
            case "updated":
            case "date":
                if (article.publishedAt == 0) {
                    article.publishedAt = parseDate(value);
                }
                break;
        }
    }

    private void normalizeArticle(ParsedArticle article) {
        if (isBlank(article.title)) {
            article.title = "Untitled";
        }
        if (isBlank(article.guid)) {
            article.guid = !isBlank(article.link) ? article.link : article.title;
        }
    }

    private static String normalize(String tag) {
        if (tag == null) {
            return "";
        }
        int separator = tag.indexOf(':');
        String value = separator >= 0 ? tag.substring(separator + 1) : tag;
        return value.toLowerCase(Locale.US);
    }

    private static long parseDate(String value) {
        List<String> patterns = new ArrayList<>();
        patterns.add("EEE, dd MMM yyyy HH:mm:ss Z");
        patterns.add("EEE, d MMM yyyy HH:mm:ss Z");
        patterns.add("yyyy-MM-dd'T'HH:mm:ss'Z'");
        patterns.add("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");
        patterns.add("yyyy-MM-dd'T'HH:mm:ssXXX");
        patterns.add("yyyy-MM-dd HH:mm:ss");
        for (String pattern : patterns) {
            try {
                SimpleDateFormat format = new SimpleDateFormat(pattern, Locale.US);
                format.setTimeZone(TimeZone.getTimeZone("UTC"));
                return format.parse(value).getTime();
            } catch (ParseException ignored) {
            }
        }
        return 0;
    }

    private static String appendIfNeeded(String current, String next) {
        if (isBlank(current)) {
            return next;
        }
        if (isBlank(next) || current.contains(next)) {
            return current;
        }
        return current + "\n" + next;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private static byte[] readAllBytes(InputStream input) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int read;
        while ((read = input.read(buffer)) != -1) {
            output.write(buffer, 0, read);
        }
        return output.toByteArray();
    }

    private static String decode(byte[] content, String contentType) {
        String encoding = detectEncoding(content, contentType);
        String[] candidates = new String[]{encoding, "UTF-8", "GBK", "GB2312", "GB18030", "ISO-8859-1"};
        for (String candidate : candidates) {
            try {
                return Charset.forName(candidate)
                        .newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(java.nio.ByteBuffer.wrap(content))
                        .toString();
            } catch (CharacterCodingException | IllegalArgumentException ignored) {
            }
        }
        return new String(content, StandardCharsets.UTF_8);
    }

    private static String detectEncoding(byte[] content, String contentType) {
        if (contentType != null) {
            Matcher matcher = CHARSET_PATTERN.matcher(contentType);
            if (matcher.find()) {
                return matcher.group(1).replace("\"", "");
            }
        }
        String header = new String(content, 0, Math.min(content.length, 200), StandardCharsets.US_ASCII);
        Matcher matcher = XML_ENCODING_PATTERN.matcher(header);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return "UTF-8";
    }
}
