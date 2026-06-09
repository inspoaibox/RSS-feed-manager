package com.mrss.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.Html;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AbsListView;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import com.mrss.mobile.api.ServerApi;
import com.mrss.mobile.data.AppSettings;
import com.mrss.mobile.data.MobileRepository;
import com.mrss.mobile.model.Article;
import com.mrss.mobile.model.Category;
import com.mrss.mobile.model.Feed;
import com.mrss.mobile.sync.SyncEngine;
import com.mrss.mobile.sync.SyncScheduler;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int PAGE_SIZE = 40;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private AppSettings settings;
    private MobileRepository repository;
    private ServerApi api;

    private final List<Category> categories = new ArrayList<>();
    private final List<Feed> feeds = new ArrayList<>();
    private final List<Article> articles = new ArrayList<>();
    private ArrayAdapter<Category> categoryAdapter;
    private ArrayAdapter<Feed> feedAdapter;
    private ArrayAdapter<Article> articleAdapter;

    private Spinner categorySpinner;
    private Spinner feedSpinner;
    private CheckBox unreadOnlyCheckbox;
    private CheckBox favoritesOnlyCheckbox;
    private EditText searchInput;
    private TextView statusText;
    private TextView pageText;
    private Button previousButton;
    private Button nextButton;

    private Long selectedCategoryId = null;
    private Long selectedFeedId = null;
    private int currentPage = 0;
    private boolean suppressSelection = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        settings = new AppSettings(this);
        repository = new MobileRepository(this);
        api = new ServerApi(settings);
        if (settings.isLoggedIn()) {
            buildMainUi();
            loadLocalData();
            runSync(false);
        } else {
            buildLoginUi();
        }
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void buildLoginUi() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            getWindow().setStatusBarColor(Color.rgb(23, 107, 91));
            getWindow().setNavigationBarColor(Color.rgb(247, 248, 245));
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(24), dp(24) + statusBarHeight(), dp(24), dp(24));
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setBackgroundColor(Color.rgb(247, 248, 245));

        TextView title = new TextView(this);
        title.setText("Rss订阅");
        title.setTextColor(Color.rgb(23, 107, 91));
        title.setTextSize(28);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title, matchWrap());

        TextView subtitle = new TextView(this);
        subtitle.setText("连接你的 RSS Manager 服务端");
        subtitle.setTextColor(Color.rgb(79, 91, 87));
        subtitle.setTextSize(14);
        subtitle.setPadding(0, dp(8), 0, dp(24));
        root.addView(subtitle, matchWrap());

        EditText baseUrlInput = input("服务端地址，例如 https://rss.example.com");
        baseUrlInput.setSingleLine(true);
        baseUrlInput.setText(settings.getBaseUrl());
        root.addView(baseUrlInput, matchWrap());

        EditText usernameInput = input("用户名");
        usernameInput.setSingleLine(true);
        usernameInput.setPadding(usernameInput.getPaddingLeft(), dp(14), usernameInput.getPaddingRight(), dp(14));
        root.addView(usernameInput, topMargin(matchWrap(), dp(12)));

        EditText passwordInput = input("密码");
        passwordInput.setSingleLine(true);
        passwordInput.setInputType(0x00000081);
        root.addView(passwordInput, topMargin(matchWrap(), dp(12)));

        Button loginButton = primaryButton("登录");
        root.addView(loginButton, topMargin(matchWrap(), dp(18)));

        TextView hint = new TextView(this);
        hint.setText("手机端数据将以服务端为准，本地只作为缓存。");
        hint.setTextColor(Color.rgb(104, 112, 109));
        hint.setTextSize(13);
        hint.setGravity(Gravity.CENTER);
        hint.setPadding(0, dp(16), 0, 0);
        root.addView(hint, matchWrap());

        loginButton.setOnClickListener(v -> {
            String baseUrl = baseUrlInput.getText().toString().trim();
            String username = usernameInput.getText().toString().trim();
            String password = passwordInput.getText().toString();
            if (baseUrl.isEmpty() || username.isEmpty() || password.isEmpty()) {
                toast("请填写服务端地址、用户名和密码");
                return;
            }
            login(baseUrl, username, password);
        });

        setContentView(root);
    }

    private void buildMainUi() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            getWindow().setStatusBarColor(Color.rgb(23, 107, 91));
            getWindow().setNavigationBarColor(Color.rgb(247, 248, 245));
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(247, 248, 245));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(16), dp(8) + statusBarHeight(), dp(16), dp(8));
        header.setBackgroundColor(Color.rgb(23, 107, 91));

        TextView title = new TextView(this);
        title.setText("Rss订阅");
        title.setTextColor(Color.WHITE);
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        TextView refresh = headerButton("刷新");
        refresh.setOnClickListener(v -> runSync(false));
        header.addView(refresh);

        TextView more = headerButton("更多");
        more.setOnClickListener(v -> showMoreMenu());
        header.addView(more);
        root.addView(header);

        LinearLayout filters = new LinearLayout(this);
        filters.setOrientation(LinearLayout.VERTICAL);
        filters.setPadding(dp(12), dp(8), dp(12), dp(8));

        LinearLayout filterRow = new LinearLayout(this);
        filterRow.setOrientation(LinearLayout.HORIZONTAL);
        categorySpinner = new Spinner(this);
        feedSpinner = new Spinner(this);
        categoryAdapter = new ArrayAdapter<Category>(this, android.R.layout.simple_spinner_dropdown_item, categories);
        feedAdapter = new ArrayAdapter<Feed>(this, android.R.layout.simple_spinner_dropdown_item, feeds);
        categorySpinner.setAdapter(categoryAdapter);
        feedSpinner.setAdapter(feedAdapter);
        filterRow.addView(categorySpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        filterRow.addView(feedSpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        filters.addView(filterRow);

        searchInput = input("搜索标题、正文、摘要或翻译");
        filters.addView(searchInput, topMargin(matchWrap(), dp(8)));

        LinearLayout toggles = new LinearLayout(this);
        toggles.setGravity(Gravity.CENTER_VERTICAL);
        unreadOnlyCheckbox = new CheckBox(this);
        unreadOnlyCheckbox.setText("未读");
        favoritesOnlyCheckbox = new CheckBox(this);
        favoritesOnlyCheckbox.setText("收藏");
        Button searchButton = secondaryButton("搜索");
        searchButton.setOnClickListener(v -> {
            currentPage = 0;
            loadArticles();
        });
        toggles.addView(unreadOnlyCheckbox);
        toggles.addView(favoritesOnlyCheckbox);
        toggles.addView(searchButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        filters.addView(toggles);
        root.addView(filters);

        articleAdapter = new ArrayAdapter<Article>(this, android.R.layout.simple_list_item_1, articles) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getView(position, convertView, parent);
                Article article = getItem(position);
                view.setText(article == null ? "" : articleLabel(article));
                view.setTextSize(15);
                view.setTextColor(article != null && article.read ? Color.rgb(102, 111, 108) : Color.rgb(30, 40, 37));
                view.setTypeface(Typeface.DEFAULT, article != null && article.read ? Typeface.NORMAL : Typeface.BOLD);
                view.setPadding(dp(14), dp(12), dp(14), dp(12));
                return view;
            }
        };

        ListView listView = new ListView(this);
        listView.setAdapter(articleAdapter);
        listView.setDividerHeight(1);
        listView.setChoiceMode(AbsListView.CHOICE_MODE_SINGLE);
        listView.setOnItemClickListener((parent, view, position, id) -> {
            Article article = articles.get(position);
            repository.setRead(article.id, true, true);
            loadArticles();
            showArticle(article.id);
        });
        root.addView(listView, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        LinearLayout footer = new LinearLayout(this);
        footer.setGravity(Gravity.CENTER_VERTICAL);
        footer.setPadding(dp(12), dp(6), dp(12), dp(8));
        previousButton = secondaryButton("上一页");
        nextButton = secondaryButton("下一页");
        pageText = new TextView(this);
        pageText.setGravity(Gravity.CENTER);
        pageText.setTextColor(Color.rgb(79, 91, 87));
        statusText = new TextView(this);
        statusText.setTextColor(Color.rgb(79, 91, 87));
        statusText.setTextSize(12);
        footer.addView(previousButton);
        footer.addView(pageText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        footer.addView(nextButton);
        root.addView(statusText, paddedParams());
        root.addView(footer);

        previousButton.setOnClickListener(v -> {
            if (currentPage > 0) {
                currentPage--;
                loadArticles();
            }
        });
        nextButton.setOnClickListener(v -> {
            if (articles.size() >= PAGE_SIZE) {
                currentPage++;
                loadArticles();
            }
        });

        categorySpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (suppressSelection) {
                    return;
                }
                Category category = categories.get(position);
                selectedCategoryId = category.id == 0 ? null : category.id;
                selectedFeedId = null;
                currentPage = 0;
                loadFeeds();
                loadArticles();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });

        feedSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (suppressSelection) {
                    return;
                }
                Feed feed = feeds.get(position);
                selectedFeedId = feed.id == 0 ? null : feed.id;
                currentPage = 0;
                loadArticles();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });

        unreadOnlyCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> {
            currentPage = 0;
            loadArticles();
        });
        favoritesOnlyCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> {
            currentPage = 0;
            loadArticles();
        });

        setContentView(root);
    }

    private void login(String baseUrl, String username, String password) {
        ProgressDialog dialog = ProgressDialog.show(this, null, "正在登录...", true, false);
        executor.execute(() -> {
            try {
                api.login(baseUrl, username, password);
                SyncScheduler.schedule(this);
                runOnUiThread(() -> {
                    dialog.dismiss();
                    buildMainUi();
                    loadLocalData();
                    runSync(true);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    dialog.dismiss();
                    toast(e.getMessage());
                });
            }
        });
    }

    private void runSync(boolean fullRefresh) {
        status("同步中...");
        executor.execute(() -> {
            try {
                SyncEngine.Result result = SyncEngine.sync(this, fullRefresh);
                runOnUiThread(() -> {
                    loadLocalData();
                    status(String.format(Locale.getDefault(), "同步完成：文章 %d，上传操作 %d", result.articles, result.uploadedActions));
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    loadLocalData();
                    status("同步失败：" + e.getMessage());
                });
            }
        });
    }

    private void loadLocalData() {
        loadCategories();
        loadFeeds();
        loadArticles();
    }

    private void loadCategories() {
        suppressSelection = true;
        categories.clear();
        categories.addAll(repository.getCategoriesWithAll());
        categoryAdapter.notifyDataSetChanged();
        categorySpinner.setSelection(0);
        selectedCategoryId = null;
        suppressSelection = false;
    }

    private void loadFeeds() {
        suppressSelection = true;
        feeds.clear();
        feeds.addAll(repository.getFeedsWithAll(selectedCategoryId));
        feedAdapter.notifyDataSetChanged();
        feedSpinner.setSelection(0);
        suppressSelection = false;
    }

    private void loadArticles() {
        articles.clear();
        articles.addAll(repository.getArticles(
                selectedCategoryId,
                selectedFeedId,
                unreadOnlyCheckbox != null && unreadOnlyCheckbox.isChecked(),
                favoritesOnlyCheckbox != null && favoritesOnlyCheckbox.isChecked(),
                searchInput == null ? "" : searchInput.getText().toString(),
                currentPage,
                PAGE_SIZE
        ));
        articleAdapter.notifyDataSetChanged();
        pageText.setText("第 " + (currentPage + 1) + " 页");
        previousButton.setEnabled(currentPage > 0);
        nextButton.setEnabled(articles.size() >= PAGE_SIZE);
        if (articles.isEmpty()) {
            status("暂无文章，刷新后会从服务端同步数据");
        }
    }

    private void showArticle(long articleId) {
        Article article = repository.getArticle(articleId);
        if (article == null) {
            toast("文章不存在");
            return;
        }

        ScrollView scroll = new ScrollView(this);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(18), dp(14), dp(18), dp(14));
        scroll.addView(box);

        TextView title = new TextView(this);
        title.setText(article.title);
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(30, 40, 37));
        box.addView(title);

        TextView meta = new TextView(this);
        meta.setText((article.feedTitle == null ? "" : article.feedTitle) + formatDateLine(article));
        meta.setTextSize(12);
        meta.setTextColor(Color.rgb(102, 111, 108));
        meta.setPadding(0, dp(8), 0, dp(8));
        box.addView(meta);

        if (!empty(article.summary)) {
            TextView summary = sectionText("摘要\n" + article.summary);
            box.addView(summary);
        }

        String translated = parseTranslation(article.translation);
        if (!empty(translated)) {
            TextView translation = sectionText("翻译\n" + translated);
            box.addView(translation);
        }

        TextView content = new TextView(this);
        content.setTextSize(15);
        content.setTextColor(Color.rgb(30, 40, 37));
        content.setLineSpacing(dp(2), 1.05f);
        String html = !empty(article.fullContent) ? article.fullContent : article.content;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            content.setText(Html.fromHtml(empty(html) ? "" : html, Html.FROM_HTML_MODE_LEGACY));
        } else {
            content.setText(Html.fromHtml(empty(html) ? "" : html));
        }
        box.addView(content);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        Button favorite = secondaryButton(article.favorite ? "取消收藏" : "收藏");
        Button readToggle = secondaryButton(article.read ? "标为未读" : "标为已读");
        Button translate = secondaryButton("翻译");
        Button summarize = secondaryButton("摘要");
        Button open = secondaryButton("原文");
        actions.addView(favorite, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        actions.addView(readToggle, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        actions.addView(translate, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        actions.addView(summarize, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        actions.addView(open, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        box.addView(actions, topMargin(matchWrap(), dp(12)));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setView(scroll)
                .setNegativeButton("关闭", null)
                .create();

        favorite.setOnClickListener(v -> {
            Article current = repository.getArticle(article.id);
            boolean next = current == null || !current.favorite;
            repository.setFavorite(article.id, next, true);
            favorite.setText(next ? "取消收藏" : "收藏");
            loadArticles();
            runSync(false);
        });
        readToggle.setOnClickListener(v -> {
            Article current = repository.getArticle(article.id);
            boolean next = current == null || !current.read;
            repository.setRead(article.id, next, true);
            readToggle.setText(next ? "标为未读" : "标为已读");
            loadArticles();
            runSync(false);
        });
        translate.setOnClickListener(v -> runArticleTask(article.id, true, dialog));
        summarize.setOnClickListener(v -> runArticleTask(article.id, false, dialog));
        open.setOnClickListener(v -> {
            if (empty(article.link)) {
                toast("没有原文链接");
            } else {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(article.link)));
            }
        });

        dialog.show();
    }

    private void runArticleTask(long articleId, boolean translate, AlertDialog parentDialog) {
        ProgressDialog progress = ProgressDialog.show(this, null, translate ? "正在请求服务端翻译..." : "正在请求服务端摘要...", true, false);
        executor.execute(() -> {
            try {
                Article result = translate ? api.translateArticle(articleId) : api.summarizeArticle(articleId);
                if (translate) {
                    repository.updateArticleTranslation(articleId, result.translation);
                } else {
                    repository.updateArticleSummary(articleId, result.summary);
                }
                runOnUiThread(() -> {
                    progress.dismiss();
                    if (parentDialog != null && parentDialog.isShowing()) {
                        parentDialog.dismiss();
                    }
                    showArticle(articleId);
                    loadArticles();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    toast(e.getMessage());
                });
            }
        });
    }

    private void showMoreMenu() {
        String[] items = {
                "全量同步",
                "退出登录",
                "服务端地址"
        };
        new AlertDialog.Builder(this)
                .setItems(items, (dialog, which) -> {
                    if (which == 0) {
                        runSync(true);
                    } else if (which == 1) {
                        settings.clearSession();
                        repository.clearAll();
                        SyncScheduler.cancel(this);
                        buildLoginUi();
                    } else {
                        new AlertDialog.Builder(this)
                                .setTitle("服务端地址")
                                .setMessage(settings.getBaseUrl())
                                .setPositiveButton("确定", null)
                                .show();
                    }
                })
                .show();
    }

    private String articleLabel(Article article) {
        StringBuilder builder = new StringBuilder();
        if (!article.read) {
            builder.append("• ");
        }
        builder.append(article.title == null ? "" : article.title);
        if (article.favorite) {
            builder.append("  ★");
        }
        if (!empty(article.feedTitle)) {
            builder.append("\n").append(article.feedTitle);
        }
        if (!empty(article.summary)) {
            builder.append(" · 有摘要");
        }
        if (!empty(article.translation)) {
            builder.append(" · 有翻译");
        }
        return builder.toString();
    }

    private String parseTranslation(String translation) {
        if (empty(translation)) {
            return "";
        }
        try {
            JSONObject object = new JSONObject(translation);
            String title = object.optString("title", "");
            String content = object.optString("content", "");
            if (empty(title)) {
                return content;
            }
            return title + "\n\n" + content;
        } catch (Exception e) {
            return translation;
        }
    }

    private TextView sectionText(String text) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(14);
        view.setTextColor(Color.rgb(30, 40, 37));
        view.setPadding(dp(12), dp(10), dp(12), dp(10));
        view.setBackgroundColor(Color.rgb(235, 241, 238));
        return view;
    }

    private String formatDateLine(Article article) {
        String value = empty(article.publishedAt) ? article.createdAt : article.publishedAt;
        if (empty(value)) {
            return "";
        }
        return " · " + value.replace("T", " ").replace("Z", "");
    }

    private TextView headerButton(String text) {
        TextView button = new TextView(this);
        button.setText(text);
        button.setTextColor(Color.WHITE);
        button.setTextSize(15);
        button.setGravity(Gravity.CENTER);
        button.setPadding(dp(12), dp(8), dp(8), dp(8));
        return button;
    }

    private Button primaryButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextColor(Color.WHITE);
        button.setBackgroundColor(Color.rgb(23, 107, 91));
        return button;
    }

    private Button secondaryButton(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        return button;
    }

    private EditText input(String hint) {
        EditText input = new EditText(this);
        input.setHint(hint);
        input.setTextSize(15);
        input.setSingleLine(false);
        input.setMinHeight(dp(46));
        input.setPadding(dp(12), dp(8), dp(12), dp(8));
        return input;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
    }

    private LinearLayout.LayoutParams topMargin(LinearLayout.LayoutParams params, int margin) {
        params.topMargin = margin;
        return params;
    }

    private LinearLayout.LayoutParams paddedParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.leftMargin = dp(12);
        params.rightMargin = dp(12);
        return params;
    }

    private int dp(int value) {
        return (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value, getResources().getDisplayMetrics());
    }

    private int statusBarHeight() {
        int resourceId = getResources().getIdentifier("status_bar_height", "dimen", "android");
        return resourceId > 0 ? getResources().getDimensionPixelSize(resourceId) : 0;
    }

    private boolean empty(String value) {
        return value == null || value.trim().isEmpty();
    }

    private void status(String message) {
        if (statusText != null) {
            statusText.setText(message == null ? "" : message);
        }
    }

    private void toast(String message) {
        Toast.makeText(this, TextUtils.isEmpty(message) ? "操作失败" : message, Toast.LENGTH_LONG).show();
    }
}
