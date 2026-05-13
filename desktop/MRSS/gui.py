import html
import json
import queue
import re
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from app import DB_NAME, PAGE_SIZE, Repository, app_data_dir, gist_pull, gist_push


APP_TITLE = "MRSS"
DEFAULT_INTERVAL_SECONDS = 3600


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def ms_to_text(value) -> str:
    try:
        value = int(value or 0)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        return "-"
    return datetime.fromtimestamp(value / 1000).strftime("%Y/%m/%d %H:%M")


def strip_markup(value) -> str:
    text = value or ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def compact(value, length=160) -> str:
    text = strip_markup(value)
    return text if len(text) <= length else text[: length - 1] + "..."


class MRSSWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.repo = Repository(app_data_dir() / DB_NAME)
        self.events = queue.Queue()
        self.stop_event = threading.Event()

        self.categories = []
        self.feeds = []
        self.category_by_id = {}
        self.feed_by_id = {}
        self.article_by_item = {}
        self.scope_key = "all"
        self.offset = 0
        self.loaded_count = 0
        self.total_count = 0

        self.search_var = tk.StringVar()
        self.unread_var = tk.BooleanVar(value=False)
        self.favorite_var = tk.BooleanVar(value=False)
        self.desc_var = tk.BooleanVar(value=True)
        self.sort_var = tk.StringVar(value="发布时间")
        self.date_var = tk.StringVar(value="全部日期")
        self.scope_title_var = tk.StringVar(value="全部文章")
        self.status_var = tk.StringVar(value="就绪")

        self.configure_root()
        self.build_ui()
        self.refresh_summary()
        self.load_articles()

        self.root.after(150, self.drain_events)
        self.root.after(600, self.startup_refresh)
        threading.Thread(target=self.scheduler_loop, daemon=True).start()

    def configure_root(self):
        self.root.title(APP_TITLE)
        self.root.geometry("1240x780")
        self.root.minsize(980, 640)
        icon = resource_path("mrss.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=30, font=("Microsoft YaHei UI", 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TButton", padding=(10, 6))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("Muted.TLabel", foreground="#667085")

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew")

        sidebar = ttk.Frame(paned, padding=(12, 12, 8, 12))
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(1, weight=1)
        paned.add(sidebar, weight=0)

        logo_row = ttk.Frame(sidebar)
        logo_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        logo_row.columnconfigure(1, weight=1)
        ttk.Label(logo_row, text="MRSS", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(logo_row, text="新建分类", command=self.add_category).grid(row=0, column=1, sticky="e")

        self.nav = ttk.Treeview(sidebar, show="tree", selectmode="browse")
        self.nav.grid(row=1, column=0, sticky="nsew")
        self.nav.tag_configure("muted", foreground="#8a8f98")
        self.nav.bind("<<TreeviewSelect>>", self.on_nav_select)
        self.nav.bind("<Button-3>", self.on_nav_menu)
        self.nav.bind("<Double-1>", self.on_nav_double_click)

        content = ttk.Frame(paned, padding=(12, 12, 12, 12))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(3, weight=1)
        paned.add(content, weight=1)

        toolbar = ttk.Frame(content)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(toolbar, textvariable=self.scope_title_var, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(toolbar, text="添加", command=self.add_feed).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(toolbar, text="刷新", command=self.refresh_current).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(toolbar, text="全部已读", command=self.mark_all_read).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(toolbar, text="备份/导入", command=self.show_backup_menu).grid(row=0, column=4, padx=(8, 0))
        ttk.Button(toolbar, text="OPML", command=self.show_opml_menu).grid(row=0, column=5, padx=(8, 0))
        ttk.Button(toolbar, text="GitHub Gist", command=self.show_gist_menu).grid(row=0, column=6, padx=(8, 0))

        filters = ttk.Frame(content)
        filters.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        filters.columnconfigure(0, weight=1)
        search = ttk.Entry(filters, textvariable=self.search_var)
        search.grid(row=0, column=0, sticky="ew")
        search.bind("<Return>", lambda _event: self.apply_filters())
        ttk.Button(filters, text="搜索", command=self.apply_filters).grid(row=0, column=1, padx=(8, 0))
        ttk.Checkbutton(filters, text="未读", variable=self.unread_var, command=self.apply_filters).grid(row=0, column=2, padx=(12, 0))
        ttk.Checkbutton(filters, text="收藏", variable=self.favorite_var, command=self.apply_filters).grid(row=0, column=3, padx=(8, 0))
        ttk.Checkbutton(filters, text="降序", variable=self.desc_var, command=self.apply_filters).grid(row=0, column=4, padx=(8, 0))

        filter_row_2 = ttk.Frame(content)
        filter_row_2.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(filter_row_2, text="排序").grid(row=0, column=0, sticky="w")
        sort_box = ttk.Combobox(filter_row_2, textvariable=self.sort_var, values=("发布时间", "创建时间", "标题"), state="readonly", width=12)
        sort_box.grid(row=0, column=1, padx=(6, 18))
        sort_box.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())
        ttk.Label(filter_row_2, text="日期").grid(row=0, column=2, sticky="w")
        date_box = ttk.Combobox(filter_row_2, textvariable=self.date_var, values=("全部日期", "今天", "昨天", "最近 7 天"), state="readonly", width=12)
        date_box.grid(row=0, column=3, padx=(6, 18))
        date_box.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())

        self.articles = ttk.Treeview(
            content,
            columns=("title", "source", "time", "author"),
            show="headings",
            selectmode="browse",
        )
        self.articles.heading("title", text="标题")
        self.articles.heading("source", text="订阅源")
        self.articles.heading("time", text="发布时间")
        self.articles.heading("author", text="作者")
        self.articles.column("title", minwidth=320, width=580, stretch=True)
        self.articles.column("source", minwidth=120, width=170, stretch=False)
        self.articles.column("time", minwidth=130, width=145, stretch=False)
        self.articles.column("author", minwidth=90, width=120, stretch=False)
        self.articles.tag_configure("read", foreground="#7a7f87")
        self.articles.grid(row=3, column=0, sticky="nsew")
        self.articles.bind("<Double-1>", self.open_selected_article)
        self.articles.bind("<Button-3>", self.on_article_menu)

        article_scroll = ttk.Scrollbar(content, orient=tk.VERTICAL, command=self.articles.yview)
        article_scroll.grid(row=3, column=1, sticky="ns")
        self.articles.configure(yscrollcommand=article_scroll.set)

        bottom = ttk.Frame(content)
        bottom.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="加载更多", command=self.load_more).grid(row=0, column=1, sticky="e")

    def drain_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "done":
                _, label, result, callback = event
                if callback:
                    callback(result)
                else:
                    self.set_status(f"{label}完成")
            elif kind == "error":
                _, label, message = event
                self.set_status(f"{label}失败")
                messagebox.showerror(APP_TITLE, f"{label}失败：\n{message}")
            elif kind == "status":
                self.set_status(event[1])
        if not self.stop_event.is_set():
            self.root.after(150, self.drain_events)

    def run_background(self, label, worker, callback=None):
        self.set_status(label)

        def target():
            try:
                result = worker()
            except Exception as exc:
                self.events.put(("error", label, str(exc)))
            else:
                self.events.put(("done", label, result, callback))

        threading.Thread(target=target, daemon=True).start()

    def scheduler_loop(self):
        while not self.stop_event.wait(60):
            try:
                result = self.repo.refresh_feeds(due_only=True)
            except Exception:
                continue
            if result.get("inserted"):
                self.events.put(("status", f"后台同步新增 {result['inserted']} 篇文章"))
                self.events.put(("done", "后台同步", result, lambda _result: self.reload_current_view()))

    def startup_refresh(self):
        if self.feeds:
            self.run_background("启动后同步全部订阅中...", self.repo.refresh_feeds, self.after_startup_refresh)

    def close(self):
        self.stop_event.set()
        self.root.destroy()

    def set_status(self, text):
        self.status_var.set(text)

    def refresh_summary(self, select_key=None):
        self.categories = self.repo.categories()
        self.feeds = self.repo.feeds()
        self.category_by_id = {int(item["id"]): item for item in self.categories}
        self.feed_by_id = {int(item["id"]): item for item in self.feeds}

        current = select_key or self.scope_key
        self.nav.delete(*self.nav.get_children(""))
        stats = self.repo.stats()
        self.nav.insert("", "end", iid="all", text=f"全部文章 ({stats['unreadCount']} 未读)", open=True)

        feeds_by_category = {}
        for feed in self.feeds:
            feeds_by_category.setdefault(feed.get("category_id"), []).append(feed)

        for category in self.categories:
            key = f"cat:{category['id']}"
            text = f"{category['name']} ({category['unread_count']} 未读)"
            self.nav.insert("", "end", iid=key, text=text, open=True)
            for feed in feeds_by_category.pop(category["id"], []):
                self.insert_feed_node(key, feed)

        ungrouped = feeds_by_category.pop(None, []) + feeds_by_category.pop(0, [])
        if ungrouped:
            self.nav.insert("", "end", iid="cat:none", text="未分类", open=True)
            for feed in ungrouped:
                self.insert_feed_node("cat:none", feed)

        if self.nav.exists(current):
            self.nav.selection_set(current)
        else:
            self.scope_key = "all"
            self.nav.selection_set("all")
        self.update_scope_title()

    def insert_feed_node(self, parent, feed):
        key = f"feed:{feed['id']}"
        title = feed["title"] or feed["url"]
        prefix = "" if feed.get("is_active") else "[停用] "
        text = f"{prefix}{title} ({feed['unread_count']} 未读)"
        tags = () if feed.get("is_active") else ("muted",)
        self.nav.insert(parent, "end", iid=key, text=text, tags=tags)

    def on_nav_select(self, _event=None):
        selection = self.nav.selection()
        if not selection:
            return
        key = selection[0]
        if key == self.scope_key:
            return
        self.scope_key = key
        self.update_scope_title()
        self.offset = 0
        self.load_articles()

    def on_nav_double_click(self, _event=None):
        key = self.selected_nav_key()
        if key and key.startswith("feed:"):
            feed = self.feed_by_id.get(self.id_from_key(key))
            if feed and feed.get("site_url"):
                webbrowser.open(feed["site_url"])

    def selected_nav_key(self):
        selection = self.nav.selection()
        return selection[0] if selection else self.scope_key

    def update_scope_title(self):
        key = self.scope_key
        if key == "all":
            title = "全部文章"
        elif key == "cat:none":
            title = "未分类"
        elif key.startswith("cat:"):
            category = self.category_by_id.get(self.id_from_key(key))
            title = category["name"] if category else "分类"
        elif key.startswith("feed:"):
            feed = self.feed_by_id.get(self.id_from_key(key))
            title = feed["title"] if feed else "订阅源"
        else:
            title = "全部文章"
        self.scope_title_var.set(title)

    def id_from_key(self, key):
        try:
            return int(key.split(":", 1)[1])
        except (TypeError, ValueError, IndexError):
            return None

    def article_params(self):
        sort_map = {"发布时间": "published", "创建时间": "created", "标题": "title"}
        date_map = {"全部日期": "all", "今天": "today", "昨天": "yesterday", "最近 7 天": "7d"}
        params = {
            "limit": str(PAGE_SIZE),
            "offset": str(self.offset),
            "q": self.search_var.get().strip(),
            "unread": "1" if self.unread_var.get() else "0",
            "favorite": "1" if self.favorite_var.get() else "0",
            "desc": "1" if self.desc_var.get() else "0",
            "sort": sort_map.get(self.sort_var.get(), "published"),
            "date": date_map.get(self.date_var.get(), "all"),
        }
        key = self.scope_key
        if key.startswith("feed:"):
            params["feed_id"] = str(self.id_from_key(key))
        elif key.startswith("cat:") and key != "cat:none":
            params["category_id"] = str(self.id_from_key(key))
        elif key == "cat:none":
            params["category_id"] = "-1"
        return params

    def load_articles(self, append=False):
        if not append:
            self.offset = 0
            self.loaded_count = 0
            self.article_by_item.clear()
            self.articles.delete(*self.articles.get_children(""))
        result = self.repo.articles(self.article_params())
        self.total_count = result["total"]
        for article in result["items"]:
            item_id = self.articles.insert(
                "",
                "end",
                values=(
                    article["title"],
                    article.get("feed_title") or "",
                    ms_to_text(article.get("published_at") or article.get("created_at")),
                    article.get("author") or "",
                ),
                tags=("read",) if article.get("is_read") else (),
            )
            self.article_by_item[item_id] = article
            self.loaded_count += 1
        self.offset = self.loaded_count
        self.set_status(f"已显示 {self.loaded_count} / {self.total_count} 篇")

    def reload_current_view(self):
        self.refresh_summary()
        self.load_articles()

    def load_more(self):
        if self.loaded_count >= self.total_count:
            self.set_status("没有更多文章")
            return
        self.load_articles(append=True)

    def apply_filters(self):
        self.offset = 0
        self.load_articles()

    def selected_article(self):
        selection = self.articles.selection()
        if not selection:
            return None
        return self.article_by_item.get(selection[0])

    def open_selected_article(self, _event=None):
        article = self.selected_article()
        if not article:
            return
        self.repo.mark_read(article["id"], True)
        article["is_read"] = 1
        self.show_article_window(article)
        self.reload_current_view()

    def show_article_window(self, article):
        window = tk.Toplevel(self.root)
        window.title(article["title"] or "文章")
        window.geometry("820x640")
        window.minsize(640, 460)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(2, weight=1)

        title = ttk.Label(window, text=article["title"], font=("Microsoft YaHei UI", 15, "bold"), wraplength=760)
        title.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        meta = f"{article.get('feed_title') or ''} · {ms_to_text(article.get('published_at') or article.get('created_at'))}"
        if article.get("author"):
            meta += f" · {article['author']}"
        ttk.Label(window, text=meta, style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        body = ScrolledText(window, wrap=tk.WORD, font=("Microsoft YaHei UI", 10), padx=12, pady=12)
        body.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 10))
        body.insert("1.0", strip_markup(article.get("content")) or compact(article.get("title"), 200))
        body.configure(state=tk.DISABLED)

        actions = ttk.Frame(window)
        actions.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 16))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="打开原文", command=lambda: self.open_article_link(article)).grid(row=0, column=1, padx=(8, 0))
        fav_text = "取消收藏" if article.get("is_favorite") else "收藏"
        ttk.Button(actions, text=fav_text, command=lambda: self.toggle_article_favorite(article, window)).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(actions, text="标为未读", command=lambda: self.mark_article_unread(article, window)).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(actions, text="关闭", command=window.destroy).grid(row=0, column=4, padx=(8, 0))

    def open_article_link(self, article):
        if article.get("link"):
            webbrowser.open(article["link"])
        else:
            messagebox.showinfo(APP_TITLE, "这篇文章没有原文链接。")

    def toggle_article_favorite(self, article, window=None):
        self.repo.toggle_favorite(article["id"])
        self.reload_current_view()
        if window:
            window.destroy()

    def mark_article_unread(self, article, window=None):
        self.repo.mark_read(article["id"], False)
        self.reload_current_view()
        if window:
            window.destroy()

    def on_article_menu(self, event):
        item = self.articles.identify_row(event.y)
        if not item:
            return
        self.articles.selection_set(item)
        article = self.article_by_item.get(item)
        if not article:
            return
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="打开", command=self.open_selected_article)
        menu.add_command(label="打开原文", command=lambda: self.open_article_link(article))
        menu.add_separator()
        menu.add_command(label="标为未读", command=lambda: self.mark_article_unread(article))
        menu.add_command(label="切换收藏", command=lambda: self.toggle_article_favorite(article))
        menu.tk_popup(event.x_root, event.y_root)

    def on_nav_menu(self, event):
        item = self.nav.identify_row(event.y)
        if item:
            self.nav.selection_set(item)
            self.scope_key = item
            self.update_scope_title()
        key = self.selected_nav_key()
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="添加订阅", command=self.add_feed)
        menu.add_command(label="新建分类", command=self.add_category)
        menu.add_separator()
        if key == "cat:none":
            menu.add_command(label="刷新未分类", command=self.refresh_current)
        elif key.startswith("cat:"):
            menu.add_command(label="重命名分类", command=lambda: self.rename_category(self.id_from_key(key)))
            menu.add_command(label="删除分类", command=lambda: self.delete_category(self.id_from_key(key)))
            menu.add_separator()
            menu.add_command(label="刷新此分类", command=self.refresh_current)
        elif key.startswith("feed:"):
            feed_id = self.id_from_key(key)
            menu.add_command(label="重命名订阅", command=lambda: self.rename_feed(feed_id))
            menu.add_command(label="移动到分类", command=lambda: self.move_feed(feed_id))
            menu.add_command(label="修改同步间隔", command=lambda: self.change_feed_interval(feed_id))
            feed = self.feed_by_id.get(feed_id)
            if feed:
                label = "停用订阅" if feed.get("is_active") else "启用订阅"
                menu.add_command(label=label, command=lambda: self.toggle_feed_active(feed_id))
            menu.add_command(label="删除订阅", command=lambda: self.delete_feed(feed_id))
            menu.add_separator()
            menu.add_command(label="刷新此订阅", command=self.refresh_current)
        else:
            menu.add_command(label="刷新全部", command=self.refresh_current)
        menu.tk_popup(event.x_root, event.y_root)

    def add_category(self):
        name = simpledialog.askstring(APP_TITLE, "分类名称：", parent=self.root)
        if not name:
            return
        try:
            self.repo.add_category(name.strip())
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.refresh_summary()

    def rename_category(self, category_id):
        category = self.category_by_id.get(category_id)
        if not category:
            return
        name = simpledialog.askstring(APP_TITLE, "新的分类名称：", initialvalue=category["name"], parent=self.root)
        if not name:
            return
        try:
            self.repo.update_category(category_id, name.strip())
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.refresh_summary(f"cat:{category_id}")

    def delete_category(self, category_id):
        category = self.category_by_id.get(category_id)
        if not category:
            return
        if not messagebox.askyesno(APP_TITLE, f"删除分类“{category['name']}”？订阅会移到未分类。"):
            return
        self.repo.delete_category(category_id)
        self.scope_key = "all"
        self.reload_current_view()

    def current_category_id(self):
        key = self.scope_key
        if key.startswith("cat:") and key != "cat:none":
            return self.id_from_key(key)
        if key.startswith("feed:"):
            feed = self.feed_by_id.get(self.id_from_key(key))
            return feed.get("category_id") if feed else None
        return None

    def add_feed(self):
        url = simpledialog.askstring(APP_TITLE, "RSS/Atom 链接：", parent=self.root)
        if not url:
            return
        interval_minutes = simpledialog.askinteger(
            APP_TITLE,
            "同步间隔（分钟）：",
            initialvalue=60,
            minvalue=5,
            maxvalue=10080,
            parent=self.root,
        )
        if interval_minutes is None:
            return
        category_id = self.current_category_id()

        def work():
            return self.repo.add_feed(url.strip(), category_id=category_id, interval=interval_minutes * 60)

        self.run_background("正在添加订阅并抓取文章...", work, lambda _feed_id: self.after_add_feed())

    def after_add_feed(self):
        self.reload_current_view()
        messagebox.showinfo(APP_TITLE, "订阅已添加。")

    def rename_feed(self, feed_id):
        feed = self.feed_by_id.get(feed_id)
        if not feed:
            return
        title = simpledialog.askstring(APP_TITLE, "新的订阅名称：", initialvalue=feed["title"], parent=self.root)
        if not title:
            return
        self.repo.update_feed(feed_id, {**feed, "title": title.strip(), "active": bool(feed["is_active"])})
        self.refresh_summary(f"feed:{feed_id}")
        self.load_articles()

    def move_feed(self, feed_id):
        feed = self.feed_by_id.get(feed_id)
        if not feed:
            return
        choice = simpledialog.askstring(APP_TITLE, "移动到分类（可填已有分类名称，留空为未分类）：", parent=self.root)
        if choice is None:
            return
        choice = choice.strip()
        category_id = None
        if choice:
            matched = next((item for item in self.categories if item["name"] == choice), None)
            if matched:
                category_id = matched["id"]
            else:
                if not messagebox.askyesno(APP_TITLE, f"分类“{choice}”不存在，是否新建？"):
                    return
                self.repo.add_category(choice)
                self.refresh_summary()
                matched = next((item for item in self.categories if item["name"] == choice), None)
                category_id = matched["id"] if matched else None
        self.repo.update_feed(feed_id, {**feed, "category_id": category_id, "active": bool(feed["is_active"])})
        self.refresh_summary(f"feed:{feed_id}")

    def change_feed_interval(self, feed_id):
        feed = self.feed_by_id.get(feed_id)
        if not feed:
            return
        minutes = simpledialog.askinteger(
            APP_TITLE,
            "同步间隔（分钟）：",
            initialvalue=max(5, int(feed.get("fetch_interval") or DEFAULT_INTERVAL_SECONDS) // 60),
            minvalue=5,
            maxvalue=10080,
            parent=self.root,
        )
        if minutes is None:
            return
        self.repo.update_feed(feed_id, {**feed, "fetch_interval": minutes * 60, "active": bool(feed["is_active"])})
        self.refresh_summary(f"feed:{feed_id}")

    def toggle_feed_active(self, feed_id):
        feed = self.feed_by_id.get(feed_id)
        if not feed:
            return
        self.repo.update_feed(feed_id, {**feed, "active": not bool(feed["is_active"])})
        self.refresh_summary(f"feed:{feed_id}")

    def delete_feed(self, feed_id):
        feed = self.feed_by_id.get(feed_id)
        if not feed:
            return
        if not messagebox.askyesno(APP_TITLE, f"删除订阅“{feed['title']}”？对应文章也会删除。"):
            return
        self.repo.delete_feed(feed_id)
        self.scope_key = "all"
        self.reload_current_view()

    def refresh_current(self):
        key = self.scope_key
        if key.startswith("feed:"):
            feed_id = self.id_from_key(key)
            work = lambda: self.repo.refresh_feeds(feed_id=feed_id)
            label = "正在刷新订阅..."
        elif key == "cat:none":
            work = lambda: self.repo.refresh_feeds(category_id=-1)
            label = "正在刷新未分类订阅..."
        elif key.startswith("cat:"):
            category_id = self.id_from_key(key)
            work = lambda: self.repo.refresh_feeds(category_id=category_id)
            label = "正在刷新分类..."
        else:
            work = self.repo.refresh_feeds
            label = "正在刷新全部订阅..."
        self.run_background(label, work, self.after_refresh)

    def after_refresh(self, result):
        self.reload_current_view()
        messagebox.showinfo(
            APP_TITLE,
            f"刷新完成。\n成功 {result.get('success', 0)} 个，失败 {result.get('failed', 0)} 个，新增 {result.get('inserted', 0)} 篇。",
        )

    def after_startup_refresh(self, result):
        self.reload_current_view()
        self.set_status(
            f"启动同步完成：成功 {result.get('success', 0)} 个，失败 {result.get('failed', 0)} 个，新增 {result.get('inserted', 0)} 篇"
        )

    def mark_all_read(self):
        key = self.scope_key
        if key.startswith("feed:"):
            count = self.repo.mark_all_read(feed_id=self.id_from_key(key))
        elif key == "cat:none":
            count = self.repo.mark_all_read(category_id=-1)
        elif key.startswith("cat:"):
            count = self.repo.mark_all_read(category_id=self.id_from_key(key))
        else:
            count = self.repo.mark_all_read()
        self.reload_current_view()
        self.set_status(f"已标记 {count} 篇为已读")

    def show_backup_menu(self):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="导出 JSON 备份", command=self.export_backup)
        menu.add_command(label="导入 JSON 备份", command=self.import_backup)
        self.popup_near_pointer(menu)

    def export_backup(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出备份",
            defaultextension=".json",
            initialfile="mrss-backup.json",
            filetypes=(("JSON", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        Path(path).write_text(json.dumps(self.repo.export_backup(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.set_status(f"备份已导出：{path}")

    def import_backup(self):
        path = filedialog.askopenfilename(parent=self.root, title="导入备份", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if not path:
            return
        if not messagebox.askyesno(APP_TITLE, "导入会覆盖当前本地数据，继续？"):
            return
        backup = json.loads(Path(path).read_text(encoding="utf-8"))
        self.repo.restore_backup(backup)
        self.scope_key = "all"
        self.reload_current_view()

    def show_opml_menu(self):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="导出 OPML", command=self.export_opml)
        menu.add_command(label="导入 OPML", command=self.import_opml)
        self.popup_near_pointer(menu)

    def export_opml(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出 OPML",
            defaultextension=".opml",
            initialfile="mrss-subscriptions.opml",
            filetypes=(("OPML", "*.opml;*.xml"), ("All files", "*.*")),
        )
        if not path:
            return
        Path(path).write_text(self.repo.export_opml(), encoding="utf-8")
        self.set_status(f"OPML 已导出：{path}")

    def import_opml(self):
        path = filedialog.askopenfilename(parent=self.root, title="导入 OPML", filetypes=(("OPML", "*.opml;*.xml"), ("All files", "*.*")))
        if not path:
            return
        imported = self.repo.import_opml(Path(path).read_text(encoding="utf-8"))
        self.reload_current_view()
        messagebox.showinfo(APP_TITLE, f"已导入 {imported} 个订阅。可以点击刷新抓取文章。")

    def show_gist_menu(self):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="上传到 GitHub Gist", command=self.gist_upload)
        menu.add_command(label="从 GitHub Gist 恢复", command=self.gist_download)
        self.popup_near_pointer(menu)

    def gist_data(self, need_gist_id):
        token = simpledialog.askstring(APP_TITLE, "GitHub Token（需要 gist 权限）：", show="*", initialvalue=self.repo.setting("github_token"), parent=self.root)
        if not token:
            return None
        gist_id = simpledialog.askstring(APP_TITLE, "Gist ID（首次上传可留空）：", initialvalue=self.repo.setting("gist_id"), parent=self.root)
        if need_gist_id and not gist_id:
            messagebox.showwarning(APP_TITLE, "恢复时必须填写 Gist ID。")
            return None
        filename = simpledialog.askstring(
            APP_TITLE,
            "Gist 文件名：",
            initialvalue=self.repo.setting("gist_filename", "mrss-backup.json") or "mrss-backup.json",
            parent=self.root,
        )
        if not filename:
            return None
        return {"token": token, "gist_id": gist_id or "", "filename": filename}

    def gist_upload(self):
        data = self.gist_data(need_gist_id=False)
        if not data:
            return
        self.run_background("正在上传到 GitHub Gist...", lambda: gist_push(self.repo, data), self.after_gist_upload)

    def after_gist_upload(self, result):
        self.set_status(f"Gist 已上传：{result.get('gist_id')}")
        messagebox.showinfo(APP_TITLE, f"上传完成。\nGist ID：{result.get('gist_id')}")

    def gist_download(self):
        data = self.gist_data(need_gist_id=True)
        if not data:
            return
        if not messagebox.askyesno(APP_TITLE, "从 Gist 恢复会覆盖当前本地数据，继续？"):
            return

        def work():
            backup = gist_pull(data)
            self.repo.restore_backup(backup)
            return True

        self.run_background("正在从 GitHub Gist 恢复...", work, lambda _ok: self.after_gist_download())

    def after_gist_download(self):
        self.scope_key = "all"
        self.reload_current_view()
        messagebox.showinfo(APP_TITLE, "Gist 备份已恢复。")

    def popup_near_pointer(self, menu):
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        menu.tk_popup(x, y)


def main():
    root = tk.Tk()
    MRSSWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
