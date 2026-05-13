import html
import json
import queue
import re
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image

from app import DB_NAME, PAGE_SIZE, Repository, app_data_dir, gist_pull, gist_push


APP_TITLE = "MRSS"
BG = "#F4F6F8"
SURFACE = "#FFFFFF"
SIDEBAR = "#111827"
SIDEBAR_MUTED = "#94A3B8"
TEXT = "#111827"
MUTED = "#667085"
BORDER = "#E5E7EB"
PRIMARY = "#0F766E"
PRIMARY_HOVER = "#115E59"
SOFT_PRIMARY = "#D9F3EE"
DANGER = "#B42318"


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


def compact(value, length=180) -> str:
    text = strip_markup(value)
    return text if len(text) <= length else text[: length - 1] + "..."


def count_text(count, label="未读") -> str:
    return f"{count} {label}" if count else f"0 {label}"


class ModernMRSS(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.repo = Repository(app_data_dir() / DB_NAME)
        self.events = queue.Queue()
        self.stop_event = threading.Event()

        self.categories = []
        self.feeds = []
        self.category_by_id = {}
        self.feed_by_id = {}
        self.current_articles = []
        self.article_by_id = {}
        self.selected_article_id = None
        self.ignore_next_article_select = False
        self.scope_key = "all"
        self.offset = 0
        self.loaded_count = 0
        self.total_count = 0
        self.nav_buttons = {}

        self.search_var = tk.StringVar()
        self.unread_var = tk.BooleanVar(value=False)
        self.favorite_var = tk.BooleanVar(value=False)
        self.desc_var = tk.BooleanVar(value=True)
        self.sort_var = tk.StringVar(value="发布时间")
        self.date_var = tk.StringVar(value="全部日期")
        self.status_var = tk.StringVar(value="就绪")
        self.logo_image = self.load_logo_image()

        self.configure_window()
        self.build_ui()
        self.refresh_summary()
        self.load_articles()

        self.after(150, self.drain_events)
        self.after(600, self.startup_refresh)
        threading.Thread(target=self.scheduler_loop, daemon=True).start()

    def configure_window(self):
        self.title(APP_TITLE)
        self.geometry("1360x820")
        self.minsize(1100, 680)
        icon = resource_path("mrss.ico")
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except tk.TclError:
                pass
        self.protocol("WM_DELETE_WINDOW", self.close)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("green")
        self.configure_ttk_style()

    def configure_ttk_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "MRSS.Treeview",
            background=SURFACE,
            foreground=TEXT,
            fieldbackground=SURFACE,
            borderwidth=0,
            rowheight=58,
            font=("Microsoft YaHei UI", 11),
        )
        style.configure(
            "MRSS.Treeview.Heading",
            background="#F8FAFC",
            foreground=MUTED,
            relief="flat",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "MRSS.Treeview",
            background=[("selected", SOFT_PRIMARY)],
            foreground=[("selected", TEXT)],
        )

    def load_logo_image(self):
        path = resource_path("static") / "logo.png"
        if not path.exists():
            path = resource_path("logo.png")
        if not path.exists():
            return None
        try:
            image = Image.open(path)
            image.thumbnail((42, 42))
            return ctk.CTkImage(light_image=image, dark_image=image, size=(42, 42))
        except Exception:
            return None

    def ask_text(self, title, label, initial="", password=False):
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("420x190")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(fg_color=BG)
        dialog.grid_columnconfigure(0, weight=1)

        value = tk.StringVar(value=initial or "")
        result = {"value": None}
        ctk.CTkLabel(dialog, text=label, text_color=TEXT, font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=0, sticky="w", padx=22, pady=(22, 8))
        entry = ctk.CTkEntry(dialog, textvariable=value, height=42, corner_radius=12, border_color=BORDER, fg_color=SURFACE, show="*" if password else "")
        entry.grid(row=1, column=0, sticky="ew", padx=22)

        actions = ctk.CTkFrame(dialog, fg_color=BG)
        actions.grid(row=2, column=0, sticky="ew", padx=22, pady=(18, 18))
        actions.grid_columnconfigure(0, weight=1)

        def submit():
            result["value"] = value.get()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        ctk.CTkButton(actions, text="取消", width=86, height=36, fg_color=SURFACE, hover_color="#F1F5F9", text_color=TEXT, border_width=1, border_color=BORDER, command=cancel).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(actions, text="确定", width=86, height=36, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=submit).grid(row=0, column=2)
        entry.bind("<Return>", lambda _event: submit())
        dialog.bind("<Escape>", lambda _event: cancel())
        entry.focus_set()
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.wait_window(dialog)
        return result["value"]

    def ask_int(self, title, label, initial=60, minvalue=None, maxvalue=None):
        while True:
            raw = self.ask_text(title, label, str(initial))
            if raw is None:
                return None
            try:
                value = int(raw.strip())
            except ValueError:
                messagebox.showwarning(APP_TITLE, "请输入数字。")
                continue
            if minvalue is not None and value < minvalue:
                messagebox.showwarning(APP_TITLE, f"不能小于 {minvalue}。")
                continue
            if maxvalue is not None and value > maxvalue:
                messagebox.showwarning(APP_TITLE, f"不能大于 {maxvalue}。")
                continue
            return value

    def build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=292, corner_radius=0, fg_color=SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color=SIDEBAR)
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 14))
        brand.grid_columnconfigure(1, weight=1)
        brand.grid_rowconfigure((0, 1), weight=1)
        if self.logo_image:
            ctk.CTkLabel(brand, image=self.logo_image, text="").grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
            title_col = 1
        else:
            title_col = 0
            brand.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(brand, text="MRSS", font=ctk.CTkFont(family="Microsoft YaHei UI", size=30, weight="bold"), text_color="#F9FAFB", anchor="w").grid(row=0, column=title_col, sticky="ew")
        ctk.CTkLabel(brand, text="本地 RSS 阅读器", font=ctk.CTkFont(family="Microsoft YaHei UI", size=13), text_color=SIDEBAR_MUTED, anchor="w").grid(row=1, column=title_col, sticky="ew", pady=(2, 0))

        sidebar_actions = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        sidebar_actions.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        sidebar_actions.grid_columnconfigure((0, 1), weight=1)
        self.side_add_button = ctk.CTkButton(sidebar_actions, text="+ 订阅", height=36, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, text_color="#FFFFFF", font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"), command=self.add_feed)
        self.side_add_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(sidebar_actions, text="+ 分类", height=36, fg_color="#1F2937", hover_color="#374151", text_color="#FFFFFF", font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"), command=self.add_category).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.nav_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", scrollbar_button_color="#374151", scrollbar_button_hover_color="#4B5563")
        self.nav_scroll.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.nav_scroll.grid_columnconfigure(0, weight=1)

        self.sidebar_status = ctk.CTkLabel(self.sidebar, textvariable=self.status_var, text_color=SIDEBAR_MUTED, anchor="w", justify="left", font=ctk.CTkFont(size=12))
        self.sidebar_status.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))

        self.article_panel = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.article_panel.grid(row=0, column=1, sticky="nsew")
        self.article_panel.grid_columnconfigure(0, weight=1)
        self.article_panel.grid_rowconfigure(3, weight=1)

        top = ctk.CTkFrame(self.article_panel, fg_color=BG, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 8))
        top.grid_columnconfigure(0, weight=1)
        self.scope_label = ctk.CTkLabel(top, text="全部文章", text_color=TEXT, font=ctk.CTkFont(size=26, weight="bold"))
        self.scope_label.grid(row=0, column=0, sticky="w")
        self.count_label = ctk.CTkLabel(top, text="", text_color=MUTED, font=ctk.CTkFont(size=13))
        self.count_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        ctk.CTkButton(top, text="刷新", width=78, height=36, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=self.refresh_current).grid(row=0, column=1, rowspan=2, padx=(8, 0))
        ctk.CTkButton(top, text="全部已读", width=92, height=36, fg_color=SURFACE, hover_color="#F1F5F9", text_color=TEXT, border_width=1, border_color=BORDER, command=self.mark_all_read).grid(row=0, column=2, rowspan=2, padx=(8, 0))
        ctk.CTkButton(top, text="更多", width=78, height=36, fg_color=SURFACE, hover_color="#F1F5F9", text_color=TEXT, border_width=1, border_color=BORDER, command=self.show_more_menu).grid(row=0, column=3, rowspan=2, padx=(8, 0))

        search_row = ctk.CTkFrame(self.article_panel, fg_color=BG, corner_radius=0)
        search_row.grid(row=1, column=0, sticky="ew", padx=22, pady=(4, 8))
        search_row.grid_columnconfigure(0, weight=1)
        search = ctk.CTkEntry(search_row, textvariable=self.search_var, height=42, corner_radius=12, placeholder_text="搜索标题、内容或订阅源", border_color=BORDER, fg_color=SURFACE)
        search.grid(row=0, column=0, sticky="ew")
        search.bind("<Return>", lambda _event: self.apply_filters())
        ctk.CTkButton(search_row, text="搜索", width=74, height=42, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=self.apply_filters).grid(row=0, column=1, padx=(10, 0))

        filter_row = ctk.CTkFrame(self.article_panel, fg_color=BG, corner_radius=0)
        filter_row.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 8))
        self.unread_switch = ctk.CTkSwitch(filter_row, text="未读", variable=self.unread_var, command=self.apply_filters, progress_color=PRIMARY)
        self.unread_switch.grid(row=0, column=0, padx=(0, 12))
        self.favorite_switch = ctk.CTkSwitch(filter_row, text="收藏", variable=self.favorite_var, command=self.apply_filters, progress_color=PRIMARY)
        self.favorite_switch.grid(row=0, column=1, padx=(0, 12))
        self.desc_switch = ctk.CTkSwitch(filter_row, text="降序", variable=self.desc_var, command=self.apply_filters, progress_color=PRIMARY)
        self.desc_switch.grid(row=0, column=2, padx=(0, 16))
        self.sort_menu = ctk.CTkOptionMenu(filter_row, values=["发布时间", "创建时间", "标题"], variable=self.sort_var, command=lambda _value: self.apply_filters(), width=120, fg_color=SURFACE, button_color=SURFACE, button_hover_color="#F1F5F9", text_color=TEXT)
        self.sort_menu.grid(row=0, column=3, padx=(0, 10))
        self.date_menu = ctk.CTkOptionMenu(filter_row, values=["全部日期", "今天", "昨天", "最近 7 天"], variable=self.date_var, command=lambda _value: self.apply_filters(), width=130, fg_color=SURFACE, button_color=SURFACE, button_hover_color="#F1F5F9", text_color=TEXT)
        self.date_menu.grid(row=0, column=4)

        list_frame = tk.Frame(self.article_panel, bg=BG, highlightthickness=0)
        list_frame.grid(row=3, column=0, sticky="nsew", padx=22, pady=(0, 8))
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)

        self.article_list = ttk.Treeview(
            list_frame,
            columns=("title", "feed", "time"),
            show="headings",
            selectmode="browse",
            style="MRSS.Treeview",
        )
        self.article_list.heading("title", text="标题")
        self.article_list.heading("feed", text="订阅源")
        self.article_list.heading("time", text="时间")
        self.article_list.column("title", width=430, minwidth=260, stretch=True, anchor="w")
        self.article_list.column("feed", width=140, minwidth=96, stretch=False, anchor="w")
        self.article_list.column("time", width=132, minwidth=118, stretch=False, anchor="w")
        self.article_list.tag_configure("read", foreground="#667085")
        self.article_list.tag_configure("unread", foreground=TEXT)
        self.article_list.tag_configure("favorite", foreground=PRIMARY)
        self.article_list.grid(row=0, column=0, sticky="nsew")
        self.article_list.bind("<<TreeviewSelect>>", self.on_article_select)
        self.article_list.bind("<Double-1>", self.on_article_double_click)
        self.article_list.bind("<Button-3>", self.show_article_menu_from_event)

        article_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.article_list.yview)
        article_scrollbar.grid(row=0, column=1, sticky="ns")
        self.article_list.configure(yscrollcommand=article_scrollbar.set)

        bottom = ctk.CTkFrame(self.article_panel, fg_color=BG, corner_radius=0)
        bottom.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 16))
        bottom.grid_columnconfigure(0, weight=1)
        self.load_more_button = ctk.CTkButton(bottom, text="加载更多", width=112, height=36, fg_color=SURFACE, hover_color="#F1F5F9", text_color=TEXT, border_width=1, border_color=BORDER, command=self.load_more)
        self.load_more_button.grid(row=0, column=1, sticky="e")

        self.reader_panel = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0)
        self.reader_panel.grid(row=0, column=2, sticky="nsew")
        self.reader_panel.grid_columnconfigure(0, weight=1)
        self.reader_panel.grid_rowconfigure(3, weight=1)
        self.build_empty_reader()

    def build_empty_reader(self):
        for child in self.reader_panel.winfo_children():
            child.destroy()
        placeholder = ctk.CTkFrame(self.reader_panel, fg_color=SURFACE)
        placeholder.grid(row=0, column=0, sticky="nsew", padx=26, pady=26)
        placeholder.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(placeholder, text="选择一篇文章", text_color=TEXT, font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w", pady=(180, 8))
        ctk.CTkLabel(placeholder, text="双击或单击左侧文章卡片，在这里阅读正文。", text_color=MUTED, font=ctk.CTkFont(size=14)).grid(row=1, column=0, sticky="w")

    def render_reader(self, article):
        for child in self.reader_panel.winfo_children():
            child.destroy()
        self.reader_panel.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(self.reader_panel, fg_color=SURFACE, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)
        title = ctk.CTkLabel(header, text=article["title"], text_color=TEXT, font=ctk.CTkFont(size=23, weight="bold"), wraplength=470, justify="left")
        title.grid(row=0, column=0, sticky="ew")
        meta = f"{article.get('feed_title') or ''} · {ms_to_text(article.get('published_at') or article.get('created_at'))}"
        if article.get("author"):
            meta += f" · {article['author']}"
        ctk.CTkLabel(header, text=meta, text_color=MUTED, font=ctk.CTkFont(size=13), wraplength=470, justify="left").grid(row=1, column=0, sticky="w", pady=(8, 0))

        actions = ctk.CTkFrame(self.reader_panel, fg_color=SURFACE, corner_radius=0)
        actions.grid(row=1, column=0, sticky="ew", padx=26, pady=(4, 12))
        actions.grid_columnconfigure(4, weight=1)
        ctk.CTkButton(actions, text="打开原文", width=92, height=34, fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=lambda: self.open_article_link(article)).grid(row=0, column=0, padx=(0, 8))
        fav_text = "取消收藏" if article.get("is_favorite") else "收藏"
        ctk.CTkButton(actions, text=fav_text, width=92, height=34, fg_color="#F8FAFC", hover_color="#EEF2F7", text_color=TEXT, border_width=1, border_color=BORDER, command=lambda: self.toggle_article_favorite(article)).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(actions, text="标为未读", width=92, height=34, fg_color="#F8FAFC", hover_color="#EEF2F7", text_color=TEXT, border_width=1, border_color=BORDER, command=lambda: self.mark_article_unread(article)).grid(row=0, column=2)

        ctk.CTkFrame(self.reader_panel, height=1, fg_color=BORDER, corner_radius=0).grid(row=2, column=0, sticky="ew")

        body = ctk.CTkTextbox(self.reader_panel, wrap="word", fg_color=SURFACE, text_color="#1F2937", border_width=0, font=ctk.CTkFont(size=15), padx=24, pady=22)
        body.grid(row=3, column=0, sticky="nsew")
        body.insert("1.0", strip_markup(article.get("content")) or compact(article.get("title"), 200))
        body.configure(state="disabled")

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
            self.after(150, self.drain_events)

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
                self.events.put(("done", "后台同步", result, lambda _result: self.reload_current_view()))
                self.events.put(("status", f"后台同步新增 {result['inserted']} 篇文章"))

    def startup_refresh(self):
        if self.feeds:
            self.run_background("启动后同步全部订阅中...", self.repo.refresh_feeds, self.after_startup_refresh)

    def close(self):
        self.stop_event.set()
        self.destroy()

    def set_status(self, text):
        self.status_var.set(text)

    def refresh_summary(self, select_key=None):
        self.categories = self.repo.categories()
        self.feeds = self.repo.feeds()
        self.category_by_id = {int(item["id"]): item for item in self.categories}
        self.feed_by_id = {int(item["id"]): item for item in self.feeds}
        self.render_nav(select_key or self.scope_key)
        self.update_header()

    def render_nav(self, selected_key):
        for child in self.nav_scroll.winfo_children():
            child.destroy()
        self.nav_buttons.clear()

        stats = self.repo.stats()
        row = 0
        row = self.add_nav_button(row, "all", "全部文章", count_text(stats["unreadCount"]), level=0)

        feeds_by_category = {}
        for feed in self.feeds:
            feeds_by_category.setdefault(feed.get("category_id"), []).append(feed)

        for category in self.categories:
            key = f"cat:{category['id']}"
            row = self.add_nav_button(row, key, category["name"], count_text(category["unread_count"]), level=0)
            for feed in feeds_by_category.pop(category["id"], []):
                row = self.add_feed_button(row, feed)

        ungrouped = feeds_by_category.pop(None, []) + feeds_by_category.pop(0, [])
        if ungrouped:
            row = self.add_nav_button(row, "cat:none", "未分类", f"{len(ungrouped)} 个订阅", level=0)
            for feed in ungrouped:
                row = self.add_feed_button(row, feed)

        if selected_key in self.nav_buttons:
            self.select_scope(selected_key, reload_articles=False)
        else:
            self.scope_key = "all"
            self.select_scope("all", reload_articles=False)

    def add_nav_button(self, row, key, title, subtitle, level=0):
        selected = key == self.scope_key
        button = ctk.CTkButton(
            self.nav_scroll,
            text=f"{title}\n{subtitle}",
            anchor="w",
            height=54,
            corner_radius=12,
            fg_color="#1F2937" if selected else "transparent",
            hover_color="#263244",
            text_color="#F9FAFB" if selected else "#D1D5DB",
            font=ctk.CTkFont(size=14, weight="bold" if level == 0 else "normal"),
            command=lambda current=key: self.select_scope(current),
        )
        button.grid(row=row, column=0, sticky="ew", padx=(level * 14, 0), pady=3)
        button.bind("<Button-3>", lambda event, current=key: self.show_nav_menu(current, event))
        self.nav_buttons[key] = button
        return row + 1

    def add_feed_button(self, row, feed):
        title = feed["title"] or feed["url"]
        if len(title) > 24:
            title = title[:23] + "..."
        subtitle = count_text(feed.get("unread_count", 0))
        if not feed.get("is_active"):
            subtitle = "停用 · " + subtitle
        return self.add_nav_button(row, f"feed:{feed['id']}", title, subtitle, level=1)

    def select_scope(self, key, reload_articles=True):
        self.scope_key = key
        for button_key, button in self.nav_buttons.items():
            selected = button_key == key
            button.configure(fg_color="#1F2937" if selected else "transparent", text_color="#F9FAFB" if selected else "#D1D5DB")
        self.update_header()
        if reload_articles:
            self.offset = 0
            self.load_articles()

    def update_header(self):
        title = self.scope_title()
        self.scope_label.configure(text=title)
        stats = self.repo.stats()
        self.count_label.configure(text=f"{stats['articleCount']} 篇文章 · {stats['unreadCount']} 未读 · {stats['favoriteCount']} 收藏")

    def scope_title(self):
        key = self.scope_key
        if key == "all":
            return "全部文章"
        if key == "cat:none":
            return "未分类"
        if key.startswith("cat:"):
            category = self.category_by_id.get(self.id_from_key(key))
            return category["name"] if category else "分类"
        if key.startswith("feed:"):
            feed = self.feed_by_id.get(self.id_from_key(key))
            return feed["title"] if feed else "订阅源"
        return "全部文章"

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
            self.current_articles.clear()
            self.article_by_id.clear()
            children = self.article_list.get_children()
            if children:
                self.article_list.delete(*children)
        result = self.repo.articles(self.article_params())
        self.total_count = result["total"]
        if not append and not result["items"]:
            self.article_list.insert("", "end", iid="empty", values=("暂无文章，添加订阅或刷新后会显示在这里", "", ""), tags=("read",))
        for article in result["items"]:
            self.current_articles.append(article)
            self.article_by_id[str(article["id"])] = article
            self.render_article_row(article)
            self.loaded_count += 1
        self.offset = self.loaded_count
        self.load_more_button.configure(state="normal" if self.loaded_count < self.total_count else "disabled")
        self.set_status(f"已显示 {self.loaded_count} / {self.total_count} 篇")

    def render_article_row(self, article):
        iid = str(article["id"])
        title = article["title"] or "Untitled"
        if article.get("is_favorite"):
            title = "★ " + title
        tags = ("unread",) if not article.get("is_read") else ("read",)
        if article.get("is_favorite"):
            tags = tags + ("favorite",)
        values = (
            title,
            article.get("feed_title") or "",
            ms_to_text(article.get("published_at") or article.get("created_at")),
        )
        if self.article_list.exists(iid):
            self.article_list.item(iid, values=values, tags=tags)
        else:
            self.article_list.insert("", "end", iid=iid, values=values, tags=tags)

    def update_article_row(self, article):
        self.article_by_id[str(article["id"])] = article
        self.render_article_row(article)

    def remove_article_row(self, article):
        iid = str(article["id"])
        if self.article_list.exists(iid):
            self.article_list.delete(iid)
        self.article_by_id.pop(iid, None)
        self.current_articles = [item for item in self.current_articles if str(item["id"]) != iid]
        self.loaded_count = max(0, self.loaded_count - 1)
        self.total_count = max(0, self.total_count - 1)
        self.load_more_button.configure(state="normal" if self.loaded_count < self.total_count else "disabled")
        self.set_status(f"已显示 {self.loaded_count} / {self.total_count} 篇")

    def on_article_select(self, _event=None):
        if self.ignore_next_article_select:
            return
        selection = self.article_list.selection()
        if not selection or selection[0] == "empty":
            return
        article = self.article_by_id.get(selection[0])
        if article:
            self.select_article(article)

    def on_article_double_click(self, _event=None):
        selection = self.article_list.selection()
        if not selection or selection[0] == "empty":
            return
        article = self.article_by_id.get(selection[0])
        if article:
            self.select_article(article, mark_read=True)

    def show_article_menu_from_event(self, event):
        iid = self.article_list.identify_row(event.y)
        if not iid or iid == "empty":
            return
        self.ignore_next_article_select = True
        self.article_list.selection_set(iid)
        self.after_idle(lambda: setattr(self, "ignore_next_article_select", False))
        article = self.article_by_id.get(iid)
        if article:
            self.show_article_menu(article, event)

    def select_article(self, article, mark_read=True):
        was_unread = not article.get("is_read")
        if mark_read and was_unread:
            self.repo.mark_read(article["id"], True)
            article["is_read"] = 1
        self.selected_article_id = article["id"]
        self.render_reader(article)
        if mark_read and was_unread and self.unread_var.get():
            self.remove_article_row(article)
        else:
            self.update_article_row(article)
        self.update_header()

    def reload_current_view(self):
        selected = self.selected_article_id
        self.refresh_summary()
        self.load_articles()
        if selected:
            article = next((item for item in self.current_articles if item["id"] == selected), None)
            if article:
                self.ignore_next_article_select = True
                self.article_list.selection_set(str(article["id"]))
                self.article_list.see(str(article["id"]))
                self.after_idle(lambda: setattr(self, "ignore_next_article_select", False))
                self.render_reader(article)

    def load_more(self):
        if self.loaded_count >= self.total_count:
            self.set_status("没有更多文章")
            return
        self.load_articles(append=True)

    def apply_filters(self):
        self.offset = 0
        self.load_articles()

    def show_article_menu(self, article, event):
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="阅读", command=lambda: self.select_article(article))
        menu.add_command(label="打开原文", command=lambda: self.open_article_link(article))
        menu.add_separator()
        menu.add_command(label="标为未读", command=lambda: self.mark_article_unread(article))
        menu.add_command(label="切换收藏", command=lambda: self.toggle_article_favorite(article))
        menu.tk_popup(event.x_root, event.y_root)

    def show_nav_menu(self, key, event):
        self.select_scope(key)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="添加订阅", command=self.add_feed)
        menu.add_command(label="新建分类", command=self.add_category)
        menu.add_separator()
        if key == "cat:none":
            menu.add_command(label="刷新未分类", command=self.refresh_current)
        elif key.startswith("cat:"):
            category_id = self.id_from_key(key)
            menu.add_command(label="重命名分类", command=lambda: self.rename_category(category_id))
            menu.add_command(label="删除分类", command=lambda: self.delete_category(category_id))
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

    def current_category_id(self):
        key = self.scope_key
        if key.startswith("cat:") and key != "cat:none":
            return self.id_from_key(key)
        if key.startswith("feed:"):
            feed = self.feed_by_id.get(self.id_from_key(key))
            return feed.get("category_id") if feed else None
        return None

    def add_category(self):
        name = self.ask_text(APP_TITLE, "分类名称：")
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
        name = self.ask_text(APP_TITLE, "新的分类名称：", initial=category["name"])
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

    def add_feed(self):
        url = self.ask_text(APP_TITLE, "RSS/Atom 链接：")
        if not url:
            return
        interval_minutes = self.ask_int(APP_TITLE, "同步间隔（分钟）：", initial=60, minvalue=5, maxvalue=10080)
        if interval_minutes is None:
            return
        category_id = self.current_category_id()
        self.run_background("正在添加订阅并抓取文章...", lambda: self.repo.add_feed(url.strip(), category_id=category_id, interval=interval_minutes * 60), lambda _feed_id: self.after_add_feed())

    def after_add_feed(self):
        self.reload_current_view()
        messagebox.showinfo(APP_TITLE, "订阅已添加。")

    def rename_feed(self, feed_id):
        feed = self.feed_by_id.get(feed_id)
        if not feed:
            return
        title = self.ask_text(APP_TITLE, "新的订阅名称：", initial=feed["title"])
        if not title:
            return
        self.repo.update_feed(feed_id, {**feed, "title": title.strip(), "active": bool(feed["is_active"])})
        self.refresh_summary(f"feed:{feed_id}")
        self.load_articles()

    def move_feed(self, feed_id):
        feed = self.feed_by_id.get(feed_id)
        if not feed:
            return
        choice = self.ask_text(APP_TITLE, "移动到分类（可填已有分类名称，留空为未分类）：")
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
        minutes = self.ask_int(APP_TITLE, "同步间隔（分钟）：", initial=max(5, int(feed.get("fetch_interval") or 3600) // 60), minvalue=5, maxvalue=10080)
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
            work = lambda: self.repo.refresh_feeds(feed_id=self.id_from_key(key))
            label = "正在刷新订阅..."
        elif key == "cat:none":
            work = lambda: self.repo.refresh_feeds(category_id=-1)
            label = "正在刷新未分类订阅..."
        elif key.startswith("cat:"):
            work = lambda: self.repo.refresh_feeds(category_id=self.id_from_key(key))
            label = "正在刷新分类..."
        else:
            work = self.repo.refresh_feeds
            label = "正在刷新全部订阅..."
        self.run_background(label, work, self.after_refresh)

    def after_refresh(self, result):
        self.reload_current_view()
        messagebox.showinfo(APP_TITLE, f"刷新完成。\n成功 {result.get('success', 0)} 个，失败 {result.get('failed', 0)} 个，新增 {result.get('inserted', 0)} 篇。")

    def after_startup_refresh(self, result):
        self.reload_current_view()
        self.set_status(f"启动同步完成：成功 {result.get('success', 0)} 个，失败 {result.get('failed', 0)} 个，新增 {result.get('inserted', 0)} 篇")

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

    def open_article_link(self, article):
        if article.get("link"):
            webbrowser.open(article["link"])
        else:
            messagebox.showinfo(APP_TITLE, "这篇文章没有原文链接。")

    def toggle_article_favorite(self, article):
        article["is_favorite"] = 1 if self.repo.toggle_favorite(article["id"]) else 0
        if self.favorite_var.get() and not article["is_favorite"]:
            self.remove_article_row(article)
        else:
            self.update_article_row(article)
        if self.selected_article_id == article["id"]:
            self.render_reader(article)
        self.update_header()

    def mark_article_unread(self, article):
        self.repo.mark_read(article["id"], False)
        article["is_read"] = 0
        self.update_article_row(article)
        if self.selected_article_id == article["id"]:
            self.render_reader(article)
        self.update_header()

    def show_more_menu(self):
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="导出 JSON 备份", command=self.export_backup)
        menu.add_command(label="导入 JSON 备份", command=self.import_backup)
        menu.add_separator()
        menu.add_command(label="导出 OPML", command=self.export_opml)
        menu.add_command(label="导入 OPML", command=self.import_opml)
        menu.add_separator()
        menu.add_command(label="上传到 GitHub Gist", command=self.gist_upload)
        menu.add_command(label="从 GitHub Gist 恢复", command=self.gist_download)
        x = self.winfo_pointerx()
        y = self.winfo_pointery()
        menu.tk_popup(x, y)

    def export_backup(self):
        path = filedialog.asksaveasfilename(parent=self, title="导出备份", defaultextension=".json", initialfile="mrss-backup.json", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if not path:
            return
        Path(path).write_text(json.dumps(self.repo.export_backup(), ensure_ascii=False, indent=2), encoding="utf-8")
        self.set_status(f"备份已导出：{path}")

    def import_backup(self):
        path = filedialog.askopenfilename(parent=self, title="导入备份", filetypes=(("JSON", "*.json"), ("All files", "*.*")))
        if not path:
            return
        if not messagebox.askyesno(APP_TITLE, "导入会覆盖当前本地数据，继续？"):
            return
        backup = json.loads(Path(path).read_text(encoding="utf-8"))
        self.repo.restore_backup(backup)
        self.scope_key = "all"
        self.reload_current_view()

    def export_opml(self):
        path = filedialog.asksaveasfilename(parent=self, title="导出 OPML", defaultextension=".opml", initialfile="mrss-subscriptions.opml", filetypes=(("OPML", "*.opml;*.xml"), ("All files", "*.*")))
        if not path:
            return
        Path(path).write_text(self.repo.export_opml(), encoding="utf-8")
        self.set_status(f"OPML 已导出：{path}")

    def import_opml(self):
        path = filedialog.askopenfilename(parent=self, title="导入 OPML", filetypes=(("OPML", "*.opml;*.xml"), ("All files", "*.*")))
        if not path:
            return
        imported = self.repo.import_opml(Path(path).read_text(encoding="utf-8"))
        self.reload_current_view()
        messagebox.showinfo(APP_TITLE, f"已导入 {imported} 个订阅。可以点击刷新抓取文章。")

    def gist_data(self, need_gist_id):
        token = self.ask_text(APP_TITLE, "GitHub Token（需要 gist 权限）：", initial=self.repo.setting("github_token"), password=True)
        if not token:
            return None
        gist_id = self.ask_text(APP_TITLE, "Gist ID（首次上传可留空）：", initial=self.repo.setting("gist_id"))
        if need_gist_id and not gist_id:
            messagebox.showwarning(APP_TITLE, "恢复时必须填写 Gist ID。")
            return None
        filename = self.ask_text(APP_TITLE, "Gist 文件名：", initial=self.repo.setting("gist_filename", "mrss-backup.json") or "mrss-backup.json")
        if not filename:
            return None
        return {"token": token, "gist_id": gist_id or "", "filename": filename}

    def gist_upload(self):
        data = self.gist_data(need_gist_id=False)
        if data:
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


def main():
    app = ModernMRSS()
    app.mainloop()


if __name__ == "__main__":
    main()
