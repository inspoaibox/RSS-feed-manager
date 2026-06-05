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
        String type = provider == null || provider.trim().isEmpty() ? "openai" : provider;
        return (name == null || name.trim().isEmpty() ? "AI Channel" : name) + " · " + type + (isDefault ? " · default" : "");
    }
}
