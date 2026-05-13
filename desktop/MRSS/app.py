import argparse
import json
import os
import socket
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock, Thread
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


APP_NAME = "MRSS Desktop"
DB_NAME = "mrss.db"
PAGE_SIZE = 50


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        path = Path(base) / "MRSS"
    else:
        path = Path.home() / ".mrss"
    path.mkdir(parents=True, exist_ok=True)
    return path


def now_ms() -> int:
    return int(time.time() * 1000)


def truncate(value, length):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= length else text[:length]


def first_non_empty(*values):
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.lock = Lock()
        self.init_db()

    def connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT,
                    site_url TEXT,
                    icon_url TEXT,
                    fetch_interval INTEGER NOT NULL DEFAULT 3600,
                    last_fetched_at INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                    guid TEXT NOT NULL,
                    link TEXT,
                    title TEXT NOT NULL,
                    content TEXT,
                    author TEXT,
                    published_at INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    is_favorite INTEGER NOT NULL DEFAULT 0,
                    read_at INTEGER NOT NULL DEFAULT 0,
                    favorited_at INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(feed_id, guid)
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_feeds_category ON feeds(category_id);
                CREATE INDEX IF NOT EXISTS idx_articles_feed ON articles(feed_id);
                CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);
                CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(is_read);
                CREATE INDEX IF NOT EXISTS idx_articles_favorite ON articles(is_favorite);
                """
            )

    def setting(self, key, default=""):
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def categories(self):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.*,
                    (SELECT COUNT(*) FROM feeds f WHERE f.category_id = c.id) AS feed_count,
                    (SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id = a.feed_id WHERE f.category_id = c.id AND a.is_read = 0) AS unread_count
                FROM categories c
                ORDER BY c.position ASC, c.name COLLATE NOCASE ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def feeds(self):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT f.*, c.name AS category_name,
                    (SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id) AS article_count,
                    (SELECT COUNT(*) FROM articles a WHERE a.feed_id = f.id AND a.is_read = 0) AS unread_count
                FROM feeds f
                LEFT JOIN categories c ON c.id = f.category_id
                ORDER BY c.position ASC, c.name COLLATE NOCASE ASC, f.position ASC, f.title COLLATE NOCASE ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def stats(self):
        with self.connect() as conn:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_ms = int(today.timestamp() * 1000)
            seven_ms = int((today - timedelta(days=6)).timestamp() * 1000)
            return {
                "categoryCount": conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
                "feedCount": conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0],
                "activeFeedCount": conn.execute("SELECT COUNT(*) FROM feeds WHERE is_active = 1").fetchone()[0],
                "articleCount": conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
                "unreadCount": conn.execute("SELECT COUNT(*) FROM articles WHERE is_read = 0").fetchone()[0],
                "favoriteCount": conn.execute("SELECT COUNT(*) FROM articles WHERE is_favorite = 1").fetchone()[0],
                "todayCount": conn.execute("SELECT COUNT(*) FROM articles WHERE CASE WHEN published_at = 0 THEN created_at ELSE published_at END >= ?", (today_ms,)).fetchone()[0],
                "lastSevenDaysCount": conn.execute("SELECT COUNT(*) FROM articles WHERE CASE WHEN published_at = 0 THEN created_at ELSE published_at END >= ?", (seven_ms,)).fetchone()[0],
                "latestArticleAt": conn.execute("SELECT MAX(CASE WHEN published_at = 0 THEN created_at ELSE published_at END) FROM articles").fetchone()[0] or 0,
            }

    def articles(self, params):
        where = []
        args = []
        feed_id = params.get("feed_id")
        category_id = params.get("category_id")
        if feed_id:
            where.append("a.feed_id = ?")
            args.append(feed_id)
        elif category_id:
            if str(category_id) == "-1":
                where.append("f.category_id IS NULL")
            else:
                where.append("f.category_id = ?")
                args.append(category_id)
        if params.get("unread") == "1":
            where.append("a.is_read = 0")
        if params.get("favorite") == "1":
            where.append("a.is_favorite = 1")
        query = (params.get("q") or "").strip()
        if query:
            like = f"%{query}%"
            where.append("(a.title LIKE ? OR a.content LIKE ? OR f.title LIKE ?)")
            args.extend([like, like, like])
        date_filter = params.get("date")
        if date_filter and date_filter != "all":
            start, end = date_range(date_filter)
            if start:
                where.append("CASE WHEN a.published_at = 0 THEN a.created_at ELSE a.published_at END >= ?")
                args.append(start)
            if end:
                where.append("CASE WHEN a.published_at = 0 THEN a.created_at ELSE a.published_at END <= ?")
                args.append(end)
        where_sql = " WHERE " + " AND ".join(where) if where else ""
        sort_map = {"created": "a.created_at", "title": "a.title COLLATE NOCASE", "published": "a.published_at"}
        sort = sort_map.get(params.get("sort"), "a.published_at")
        direction = "ASC" if params.get("desc") == "0" else "DESC"
        limit = max(1, min(200, int(params.get("limit") or PAGE_SIZE)))
        offset = max(0, int(params.get("offset") or 0))
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM articles a JOIN feeds f ON f.id = a.feed_id{where_sql}", args).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT a.*, f.title AS feed_title
                FROM articles a JOIN feeds f ON f.id = a.feed_id
                {where_sql}
                ORDER BY {sort} {direction}, a.id DESC
                LIMIT ? OFFSET ?
                """,
                args + [limit, offset],
            ).fetchall()
            return {"total": total, "items": [dict(row) for row in rows]}

    def add_category(self, name):
        with self.lock, self.connect() as conn:
            conn.execute("INSERT INTO categories(name, created_at) VALUES(?, ?)", (name.strip(), now_ms()))

    def update_category(self, category_id, name):
        with self.lock, self.connect() as conn:
            conn.execute("UPDATE categories SET name = ?, updated_at = ? WHERE id = ?", (name.strip(), now_ms(), category_id))

    def delete_category(self, category_id):
        with self.lock, self.connect() as conn:
            conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def add_feed(self, url, category_id=None, interval=3600):
        parsed = fetch_and_parse_feed(url)
        with self.lock, self.connect() as conn:
            current = conn.execute("SELECT id FROM feeds WHERE url = ?", (url,)).fetchone()
            if current:
                feed_id = current["id"]
                self._save_articles(conn, feed_id, parsed)
                return feed_id
            ts = now_ms()
            cur = conn.execute(
                """
                INSERT INTO feeds(category_id, url, title, description, site_url, icon_url, fetch_interval, last_fetched_at, is_active, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (category_id, url, parsed["title"], parsed.get("description"), parsed.get("site_url"), parsed.get("icon_url"), interval, ts, ts),
            )
            feed_id = cur.lastrowid
            self._save_articles(conn, feed_id, parsed)
            return feed_id

    def update_feed(self, feed_id, data):
        category_id = data.get("category_id")
        if category_id in ("", 0, "0"):
            category_id = None
        active = 1 if data.get("active", True) else 0
        with self.lock, self.connect() as conn:
            conn.execute(
                "UPDATE feeds SET title = ?, category_id = ?, fetch_interval = ?, is_active = ?, updated_at = ? WHERE id = ?",
                (data.get("title") or "Untitled Feed", category_id, int(data.get("fetch_interval") or 3600), active, now_ms(), feed_id),
            )

    def delete_feed(self, feed_id):
        with self.lock, self.connect() as conn:
            conn.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))

    def refresh_feeds(self, feed_id=None, category_id=None, due_only=False):
        feeds = self.feeds()
        ts = now_ms()
        result = {"candidates": 0, "success": 0, "failed": 0, "inserted": 0}
        for feed in feeds:
            if not feed["is_active"]:
                continue
            if feed_id and feed["id"] != feed_id:
                continue
            if not feed_id and category_id:
                if str(category_id) == "-1":
                    if feed["category_id"] is not None:
                        continue
                elif feed["category_id"] != category_id:
                    continue
            if due_only and feed["last_fetched_at"] and feed["last_fetched_at"] + feed["fetch_interval"] * 1000 > ts:
                continue
            result["candidates"] += 1
            try:
                parsed = fetch_and_parse_feed(feed["url"])
                with self.lock, self.connect() as conn:
                    conn.execute(
                        """
                        UPDATE feeds SET title = ?, description = ?, site_url = ?, icon_url = ?,
                        last_fetched_at = ?, last_error = NULL, error_count = 0, updated_at = ? WHERE id = ?
                        """,
                        (parsed["title"], parsed.get("description"), parsed.get("site_url"), parsed.get("icon_url"), ts, ts, feed["id"]),
                    )
                    result["inserted"] += self._save_articles(conn, feed["id"], parsed)
                result["success"] += 1
            except Exception as exc:
                with self.lock, self.connect() as conn:
                    conn.execute(
                        "UPDATE feeds SET last_error = ?, last_fetched_at = ?, error_count = error_count + 1, updated_at = ? WHERE id = ?",
                        (str(exc), ts, ts, feed["id"]),
                    )
                result["failed"] += 1
        return result

    def mark_read(self, article_id, read=True):
        with self.lock, self.connect() as conn:
            conn.execute(
                "UPDATE articles SET is_read = ?, read_at = ? WHERE id = ?",
                (1 if read else 0, now_ms() if read else 0, article_id),
            )

    def toggle_favorite(self, article_id):
        with self.lock, self.connect() as conn:
            row = conn.execute("SELECT is_favorite FROM articles WHERE id = ?", (article_id,)).fetchone()
            next_value = 0 if row and row["is_favorite"] else 1
            conn.execute(
                "UPDATE articles SET is_favorite = ?, favorited_at = ? WHERE id = ?",
                (next_value, now_ms() if next_value else 0, article_id),
            )
            return bool(next_value)

    def mark_all_read(self, feed_id=None, category_id=None):
        where = "is_read = 0"
        args = []
        if feed_id:
            where += " AND feed_id = ?"
            args.append(feed_id)
        elif category_id:
            if str(category_id) == "-1":
                where += " AND feed_id IN (SELECT id FROM feeds WHERE category_id IS NULL)"
            else:
                where += " AND feed_id IN (SELECT id FROM feeds WHERE category_id = ?)"
                args.append(category_id)
        with self.lock, self.connect() as conn:
            cur = conn.execute(f"UPDATE articles SET is_read = 1, read_at = ? WHERE {where}", [now_ms()] + args)
            return cur.rowcount

    def export_backup(self):
        with self.connect() as conn:
            return {
                "schema_version": 1,
                "exported_at": now_ms(),
                "categories": [dict(row) for row in conn.execute("SELECT * FROM categories ORDER BY id ASC")],
                "feeds": [dict(row) for row in conn.execute("SELECT * FROM feeds ORDER BY id ASC")],
                "articles": [dict(row) for row in conn.execute("SELECT * FROM articles ORDER BY id ASC")],
            }

    def restore_backup(self, backup):
        for key in ("categories", "feeds", "articles"):
            if key not in backup:
                raise ValueError("备份文件缺少 categories / feeds / articles")
        with self.lock, self.connect() as conn:
            conn.execute("DELETE FROM articles")
            conn.execute("DELETE FROM feeds")
            conn.execute("DELETE FROM categories")
            insert_rows(conn, "categories", backup["categories"])
            insert_rows(conn, "feeds", backup["feeds"])
            insert_rows(conn, "articles", backup["articles"])

    def export_opml(self):
        feeds = self.feeds()
        root = ET.Element("opml", version="2.0")
        head = ET.SubElement(root, "head")
        ET.SubElement(head, "title").text = "MRSS Subscriptions"
        body = ET.SubElement(root, "body")
        grouped = {}
        for feed in feeds:
            grouped.setdefault(feed.get("category_name"), []).append(feed)
        for feed in grouped.get(None, []):
            add_opml_feed(body, feed)
        for category, category_feeds in grouped.items():
            if category is None:
                continue
            node = ET.SubElement(body, "outline", text=category, title=category)
            for feed in category_feeds:
                add_opml_feed(node, feed)
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def import_opml(self, content):
        feeds = parse_opml(content)
        imported = 0
        with self.lock, self.connect() as conn:
            for feed in feeds:
                if conn.execute("SELECT id FROM feeds WHERE url = ?", (feed["url"],)).fetchone():
                    continue
                category_id = None
                if feed.get("category"):
                    row = conn.execute("SELECT id FROM categories WHERE name = ?", (feed["category"],)).fetchone()
                    if row:
                        category_id = row["id"]
                    else:
                        cur = conn.execute("INSERT INTO categories(name, created_at) VALUES(?, ?)", (feed["category"], now_ms()))
                        category_id = cur.lastrowid
                conn.execute(
                    "INSERT INTO feeds(category_id, url, title, site_url, fetch_interval, is_active, created_at) VALUES(?, ?, ?, ?, 3600, 1, ?)",
                    (category_id, feed["url"], feed["title"], feed.get("site_url"), now_ms()),
                )
                imported += 1
        return imported

    def _save_articles(self, conn, feed_id, parsed):
        inserted = 0
        ts = now_ms()
        for item in parsed["articles"]:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO articles(feed_id, guid, link, title, content, author, published_at, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feed_id,
                    truncate(first_non_empty(item.get("guid"), item.get("link"), item.get("title")), 2048),
                    truncate(item.get("link"), 2048),
                    truncate(first_non_empty(item.get("title"), "Untitled"), 500),
                    item.get("content"),
                    truncate(item.get("author"), 500),
                    item.get("published_at") or 0,
                    ts,
                ),
            )
            if cur.rowcount:
                inserted += 1
        return inserted


def insert_rows(conn, table, rows):
    if not rows:
        return
    for row in rows:
        clean = {k: v for k, v in row.items()}
        columns = list(clean.keys())
        placeholders = ",".join("?" for _ in columns)
        quoted = ",".join(columns)
        conn.execute(f"INSERT INTO {table}({quoted}) VALUES({placeholders})", [clean[c] for c in columns])


def date_range(name):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if name == "today":
        return int(today.timestamp() * 1000), int((today + timedelta(days=1)).timestamp() * 1000) - 1
    if name == "yesterday":
        start = today - timedelta(days=1)
        return int(start.timestamp() * 1000), int(today.timestamp() * 1000) - 1
    if name == "7d":
        return int((today - timedelta(days=6)).timestamp() * 1000), None
    return None, None


def fetch_text(url, timeout=30):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "MRSS Desktop/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset()
        for encoding in [charset, "utf-8", "gbk", "gb18030", "latin-1"]:
            if not encoding:
                continue
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                pass
        return raw.decode("utf-8", errors="replace")


def fetch_and_parse_feed(url):
    content = fetch_text(url)
    root = ET.fromstring(content.strip())
    tag = strip_ns(root.tag).lower()
    if tag == "rss":
        return parse_rss(root)
    if tag == "feed":
        return parse_atom(root)
    raise ValueError("不支持的 RSS/Atom 格式")


def parse_rss(root):
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS 缺少 channel")
    parsed = {
        "title": text_of(channel, "title") or "Untitled Feed",
        "description": text_of(channel, "description"),
        "site_url": text_of(channel, "link"),
        "icon_url": None,
        "articles": [],
    }
    image = channel.find("image")
    if image is not None:
        parsed["icon_url"] = text_of(image, "url")
    for item in channel.findall("item"):
        parsed["articles"].append({
            "guid": text_of(item, "guid") or text_of(item, "link") or text_of(item, "title"),
            "title": text_of(item, "title") or "Untitled",
            "link": text_of(item, "link"),
            "content": first_non_empty(text_of(item, "content:encoded"), text_of(item, "description")),
            "author": first_non_empty(text_of(item, "author"), text_of(item, "dc:creator")),
            "published_at": parse_date_ms(first_non_empty(text_of(item, "pubDate"), text_of(item, "date"))),
        })
    return parsed


def parse_atom(root):
    parsed = {
        "title": text_of(root, "title") or "Untitled Feed",
        "description": text_of(root, "subtitle"),
        "site_url": atom_link(root),
        "icon_url": text_of(root, "icon"),
        "articles": [],
    }
    for entry in children_by_name(root, "entry"):
        parsed["articles"].append({
            "guid": text_of(entry, "id") or atom_link(entry) or text_of(entry, "title"),
            "title": text_of(entry, "title") or "Untitled",
            "link": atom_link(entry),
            "content": first_non_empty(text_of(entry, "content"), text_of(entry, "summary")),
            "author": atom_author(entry),
            "published_at": parse_date_ms(first_non_empty(text_of(entry, "published"), text_of(entry, "updated"))),
        })
    return parsed


def strip_ns(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def children_by_name(element, name):
    return [child for child in list(element) if strip_ns(child.tag) == name or child.tag == name]


def text_of(element, name):
    for child in list(element):
        if strip_ns(child.tag) == name or child.tag == name:
            return "".join(child.itertext()).strip()
    return None


def atom_link(element):
    fallback = None
    for child in children_by_name(element, "link"):
        href = child.attrib.get("href")
        if not href:
            continue
        if child.attrib.get("rel") in (None, "", "alternate"):
            return href
        fallback = fallback or href
    return fallback


def atom_author(element):
    for author in children_by_name(element, "author"):
        name = text_of(author, "name")
        if name:
            return name
    return None


def parse_date_ms(value):
    if not value:
        return 0
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(value)
        return int(dt.timestamp() * 1000)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def parse_opml(content):
    root = ET.fromstring(content)
    body = root.find("body")
    if body is None:
        raise ValueError("OPML 缺少 body")
    feeds = []
    walk_opml(body, feeds, None)
    return feeds


def walk_opml(node, feeds, category):
    for child in node.findall("outline"):
        xml_url = child.attrib.get("xmlUrl")
        title = child.attrib.get("title") or child.attrib.get("text") or "Untitled"
        if xml_url:
            feeds.append({"title": title, "url": xml_url, "site_url": child.attrib.get("htmlUrl"), "category": category})
        else:
            walk_opml(child, feeds, title or category)


def add_opml_feed(parent, feed):
    attrs = {
        "type": "rss",
        "text": feed.get("title") or "Untitled",
        "title": feed.get("title") or "Untitled",
        "xmlUrl": feed.get("url") or "",
    }
    if feed.get("site_url"):
        attrs["htmlUrl"] = feed["site_url"]
    ET.SubElement(parent, "outline", attrs)


class APIHandler(SimpleHTTPRequestHandler):
    repo: Repository = None
    static_dir: Path = None

    def log_message(self, format, *args):
        return

    def translate_path(self, path):
        if path == "/" or not path.startswith("/api/"):
            clean = urllib.parse.urlparse(path).path
            if clean == "/":
                clean = "/index.html"
            return str(self.static_dir / clean.lstrip("/"))
        return super().translate_path(path)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        try:
            if parsed.path == "/api/summary":
                return self.json({"categories": self.repo.categories(), "feeds": self.repo.feeds(), "stats": self.repo.stats()})
            if parsed.path == "/api/articles":
                return self.json(self.repo.articles(params))
            if parsed.path == "/api/backup/export":
                return self.json(self.repo.export_backup())
            if parsed.path == "/api/opml/export":
                return self.text(self.repo.export_opml(), "text/xml; charset=utf-8")
            return super().do_GET()
        except Exception as exc:
            self.error(exc)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        data = self.read_json()
        try:
            if parsed.path == "/api/categories":
                self.repo.add_category(data["name"])
                return self.json({"ok": True})
            if parsed.path.startswith("/api/categories/"):
                category_id = int(parsed.path.rsplit("/", 1)[-1])
                self.repo.update_category(category_id, data["name"])
                return self.json({"ok": True})
            if parsed.path == "/api/feeds":
                feed_id = self.repo.add_feed(data["url"], data.get("category_id"), int(data.get("fetch_interval") or 3600))
                return self.json({"ok": True, "id": feed_id})
            if parsed.path.startswith("/api/feeds/"):
                feed_id = int(parsed.path.rsplit("/", 1)[-1])
                self.repo.update_feed(feed_id, data)
                return self.json({"ok": True})
            if parsed.path == "/api/refresh":
                return self.json(self.repo.refresh_feeds(data.get("feed_id"), data.get("category_id"), bool(data.get("due_only"))))
            if parsed.path.startswith("/api/articles/") and parsed.path.endswith("/read"):
                article_id = int(parsed.path.split("/")[3])
                self.repo.mark_read(article_id, bool(data.get("read", True)))
                return self.json({"ok": True})
            if parsed.path.startswith("/api/articles/") and parsed.path.endswith("/favorite"):
                article_id = int(parsed.path.split("/")[3])
                return self.json({"favorite": self.repo.toggle_favorite(article_id)})
            if parsed.path == "/api/articles/mark-all-read":
                return self.json({"count": self.repo.mark_all_read(data.get("feed_id"), data.get("category_id"))})
            if parsed.path == "/api/backup/restore":
                self.repo.restore_backup(data)
                return self.json({"ok": True})
            if parsed.path == "/api/opml/import":
                return self.json({"imported": self.repo.import_opml(data.get("content") or "")})
            if parsed.path == "/api/gist/push":
                return self.json(gist_push(self.repo, data))
            if parsed.path == "/api/gist/pull":
                backup = gist_pull(data)
                self.repo.restore_backup(backup)
                return self.json({"ok": True})
            if parsed.path == "/api/settings/github":
                for key in ("github_token", "gist_id", "gist_filename"):
                    if key in data:
                        self.repo.set_setting(key, data.get(key) or "")
                return self.json({"ok": True})
            self.send_error(404)
        except Exception as exc:
            self.error(exc)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path.startswith("/api/categories/"):
                self.repo.delete_category(int(parsed.path.rsplit("/", 1)[-1]))
                return self.json({"ok": True})
            if parsed.path.startswith("/api/feeds/"):
                self.repo.delete_feed(int(parsed.path.rsplit("/", 1)[-1]))
                return self.json({"ok": True})
            self.send_error(404)
        except Exception as exc:
            self.error(exc)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def text(self, text, content_type):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def error(self, exc):
        self.json({"error": str(exc)}, status=500)


def gist_push(repo, data):
    token = data.get("token") or repo.setting("github_token")
    gist_id = data.get("gist_id") or repo.setting("gist_id")
    filename = data.get("filename") or repo.setting("gist_filename", "mrss-backup.json") or "mrss-backup.json"
    if not token:
        raise ValueError("缺少 GitHub Token")
    payload = {"files": {filename: {"content": json.dumps(repo.export_backup(), ensure_ascii=False, indent=2)}}}
    if gist_id:
        request = github_request(f"https://api.github.com/gists/{gist_id}", token, "PATCH", payload)
    else:
        payload["description"] = "MRSS backup"
        payload["public"] = False
        request = github_request("https://api.github.com/gists", token, "POST", payload)
    repo.set_setting("github_token", token)
    repo.set_setting("gist_id", request["id"])
    repo.set_setting("gist_filename", filename)
    return {"ok": True, "gist_id": request["id"], "url": request.get("html_url")}


def gist_pull(data):
    token = data.get("token")
    gist_id = data.get("gist_id")
    filename = data.get("filename") or "mrss-backup.json"
    if not token or not gist_id:
        raise ValueError("缺少 GitHub Token 或 Gist ID")
    gist = github_request(f"https://api.github.com/gists/{gist_id}", token, "GET")
    files = gist.get("files") or {}
    if filename not in files:
        raise ValueError(f"Gist 中没有文件 {filename}")
    content = files[filename].get("content")
    if content is None and files[filename].get("raw_url"):
        content = fetch_text(files[filename]["raw_url"])
    return json.loads(content)


def github_request(url, token, method, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"GitHub 请求失败：{exc.code} {detail}")


def run_scheduler(repo):
    while True:
        try:
            repo.refresh_feeds(due_only=True)
        except Exception:
            pass
        time.sleep(60)


def find_free_port(start_port):
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise OSError("没有找到可用端口")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).parent.resolve()
    repo = Repository(app_data_dir() / DB_NAME)
    APIHandler.repo = repo
    APIHandler.static_dir = root / "static"
    Thread(target=run_scheduler, args=(repo,), daemon=True).start()
    port = find_free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    if not args.no_browser:
        Thread(target=lambda: (time.sleep(0.8), webbrowser.open(url)), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), APIHandler)
    print(f"{APP_NAME} running at {url}")
    print(f"Data: {app_data_dir()}")
    server.serve_forever()


if __name__ == "__main__":
    main()
