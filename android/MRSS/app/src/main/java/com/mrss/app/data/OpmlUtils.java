package com.mrss.app.data;

import android.util.Xml;

import com.mrss.app.model.Feed;
import com.mrss.app.model.OpmlFeed;

import org.xmlpull.v1.XmlPullParser;
import org.xmlpull.v1.XmlSerializer;

import java.io.StringReader;
import java.io.StringWriter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class OpmlUtils {
    private OpmlUtils() {
    }

    public static List<OpmlFeed> parse(String content) throws Exception {
        XmlPullParser parser = Xml.newPullParser();
        parser.setInput(new StringReader(content));
        List<OpmlFeed> feeds = new ArrayList<>();
        List<String> categoryStack = new ArrayList<>();
        List<Boolean> outlineStack = new ArrayList<>();

        int event = parser.getEventType();
        while (event != XmlPullParser.END_DOCUMENT) {
            if (event == XmlPullParser.START_TAG && "outline".equalsIgnoreCase(parser.getName())) {
                String xmlUrl = parser.getAttributeValue(null, "xmlUrl");
                if (xmlUrl == null) {
                    xmlUrl = parser.getAttributeValue(null, "xmlurl");
                }
                String title = firstNonEmpty(
                        parser.getAttributeValue(null, "title"),
                        parser.getAttributeValue(null, "text"),
                        "Untitled"
                );
                if (xmlUrl != null && !xmlUrl.trim().isEmpty()) {
                    outlineStack.add(false);
                    OpmlFeed feed = new OpmlFeed();
                    feed.title = title;
                    feed.url = xmlUrl.trim();
                    feed.siteUrl = parser.getAttributeValue(null, "htmlUrl");
                    feed.category = categoryStack.isEmpty() ? null : categoryStack.get(categoryStack.size() - 1);
                    feeds.add(feed);
                } else {
                    outlineStack.add(true);
                    categoryStack.add(title);
                }
            } else if (event == XmlPullParser.END_TAG && "outline".equalsIgnoreCase(parser.getName())) {
                boolean categoryOutline = !outlineStack.isEmpty() && outlineStack.remove(outlineStack.size() - 1);
                if (categoryOutline && !categoryStack.isEmpty()) {
                    categoryStack.remove(categoryStack.size() - 1);
                }
            }
            event = parser.next();
        }
        return feeds;
    }

    public static String generate(List<Feed> feeds) throws Exception {
        StringWriter writer = new StringWriter();
        XmlSerializer serializer = Xml.newSerializer();
        serializer.setOutput(writer);
        serializer.startDocument("UTF-8", true);
        serializer.startTag(null, "opml");
        serializer.attribute(null, "version", "2.0");
        serializer.startTag(null, "head");
        serializer.startTag(null, "title");
        serializer.text("MRSS Subscriptions");
        serializer.endTag(null, "title");
        serializer.endTag(null, "head");
        serializer.startTag(null, "body");

        Map<String, List<Feed>> grouped = new LinkedHashMap<>();
        grouped.put("", new ArrayList<>());
        for (Feed feed : feeds) {
            String category = feed.categoryName == null ? "" : feed.categoryName;
            if (!grouped.containsKey(category)) {
                grouped.put(category, new ArrayList<>());
            }
            grouped.get(category).add(feed);
        }

        for (Feed feed : grouped.get("")) {
            writeFeed(serializer, feed);
        }
        for (Map.Entry<String, List<Feed>> entry : grouped.entrySet()) {
            if (entry.getKey().isEmpty()) {
                continue;
            }
            serializer.startTag(null, "outline");
            serializer.attribute(null, "text", entry.getKey());
            serializer.attribute(null, "title", entry.getKey());
            for (Feed feed : entry.getValue()) {
                writeFeed(serializer, feed);
            }
            serializer.endTag(null, "outline");
        }

        serializer.endTag(null, "body");
        serializer.endTag(null, "opml");
        serializer.endDocument();
        return writer.toString();
    }

    private static void writeFeed(XmlSerializer serializer, Feed feed) throws Exception {
        serializer.startTag(null, "outline");
        serializer.attribute(null, "type", "rss");
        serializer.attribute(null, "text", firstNonEmpty(feed.title, feed.url, "Untitled"));
        serializer.attribute(null, "title", firstNonEmpty(feed.title, feed.url, "Untitled"));
        serializer.attribute(null, "xmlUrl", feed.url);
        if (feed.siteUrl != null && !feed.siteUrl.trim().isEmpty()) {
            serializer.attribute(null, "htmlUrl", feed.siteUrl);
        }
        serializer.endTag(null, "outline");
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) {
                return value.trim();
            }
        }
        return "";
    }
}
