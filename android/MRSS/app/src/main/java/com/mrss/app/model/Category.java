package com.mrss.app.model;

public class Category {
    public long id;
    public String name;
    public String description;
    public int position;
    public int feedCount;
    public int unreadCount;

    @Override
    public String toString() {
        return unreadCount > 0 ? name + " (" + unreadCount + ")" : name;
    }
}
