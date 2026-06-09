package com.mrss.mobile.api;

import org.json.JSONException;
import org.json.JSONObject;

public final class JsonUtils {
    private JsonUtils() {
    }

    public static String optString(JSONObject object, String name) {
        if (object == null || object.isNull(name)) {
            return null;
        }
        return object.optString(name, null);
    }

    public static Long optLongObject(JSONObject object, String name) {
        if (object == null || object.isNull(name)) {
            return null;
        }
        return object.optLong(name);
    }

    public static boolean hasNonEmpty(JSONObject object, String name) {
        return object != null && !object.isNull(name) && !object.optString(name, "").trim().isEmpty();
    }

    public static JSONObject parseObject(String body) throws JSONException {
        return new JSONObject(body == null ? "{}" : body);
    }
}
