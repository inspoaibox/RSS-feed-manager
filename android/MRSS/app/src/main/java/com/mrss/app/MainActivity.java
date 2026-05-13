package com.mrss.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.provider.Settings;
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

import com.mrss.app.data.AppSettings;
import com.mrss.app.data.FeedRepository;
import com.mrss.app.data.OpmlUtils;
import com.mrss.app.model.AiChannel;
import com.mrss.app.model.Article;
import com.mrss.app.model.ArticleTranslation;
import com.mrss.app.model.Category;
import com.mrss.app.model.Feed;
import com.mrss.app.model.KeywordSubscription;
import com.mrss.app.model.OpmlFeed;
import com.mrss.app.model.ParsedFeed;
import com.mrss.app.model.Stats;
import com.mrss.app.model.TranslationJob;
import com.mrss.app.network.AiClient;
import com.mrss.app.network.FeedParser;
import com.mrss.app.network.GistClient;
import com.mrss.app.sync.SyncEngine;
import com.mrss.app.sync.SyncScheduler;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
    private static final int REQUEST_IMPORT_OPML = 1101;
    private static final int REQUEST_EXPORT_OPML = 1102;
    private static final int REQUEST_IMPORT_BACKUP = 1103;
    private static final int REQUEST_EXPORT_BACKUP = 1104;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ExecutorService syncExecutor = Executors.newSingleThreadExecutor();
    private final ExecutorService autoAiExecutor = Executors.newSingleThreadExecutor();
    private final ExecutorService manualAiExecutor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean autoAiRunning = new AtomicBoolean(false);
    private final AtomicBoolean manualAiRunning = new AtomicBoolean(false);
    private FeedRepository repository;
    private AppSettings settings;
    private final List<Category> categories = new ArrayList<>();
    private final List<Feed> feeds = new ArrayList<>();
    private final List<KeywordSubscription> keywordSubscriptions = new ArrayList<>();
    private final List<Article> articles = new ArrayList<>();
    private ArrayAdapter<Category> categoryAdapter;
    private ArrayAdapter<Feed> feedAdapter;
    private ArrayAdapter<Article> articleAdapter;
    private Spinner categorySpinner;
    private Spinner feedSpinner;
    private EditText searchInput;
    private Spinner sortSpinner;
    private Spinner dateSpinner;
    private CheckBox sortDescendingCheckbox;
    private CheckBox unreadOnlyCheckbox;
    private CheckBox favoritesOnlyCheckbox;
    private TextView statusText;
    private Button previousPageButton;
    private Button nextPageButton;
    private TextView pageInfoText;
    private LinearLayout drawerPanel;
    private View drawerScrim;
    private Long selectedCategoryId = null;
    private Long selectedFeedId = null;
    private Long selectedKeywordId = null;
    private int currentPage = 0;
    private int currentTotal = 0;
    private boolean suppressSelectionEvents = false;
    private boolean launchRefreshRunning = false;
    private boolean syncReceiverRegistered = false;
    private boolean filterLoadRunning = false;
    private boolean filterLoadPending = false;
    private boolean articleLoadRunning = false;
    private Integer pendingArticlePage = null;
    private long lastHandledSyncCompletedAt = 0L;
    private final BroadcastReceiver syncCompletedReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (!SyncEngine.ACTION_SYNC_COMPLETED.equals(intent.getAction())) {
                return;
            }
            int totalNew = intent.getIntExtra(SyncEngine.EXTRA_TOTAL_NEW, 0);
            int success = intent.getIntExtra(SyncEngine.EXTRA_SUCCESS, 0);
            int failed = intent.getIntExtra(SyncEngine.EXTRA_FAILED, 0);
            int candidates = intent.getIntExtra(SyncEngine.EXTRA_CANDIDATES, 0);
            int translated = intent.getIntExtra(SyncEngine.EXTRA_TRANSLATED, 0);
            int translationFailed = intent.getIntExtra(SyncEngine.EXTRA_TRANSLATION_FAILED, 0);
            onExternalSyncCompleted(totalNew, success, failed, candidates, translated, translationFailed, false);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        repository = new FeedRepository(this);
        settings = new AppSettings(this);
        if (settings.isBackgroundSyncEnabled()) {
            SyncScheduler.schedule(this);
        }
        requestNotificationPermissionIfNeeded();
        buildUi();
        loadFiltersAndArticles();
        autoRefreshOnLaunch();
    }

    @Override
    protected void onResume() {
        super.onResume();
        registerSyncCompletedReceiver();
        refreshIfSyncCompletedWhileAway();
    }

    @Override
    protected void onPause() {
        unregisterSyncCompletedReceiver();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        unregisterSyncCompletedReceiver();
        executor.shutdownNow();
        syncExecutor.shutdownNow();
        autoAiExecutor.shutdownNow();
        manualAiExecutor.shutdownNow();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) {
            return;
        }
        if (requestCode == REQUEST_IMPORT_OPML) {
            importOpml(data.getData());
        } else if (requestCode == REQUEST_EXPORT_OPML) {
            exportOpml(data.getData());
        } else if (requestCode == REQUEST_IMPORT_BACKUP) {
            restoreBackup(data.getData());
        } else if (requestCode == REQUEST_EXPORT_BACKUP) {
            exportBackup(data.getData());
        }
    }

    private void buildUi() {
        int padding = dp(16);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            getWindow().setStatusBarColor(Color.rgb(23, 107, 91));
            getWindow().setNavigationBarColor(Color.rgb(247, 248, 245));
        }

        FrameLayout frame = new FrameLayout(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(247, 248, 245));
        frame.addView(root, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(padding, dp(8) + statusBarHeight(), padding, dp(8));
        header.setBackgroundColor(Color.rgb(23, 107, 91));

        TextView menuButton = headerButton("☰ 分类");
        menuButton.setContentDescription("打开分类菜单");
        menuButton.setOnClickListener(v -> showCategoryDrawer());
        header.addView(menuButton);

        TextView title = new TextView(this);
        title.setText("MRSS");
        title.setTextColor(Color.WHITE);
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        TextView addButton = headerButton("添加");
        addButton.setContentDescription("添加订阅");
        addButton.setOnClickListener(v -> showAddFeedDialog());
        header.addView(addButton);

        TextView refreshButton = headerButton("刷新");
        refreshButton.setContentDescription("刷新订阅");
        refreshButton.setOnClickListener(v -> refreshAllFeeds());
        header.addView(refreshButton);

        TextView moreButton = headerButton("更多");
        moreButton.setContentDescription("更多功能");
        moreButton.setOnClickListener(v -> showMoreMenu());
        header.addView(moreButton);
        root.addView(header);

        LinearLayout filters = new LinearLayout(this);
        filters.setOrientation(LinearLayout.VERTICAL);
        filters.setPadding(padding, dp(8), padding, dp(8));

        categorySpinner = new Spinner(this);
        categoryAdapter = new ArrayAdapter<Category>(this, android.R.layout.simple_spinner_dropdown_item, categories) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getView(position, convertView, parent);
                view.setText(categoryLabel(getItem(position)));
                return view;
            }

            @Override
            public View getDropDownView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getDropDownView(position, convertView, parent);
                view.setText(categoryLabel(getItem(position)));
                return view;
            }
        };
        categorySpinner.setAdapter(categoryAdapter);
        categorySpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (suppressSelectionEvents || position < 0 || position >= categories.size()) {
                    return;
                }
                Category category = categories.get(position);
                selectedCategoryId = category.id <= 0 ? null : category.id;
                selectedFeedId = null;
                selectedKeywordId = null;
                refreshFeedSpinner();
                loadArticles();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
                selectedCategoryId = null;
            }
        });
        categorySpinner.setVisibility(View.GONE);

        feedSpinner = new Spinner(this);
        feedAdapter = new ArrayAdapter<Feed>(this, android.R.layout.simple_spinner_dropdown_item, feeds) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getView(position, convertView, parent);
                view.setText(feedLabel(getItem(position)));
                return view;
            }

            @Override
            public View getDropDownView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getDropDownView(position, convertView, parent);
                view.setText(feedLabel(getItem(position)));
                return view;
            }
        };
        feedSpinner.setAdapter(feedAdapter);
        feedSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (suppressSelectionEvents || position < 0 || position >= feeds.size()) {
                    return;
                }
                Feed feed = feeds.get(position);
                selectedFeedId = feed.id <= 0 ? null : feed.id;
                selectedKeywordId = null;
                loadArticles();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
                selectedFeedId = null;
            }
        });
        feedSpinner.setVisibility(View.GONE);

        LinearLayout searchRow = new LinearLayout(this);
        searchRow.setOrientation(LinearLayout.HORIZONTAL);
        searchRow.setGravity(Gravity.CENTER_VERTICAL);
        searchRow.setPadding(0, dp(8), 0, 0);
        searchInput = new EditText(this);
        searchInput.setSingleLine(true);
        searchInput.setHint("搜索标题、内容或订阅源");
        searchRow.addView(searchInput, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button searchButton = new Button(this);
        searchButton.setText("搜索");
        searchButton.setOnClickListener(v -> loadArticles());
        searchRow.addView(searchButton);
        filters.addView(searchRow);

        LinearLayout toggles = new LinearLayout(this);
        toggles.setOrientation(LinearLayout.HORIZONTAL);
        unreadOnlyCheckbox = new CheckBox(this);
        unreadOnlyCheckbox.setText("未读");
        unreadOnlyCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> loadArticles());
        toggles.addView(unreadOnlyCheckbox);
        favoritesOnlyCheckbox = new CheckBox(this);
        favoritesOnlyCheckbox.setText("收藏");
        favoritesOnlyCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> loadArticles());
        toggles.addView(favoritesOnlyCheckbox);
        sortDescendingCheckbox = new CheckBox(this);
        sortDescendingCheckbox.setText("降序");
        sortDescendingCheckbox.setChecked(true);
        sortDescendingCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> loadArticles());
        toggles.addView(sortDescendingCheckbox);
        Button markAllReadButton = new Button(this);
        markAllReadButton.setText("全部已读");
        markAllReadButton.setOnClickListener(v -> markAllRead());
        toggles.addView(markAllReadButton);
        filters.addView(toggles);

        LinearLayout sortDateRow = new LinearLayout(this);
        sortDateRow.setOrientation(LinearLayout.HORIZONTAL);
        sortDateRow.setGravity(Gravity.CENTER_VERTICAL);
        sortSpinner = new Spinner(this);
        sortSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{"发布时间", "抓取时间", "标题"}));
        sortSpinner.setOnItemSelectedListener(simpleSelectionListener());
        sortDateRow.addView(sortSpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        dateSpinner = new Spinner(this);
        dateSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{"全部日期", "今天", "昨天", "最近 7 天"}));
        dateSpinner.setOnItemSelectedListener(simpleSelectionListener());
        sortDateRow.addView(dateSpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        filters.addView(sortDateRow);

        statusText = new TextView(this);
        statusText.setTextColor(Color.rgb(80, 88, 84));
        statusText.setPadding(0, dp(6), 0, 0);
        filters.addView(statusText);
        root.addView(filters);

        ListView articleList = new ListView(this);
        articleList.setDivider(null);
        articleList.setDividerHeight(dp(8));
        articleList.setPadding(dp(10), dp(4), dp(10), dp(8));
        articleList.setClipToPadding(false);
        articleAdapter = new ArrayAdapter<Article>(this, android.R.layout.simple_list_item_2, android.R.id.text1, articles) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                Article article = getItem(position);
                return articleRowView(article, parent);
            }
        };
        articleList.setAdapter(articleAdapter);
        articleList.setOnItemClickListener((parent, view, position, id) -> openArticle(articles.get(position)));
        root.addView(articleList, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        LinearLayout pagerBar = new LinearLayout(this);
        pagerBar.setOrientation(LinearLayout.HORIZONTAL);
        pagerBar.setGravity(Gravity.CENTER_VERTICAL);
        pagerBar.setPadding(dp(10), dp(6), dp(10), dp(8));
        previousPageButton = new Button(this);
        previousPageButton.setText("上一页");
        previousPageButton.setOnClickListener(v -> loadPreviousPage());
        pagerBar.addView(previousPageButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        pageInfoText = new TextView(this);
        pageInfoText.setTextColor(Color.rgb(80, 88, 84));
        pageInfoText.setTextSize(14);
        pageInfoText.setGravity(Gravity.CENTER);
        pagerBar.addView(pageInfoText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        nextPageButton = new Button(this);
        nextPageButton.setText("下一页");
        nextPageButton.setOnClickListener(v -> loadNextPage());
        pagerBar.addView(nextPageButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        root.addView(pagerBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        drawerScrim = new View(this);
        drawerScrim.setBackgroundColor(0x66000000);
        drawerScrim.setVisibility(View.GONE);
        drawerScrim.setOnClickListener(v -> closeCategoryDrawer());
        frame.addView(drawerScrim, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));

        drawerPanel = new LinearLayout(this);
        drawerPanel.setOrientation(LinearLayout.VERTICAL);
        drawerPanel.setBackgroundColor(Color.WHITE);
        drawerPanel.setPadding(0, statusBarHeight(), 0, 0);
        drawerPanel.setVisibility(View.GONE);
        FrameLayout.LayoutParams drawerParams = new FrameLayout.LayoutParams(dp(304), ViewGroup.LayoutParams.MATCH_PARENT);
        drawerParams.gravity = Gravity.START;
        frame.addView(drawerPanel, drawerParams);

        setContentView(frame);
    }

    private View articleRowView(Article article, ViewGroup parent) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(14), dp(12), dp(14), dp(12));
        boolean read = article != null && article.read;
        card.setBackgroundColor(read ? Color.rgb(248, 250, 252) : Color.WHITE);
        card.setAlpha(read ? 0.72f : 1f);
        card.setMinimumHeight(dp(88));

        TextView title = new TextView(this);
        title.setSingleLine(false);
        title.setMaxLines(2);
        title.setEllipsize(TextUtils.TruncateAt.END);
        title.setTextColor(read ? Color.rgb(92, 103, 98) : Color.rgb(30, 40, 37));
        title.setTextSize(16);
        title.setTypeface(Typeface.DEFAULT, article != null && !article.read ? Typeface.BOLD : Typeface.NORMAL);
        String titleText = article == null ? "" : (read ? "" : "● ") + article.title;
        if (article != null && article.favorite) {
            titleText = "★ " + titleText;
        }
        title.setText(titleText);
        card.addView(title);

        TextView preview = new TextView(this);
        preview.setSingleLine(false);
        preview.setMaxLines(2);
        preview.setEllipsize(TextUtils.TruncateAt.END);
        preview.setTextColor(read ? Color.rgb(125, 135, 145) : Color.rgb(92, 103, 98));
        preview.setTextSize(13);
        preview.setPadding(0, dp(5), 0, dp(4));
        preview.setText(stripHtml(article == null ? "" : article.content));
        card.addView(preview);

        TextView meta = new TextView(this);
        meta.setSingleLine(true);
        meta.setEllipsize(TextUtils.TruncateAt.END);
        meta.setTextColor(Color.rgb(117, 126, 122));
        meta.setTextSize(12);
        meta.setText(articleSubtitle(article));
        card.addView(meta);

        AbsListView.LayoutParams params = new AbsListView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        card.setLayoutParams(params);
        return card;
    }

    private TextView headerButton(String text) {
        TextView button = new TextView(this);
        button.setText(text);
        button.setTextColor(Color.WHITE);
        button.setTextSize(15);
        button.setGravity(Gravity.CENTER);
        button.setClickable(true);
        button.setFocusable(true);
        button.setMinWidth(dp(52));
        button.setMinHeight(dp(44));
        button.setPadding(dp(10), dp(8), dp(10), dp(8));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            TypedValue typedValue = new TypedValue();
            getTheme().resolveAttribute(android.R.attr.selectableItemBackgroundBorderless, typedValue, true);
            button.setForeground(getDrawable(typedValue.resourceId));
        }
        return button;
    }

    private void requestNotificationPermissionIfNeeded() {
        if (android.os.Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 1201);
        }
    }

    private void registerSyncCompletedReceiver() {
        if (syncReceiverRegistered) {
            return;
        }
        IntentFilter filter = new IntentFilter(SyncEngine.ACTION_SYNC_COMPLETED);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(syncCompletedReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(syncCompletedReceiver, filter);
        }
        syncReceiverRegistered = true;
    }

    private void unregisterSyncCompletedReceiver() {
        if (!syncReceiverRegistered) {
            return;
        }
        try {
            unregisterReceiver(syncCompletedReceiver);
        } catch (IllegalArgumentException ignored) {
        }
        syncReceiverRegistered = false;
    }

    private void refreshIfSyncCompletedWhileAway() {
        long completedAt = settings == null ? 0L : settings.getLastSyncCompletedAt();
        if (completedAt <= 0 || completedAt <= lastHandledSyncCompletedAt) {
            return;
        }
        lastHandledSyncCompletedAt = completedAt;
        onExternalSyncCompleted(
                settings.getLastSyncTotalNew(),
                settings.getLastSyncSuccess(),
                settings.getLastSyncFailed(),
                settings.getLastSyncCandidates(),
                0,
                0,
                true
        );
    }

    private void onExternalSyncCompleted(int totalNew, int success, int failed, int candidates, int translated, int translationFailed, boolean fromResume) {
        if (settings != null) {
            lastHandledSyncCompletedAt = Math.max(lastHandledSyncCompletedAt, settings.getLastSyncCompletedAt());
        }
        loadFiltersAndArticles();
        if (totalNew > 0) {
            Toast.makeText(this, "已自动更新：新增 " + totalNew + " 篇，翻译 " + translated + " 篇", Toast.LENGTH_SHORT).show();
        } else if (translated > 0 || translationFailed > 0) {
            Toast.makeText(this, "自动翻译完成：成功 " + translated + "，失败 " + translationFailed, Toast.LENGTH_SHORT).show();
        } else if (fromResume && candidates > 0 && failed > 0) {
            Toast.makeText(this, "同步完成：成功 " + success + "，失败 " + failed, Toast.LENGTH_SHORT).show();
        }
    }

    private void showMoreMenu() {
        String[] actions = {"统计", "导入 OPML", "导出 OPML", "导出备份", "恢复备份", "分类管理", "订阅管理", "关键词管理", "数据同步", "AI 默认模型", "AI 渠道管理", "刷新设置"};
        new AlertDialog.Builder(this)
                .setTitle("更多")
                .setItems(actions, (dialog, which) -> {
                    if (which == 0) {
                        showStatsDialog();
                    } else if (which == 1) {
                        pickOpmlFile();
                    } else if (which == 2) {
                        createOpmlFile();
                    } else if (which == 3) {
                        createBackupFile();
                    } else if (which == 4) {
                        pickBackupFile();
                    } else if (which == 5) {
                        showCategoryManagement();
                    } else if (which == 6) {
                        showFeedManagement();
                    } else if (which == 7) {
                        showKeywordManagement();
                    } else if (which == 8) {
                        showDataSyncDialog();
                    } else if (which == 9) {
                        showAiDefaultModelDialog();
                    } else if (which == 10) {
                        showAiChannelManagementDialog();
                    } else {
                        showSettingsDialog();
                    }
                })
                .show();
    }

    private void showCategoryDrawer() {
        if (drawerPanel == null || drawerScrim == null) {
            return;
        }
        drawerScrim.setVisibility(View.VISIBLE);
        drawerPanel.setVisibility(View.VISIBLE);
        drawerPanel.removeAllViews();

        TextView loading = drawerSection("正在加载分类...");
        drawerPanel.addView(loading);

        executor.execute(() -> {
            List<Category> loadedCategories = repository.getCategories();
            List<Feed> loadedFeeds = repository.getFeeds();
            List<KeywordSubscription> loadedKeywords = repository.getKeywordSubscriptions();
            runOnUiThread(() -> populateCategoryDrawer(loadedCategories, loadedFeeds, loadedKeywords));
        });
    }

    private void populateCategoryDrawer(List<Category> loadedCategories, List<Feed> loadedFeeds, List<KeywordSubscription> loadedKeywords) {
        drawerPanel.removeAllViews();

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(16), dp(10), dp(8), dp(8));
        TextView title = new TextView(this);
        title.setText("分类");
        title.setTextColor(Color.rgb(30, 40, 37));
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView closeButton = drawerAction("关闭");
        closeButton.setOnClickListener(v -> closeCategoryDrawer());
        header.addView(closeButton);
        drawerPanel.addView(header);

        ScrollView scrollView = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        scrollView.addView(content);
        drawerPanel.addView(scrollView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1
        ));

        int totalArticles = 0;
        int totalUnread = 0;
        for (Feed feed : loadedFeeds) {
            totalArticles += feed.articleCount;
            totalUnread += feed.unreadCount;
        }

        TextView allItem = drawerItem("全部文章", totalArticles, totalUnread, selectedCategoryId == null && selectedFeedId == null && selectedKeywordId == null, 16);
        allItem.setOnClickListener(v -> selectScopeFromDrawer(null, null, null));
        content.addView(allItem);

        for (Category category : loadedCategories) {
            TextView categoryItem = drawerItem(category.name, category.feedCount, category.unreadCount, selectedKeywordId == null && selectedFeedId == null && selectedCategoryId != null && selectedCategoryId == category.id, 16);
            categoryItem.setOnClickListener(v -> selectScopeFromDrawer(category.id, null, null));
            categoryItem.setOnLongClickListener(v -> {
                showCategoryDrawerActions(category);
                return true;
            });
            content.addView(categoryItem);

            for (Feed feed : loadedFeeds) {
                if (feed.categoryId != null && feed.categoryId == category.id) {
                    TextView feedItem = drawerItem(feed.title, feed.articleCount, feed.unreadCount, selectedKeywordId == null && selectedFeedId != null && selectedFeedId == feed.id, 34);
                    feedItem.setOnClickListener(v -> selectScopeFromDrawer(feed.categoryId, feed.id, null));
                    feedItem.setOnLongClickListener(v -> {
                        showFeedDrawerActions(feed);
                        return true;
                    });
                    content.addView(feedItem);
                }
            }
        }

        boolean hasUncategorized = false;
        for (Feed feed : loadedFeeds) {
            if (feed.categoryId == null) {
                if (!hasUncategorized) {
                    content.addView(drawerSection("未分类订阅"));
                    hasUncategorized = true;
                }
                TextView feedItem = drawerItem(feed.title, feed.articleCount, feed.unreadCount, selectedKeywordId == null && selectedFeedId != null && selectedFeedId == feed.id, 34);
                feedItem.setOnClickListener(v -> selectScopeFromDrawer(null, feed.id, null));
                feedItem.setOnLongClickListener(v -> {
                    showFeedDrawerActions(feed);
                    return true;
                });
                content.addView(feedItem);
            }
        }

        content.addView(drawerSection("关键词订阅"));
        if (loadedKeywords.isEmpty()) {
            TextView empty = drawerItem("添加关键词订阅", 0, 0, false, 16);
            empty.setOnClickListener(v -> {
                closeCategoryDrawer();
                showKeywordEditDialog(null);
            });
            content.addView(empty);
        } else {
            for (KeywordSubscription keyword : loadedKeywords) {
                int count = repository.countArticles(null, null, keyword.id, false, false, "", 0, 0);
                TextView keywordItem = drawerItem(keyword.toString(), count, 0, selectedKeywordId != null && selectedKeywordId == keyword.id, 16);
                keywordItem.setOnClickListener(v -> selectScopeFromDrawer(null, null, keyword.id));
                keywordItem.setOnLongClickListener(v -> {
                    showKeywordDrawerActions(keyword);
                    return true;
                });
                content.addView(keywordItem);
            }
        }

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setPadding(dp(10), dp(8), dp(10), dp(12));
        TextView addFeed = drawerAction("添加订阅");
        addFeed.setOnClickListener(v -> {
            closeCategoryDrawer();
            showAddFeedDialog();
        });
        actions.addView(addFeed, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView manage = drawerAction("管理分类");
        manage.setOnClickListener(v -> {
            closeCategoryDrawer();
            showCategoryManagement();
        });
        actions.addView(manage, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView addKeyword = drawerAction("关键词");
        addKeyword.setOnClickListener(v -> {
            closeCategoryDrawer();
            showKeywordEditDialog(null);
        });
        actions.addView(addKeyword, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        drawerPanel.addView(actions);
    }

    private TextView drawerItem(String title, int count, int unread, boolean selected, int leftPadding) {
        TextView item = new TextView(this);
        StringBuilder label = new StringBuilder(title == null || title.trim().isEmpty() ? "未命名" : title);
        if (unread > 0) {
            label.append("  ").append(unread).append(" 未读");
        } else if (count > 0) {
            label.append("  ").append(count);
        }
        item.setText(label.toString());
        item.setSingleLine(true);
        item.setEllipsize(TextUtils.TruncateAt.END);
        item.setTextColor(selected ? Color.rgb(23, 107, 91) : Color.rgb(30, 40, 37));
        item.setTypeface(Typeface.DEFAULT, selected ? Typeface.BOLD : Typeface.NORMAL);
        item.setTextSize(leftPadding > 20 ? 14 : 16);
        item.setGravity(Gravity.CENTER_VERTICAL);
        item.setMinHeight(dp(46));
        item.setPadding(dp(leftPadding), 0, dp(14), 0);
        item.setBackgroundColor(selected ? Color.rgb(232, 244, 240) : Color.WHITE);
        item.setClickable(true);
        item.setFocusable(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            TypedValue typedValue = new TypedValue();
            getTheme().resolveAttribute(android.R.attr.selectableItemBackground, typedValue, true);
            item.setForeground(getDrawable(typedValue.resourceId));
        }
        return item;
    }

    private TextView drawerSection(String text) {
        TextView section = new TextView(this);
        section.setText(text);
        section.setTextColor(Color.rgb(92, 103, 98));
        section.setTextSize(13);
        section.setTypeface(Typeface.DEFAULT_BOLD);
        section.setPadding(dp(16), dp(14), dp(14), dp(6));
        return section;
    }

    private TextView drawerAction(String text) {
        TextView action = new TextView(this);
        action.setText(text);
        action.setTextColor(Color.rgb(23, 107, 91));
        action.setTextSize(14);
        action.setGravity(Gravity.CENTER);
        action.setMinHeight(dp(42));
        action.setClickable(true);
        action.setFocusable(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            TypedValue typedValue = new TypedValue();
            getTheme().resolveAttribute(android.R.attr.selectableItemBackground, typedValue, true);
            action.setForeground(getDrawable(typedValue.resourceId));
        }
        return action;
    }

    private void selectScopeFromDrawer(Long categoryId, Long feedId) {
        selectScopeFromDrawer(categoryId, feedId, null);
    }

    private void selectScopeFromDrawer(Long categoryId, Long feedId, Long keywordId) {
        selectedCategoryId = categoryId;
        selectedFeedId = feedId;
        selectedKeywordId = keywordId;
        closeCategoryDrawer();
        loadFiltersAndArticles();
    }

    private void showCategoryDrawerActions(Category category) {
        if (category == null || category.id <= 0) {
            return;
        }
        String[] actions = {"打开分类", "重命名分类", "删除分类"};
        new AlertDialog.Builder(this)
                .setTitle(category.name)
                .setItems(actions, (dialog, which) -> {
                    if (which == 0) {
                        selectScopeFromDrawer(category.id, null);
                    } else if (which == 1) {
                        closeCategoryDrawer();
                        showCategoryEditDialog(category);
                    } else {
                        closeCategoryDrawer();
                        confirmDeleteCategory(category, null);
                    }
                })
                .show();
    }

    private void showFeedDrawerActions(Feed feed) {
        if (feed == null || feed.id <= 0) {
            return;
        }
        String[] actions = {"打开订阅", "编辑订阅", "删除订阅"};
        new AlertDialog.Builder(this)
                .setTitle(feed.title)
                .setItems(actions, (dialog, which) -> {
                    if (which == 0) {
                        selectScopeFromDrawer(feed.categoryId, feed.id);
                    } else if (which == 1) {
                        closeCategoryDrawer();
                        showFeedEditDialog(feed);
                    } else {
                        closeCategoryDrawer();
                        confirmDeleteFeed(feed, null);
                    }
                })
                .show();
    }

    private void showKeywordDrawerActions(KeywordSubscription keyword) {
        if (keyword == null || keyword.id <= 0) {
            return;
        }
        String[] actions = {"打开关键词", "编辑关键词", "删除关键词"};
        new AlertDialog.Builder(this)
                .setTitle(keyword.toString())
                .setItems(actions, (dialog, which) -> {
                    if (which == 0) {
                        selectScopeFromDrawer(null, null, keyword.id);
                    } else if (which == 1) {
                        closeCategoryDrawer();
                        showKeywordEditDialog(keyword);
                    } else {
                        closeCategoryDrawer();
                        confirmDeleteKeyword(keyword);
                    }
                })
                .show();
    }

    private void showKeywordEditDialog(KeywordSubscription keyword) {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);

        EditText nameInput = new EditText(this);
        nameInput.setSingleLine(true);
        nameInput.setHint("显示名称，如 爱情");
        nameInput.setText(keyword == null ? "" : keyword.name);
        form.addView(labeledView("名称", nameInput));

        EditText keywordInput = new EditText(this);
        keywordInput.setSingleLine(true);
        keywordInput.setHint("关键词，如 爱情");
        keywordInput.setText(keyword == null ? "" : keyword.keyword);
        form.addView(labeledView("关键词", keywordInput));

        CheckBox activeInput = new CheckBox(this);
        activeInput.setText("启用关键词订阅");
        activeInput.setChecked(keyword == null || keyword.active);
        form.addView(activeInput);

        new AlertDialog.Builder(this)
                .setTitle(keyword == null ? "新增关键词订阅" : "编辑关键词订阅")
                .setView(form)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存", (dialog, which) -> {
                    String keywordText = keywordInput.getText().toString().trim();
                    String name = nameInput.getText().toString().trim();
                    if (keywordText.isEmpty()) {
                        Toast.makeText(this, "请输入关键词", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    executor.execute(() -> {
                        try {
                            if (keyword == null) {
                                repository.createKeywordSubscription(name, keywordText);
                            } else {
                                repository.updateKeywordSubscription(keyword.id, name, keywordText, activeInput.isChecked());
                            }
                            runOnUiThread(() -> {
                                Toast.makeText(this, "关键词订阅已保存", Toast.LENGTH_SHORT).show();
                                loadFiltersAndArticles();
                            });
                        } catch (Exception e) {
                            runOnUiThread(() -> Toast.makeText(this, "保存失败：" + e.getMessage(), Toast.LENGTH_LONG).show());
                        }
                    });
                })
                .show();
    }

    private void confirmDeleteKeyword(KeywordSubscription keyword) {
        new AlertDialog.Builder(this)
                .setTitle("删除关键词订阅")
                .setMessage("删除“" + keyword.toString() + "”？文章不会被删除。")
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (dialog, which) -> executor.execute(() -> {
                    repository.deleteKeywordSubscription(keyword.id);
                    runOnUiThread(() -> {
                        if (selectedKeywordId != null && selectedKeywordId == keyword.id) {
                            selectedKeywordId = null;
                        }
                        Toast.makeText(this, "关键词订阅已删除", Toast.LENGTH_SHORT).show();
                        loadFiltersAndArticles();
                    });
                }))
                .show();
    }

    private void closeCategoryDrawer() {
        if (drawerScrim != null) {
            drawerScrim.setVisibility(View.GONE);
        }
        if (drawerPanel != null) {
            drawerPanel.setVisibility(View.GONE);
        }
    }

    private void showAddFeedDialog() {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);

        EditText input = new EditText(this);
        input.setHint("https://example.com/feed.xml");
        input.setSingleLine(true);
        form.addView(input);

        List<Category> categoryOptions = categoryOptions(true);
        Spinner categoryInput = spinnerForCategories(categoryOptions);
        form.addView(labeledView("分类", categoryInput));

        int[] intervals = intervalValues();
        Spinner intervalInput = spinnerForIntervals(intervals);
        selectInterval(intervalInput, intervals, settings.getDefaultFetchIntervalSeconds());
        form.addView(labeledView("同步间隔", intervalInput));

        CheckBox translateInput = new CheckBox(this);
        translateInput.setText("自动 AI 翻译");
        form.addView(translateInput);

        EditText languageInput = new EditText(this);
        languageInput.setSingleLine(true);
        languageInput.setText(settings.getDefaultTranslationLanguage());
        form.addView(labeledView("翻译为", languageInput));

        new AlertDialog.Builder(this)
                .setTitle("添加订阅")
                .setView(form)
                .setNegativeButton("取消", null)
                .setPositiveButton("添加", (dialog, which) -> {
                    String url = input.getText().toString().trim();
                    if (!url.startsWith("http://") && !url.startsWith("https://")) {
                        Toast.makeText(this, "请输入完整的 http/https 地址", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    Category selectedCategory = categoryOptions.get(categoryInput.getSelectedItemPosition());
                    Long categoryId = selectedCategory.id <= 0 ? null : selectedCategory.id;
                    int interval = intervals[intervalInput.getSelectedItemPosition()];
                    addFeed(url, categoryId, interval, translateInput.isChecked(), languageInput.getText().toString().trim());
                })
                .show();
    }

    private void addFeed(String url, Long categoryId, int intervalSeconds, boolean translateEnabled, String translationLanguage) {
        ProgressDialog progress = ProgressDialog.show(this, "添加订阅", "正在抓取 RSS...", true, false);
        syncExecutor.execute(() -> {
            try {
                ParsedFeed parsedFeed = new FeedParser().fetchAndParse(url);
                repository.addFeed(url, parsedFeed, categoryId, intervalSeconds, translateEnabled, translationLanguage);
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "订阅已添加", Toast.LENGTH_SHORT).show();
                    if (settings.isBackgroundSyncEnabled()) {
                        SyncScheduler.schedule(this);
                    }
                    loadFiltersAndArticles();
                });
                if (translateEnabled) {
                    scheduleAutoTranslation();
                }
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "添加失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void autoRefreshOnLaunch() {
        if (launchRefreshRunning) {
            return;
        }
        launchRefreshRunning = true;
        statusText.setText("正在后台同步，已优先显示本地文章...");
        syncExecutor.execute(() -> {
            RefreshResult result = refreshFeedsInScope(null, null);
                runOnUiThread(() -> {
                    launchRefreshRunning = false;
                    settings.markSyncCompleted(result.inserted, result.success, result.failed, result.candidates);
                lastHandledSyncCompletedAt = settings.getLastSyncCompletedAt();
                if (settings.isBackgroundSyncEnabled()) {
                    SyncScheduler.schedule(this);
                }
                loadFiltersAndArticles();
                if (result.candidates > 0) {
                    statusText.setText("启动同步完成：成功 " + result.success + "，失败 " + result.failed + "，新增 " + result.inserted + " 篇");
                }
            });
            if (result.inserted > 0) {
                scheduleAutoTranslation();
            }
        });
    }

    private void refreshAllFeeds() {
        ProgressDialog progress = ProgressDialog.show(this, "刷新订阅", "正在同步本地订阅源...", true, false);
        syncExecutor.execute(() -> {
            RefreshResult result = refreshFeedsInScope(selectedCategoryId, selectedFeedId);
            runOnUiThread(() -> {
                progress.dismiss();
                settings.markSyncCompleted(result.inserted, result.success, result.failed, result.candidates);
                lastHandledSyncCompletedAt = settings.getLastSyncCompletedAt();
                if (result.candidates == 0) {
                    Toast.makeText(this, "当前范围没有可刷新的订阅，请先添加 RSS 链接。", Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(this, "刷新完成：成功 " + result.success + "，失败 " + result.failed + "，新增 " + result.inserted, Toast.LENGTH_LONG).show();
                }
                if (settings.isBackgroundSyncEnabled()) {
                    SyncScheduler.schedule(this);
                }
                loadFiltersAndArticles();
                if (result.inserted > 0) {
                    scheduleAutoTranslation();
                }
            });
        });
    }

    private RefreshResult refreshFeedsInScope(Long categoryId, Long feedId) {
        RefreshResult result = new RefreshResult();
        FeedParser parser = new FeedParser();
        List<Feed> currentFeeds = repository.getFeeds();
        for (Feed feed : currentFeeds) {
            if (feed.id <= 0 || !feed.active) {
                continue;
            }
            if (feedId != null && feed.id != feedId) {
                continue;
            }
            if (feedId == null && categoryId != null && (feed.categoryId == null || !feed.categoryId.equals(categoryId))) {
                continue;
            }
            result.candidates++;
            try {
                ParsedFeed parsedFeed = parser.fetchAndParse(feed.url);
                result.inserted += repository.refreshFeed(feed, parsedFeed);
                result.success++;
            } catch (Exception e) {
                repository.markFeedError(feed.id, e.getMessage());
                result.failed++;
            }
        }
        return result;
    }

    private void translatePendingArticles() {
        AiChannel channel = repository.getDefaultAiChannel();
        if (channel == null || channel.apiKey == null || channel.apiKey.trim().isEmpty() || channel.model == null || channel.model.trim().isEmpty()) {
            runOnUiThread(() -> statusText.setText("自动翻译未执行：请先设置默认 AI 渠道和模型"));
            return;
        }

        AiClient client = new AiClient();
        int translated = 0;
        int failed = 0;
        while (true) {
            List<TranslationJob> jobs = repository.pendingTranslationJobs(5);
            if (jobs.isEmpty()) {
                int finalTranslated = translated;
                int finalFailed = failed;
                runOnUiThread(() -> {
                    if (finalTranslated > 0 || finalFailed > 0) {
                        loadFiltersAndArticles();
                        Toast.makeText(this, "自动翻译完成：成功 " + finalTranslated + "，失败 " + finalFailed, Toast.LENGTH_LONG).show();
                    }
                });
                return;
            }

            for (TranslationJob job : jobs) {
                try {
                    ArticleTranslation translation = client.translate(channel, job);
                    repository.saveTranslation(job.articleId, job.targetLanguage, translation);
                    translated++;
                } catch (Exception e) {
                    repository.markTranslationFailed(job.articleId, e.getMessage());
                    failed++;
                }
            }
        }
    }

    private void scheduleAutoTranslation() {
        if (repository.countPendingTranslationJobs() <= 0) {
            return;
        }
        if (!autoAiRunning.compareAndSet(false, true)) {
            return;
        }
        runOnUiThread(() -> statusText.setText("正在自动 AI 翻译待处理文章..."));
        autoAiExecutor.execute(() -> {
            try {
                translatePendingArticles();
            } finally {
                autoAiRunning.set(false);
            }
        });
    }

    private void loadFiltersAndArticles() {
        if (filterLoadRunning) {
            filterLoadPending = true;
            return;
        }
        filterLoadRunning = true;
        executor.execute(() -> {
            List<Category> loadedCategories = repository.getCategories();
            Category allCategory = new Category();
            allCategory.id = 0;
            allCategory.name = "全部分类";
            loadedCategories.add(0, allCategory);

            List<Feed> loadedFeeds = repository.getFeeds();
            List<KeywordSubscription> loadedKeywords = repository.getKeywordSubscriptions();
            Feed allFeed = new Feed();
            allFeed.id = 0;
            allFeed.title = selectedKeywordId == null ? "全部文章" : "关键词文章";
            for (Feed feed : loadedFeeds) {
                allFeed.articleCount += feed.articleCount;
                allFeed.unreadCount += feed.unreadCount;
            }
            loadedFeeds.add(0, allFeed);
            runOnUiThread(() -> {
                categories.clear();
                categories.addAll(loadedCategories);
                keywordSubscriptions.clear();
                keywordSubscriptions.addAll(loadedKeywords);
                categoryAdapter.notifyDataSetChanged();
                feeds.clear();
                feeds.addAll(filterFeedsForSelectedCategory(loadedFeeds));
                feedAdapter.notifyDataSetChanged();
                suppressSelectionEvents = true;
                if (!categories.isEmpty()) {
                    categorySpinner.setSelection(categoryIndexFor(selectedCategoryId), false);
                }
                if (!feeds.isEmpty()) {
                    feedSpinner.setSelection(feedIndexFor(selectedFeedId), false);
                }
                suppressSelectionEvents = false;
                filterLoadRunning = false;
                loadArticles();
                if (filterLoadPending) {
                    filterLoadPending = false;
                    loadFiltersAndArticles();
                }
            });
        });
    }

    private void refreshFeedSpinner() {
        executor.execute(() -> {
            List<Feed> loadedFeeds = repository.getFeeds();
            Feed allFeed = new Feed();
            allFeed.id = 0;
            allFeed.title = selectedCategoryId == null ? "全部文章" : "该分类全部文章";
            for (Feed feed : loadedFeeds) {
                if (selectedCategoryId == null || (feed.categoryId != null && feed.categoryId.equals(selectedCategoryId))) {
                    allFeed.articleCount += feed.articleCount;
                    allFeed.unreadCount += feed.unreadCount;
                }
            }
            loadedFeeds.add(0, allFeed);
            runOnUiThread(() -> {
                feeds.clear();
                feeds.addAll(filterFeedsForSelectedCategory(loadedFeeds));
                feedAdapter.notifyDataSetChanged();
                suppressSelectionEvents = true;
                if (!feeds.isEmpty()) {
                    feedSpinner.setSelection(0);
                }
                suppressSelectionEvents = false;
            });
        });
    }

    private int categoryIndexFor(Long categoryId) {
        for (int i = 0; i < categories.size(); i++) {
            Category category = categories.get(i);
            if (categoryId == null && category.id <= 0) {
                return i;
            }
            if (categoryId != null && category.id == categoryId) {
                return i;
            }
        }
        selectedCategoryId = null;
        return 0;
    }

    private int feedIndexFor(Long feedId) {
        for (int i = 0; i < feeds.size(); i++) {
            Feed feed = feeds.get(i);
            if (feedId == null && feed.id <= 0) {
                return i;
            }
            if (feedId != null && feed.id == feedId) {
                return i;
            }
        }
        selectedFeedId = null;
        return 0;
    }

    private List<Feed> filterFeedsForSelectedCategory(List<Feed> source) {
        if (selectedCategoryId == null) {
            return source;
        }
        List<Feed> filtered = new ArrayList<>();
        for (Feed feed : source) {
            if (feed.id <= 0 || (feed.categoryId != null && feed.categoryId.equals(selectedCategoryId))) {
                filtered.add(feed);
            }
        }
        return filtered;
    }

    private static class RefreshResult {
        int candidates;
        int success;
        int failed;
        int inserted;
    }

    private void loadArticles() {
        currentPage = 0;
        loadArticlesPage(currentPage);
    }

    private void loadPreviousPage() {
        if (currentPage <= 0) {
            return;
        }
        loadArticlesPage(currentPage - 1);
    }

    private void loadNextPage() {
        if ((currentPage + 1) * currentPageSize() >= currentTotal) {
            return;
        }
        loadArticlesPage(currentPage + 1);
    }

    private void loadArticlesPage(int page) {
        if (repository == null || articleAdapter == null) {
            return;
        }
        if (articleLoadRunning) {
            pendingArticlePage = Math.max(0, page);
            return;
        }
        articleLoadRunning = true;
        Long feedId = selectedFeedId;
        Long categoryId = selectedKeywordId == null && selectedFeedId == null ? selectedCategoryId : null;
        Long keywordId = selectedKeywordId;
        boolean unread = unreadOnlyCheckbox != null && unreadOnlyCheckbox.isChecked();
        boolean favorites = favoritesOnlyCheckbox != null && favoritesOnlyCheckbox.isChecked();
        String query = searchInput == null ? "" : searchInput.getText().toString();
        long[] dateRange = selectedDateRange();
        String sortBy = selectedSortBy();
        boolean descending = sortDescendingCheckbox == null || sortDescendingCheckbox.isChecked();
        int pageSize = currentPageSize();
        int targetPage = Math.max(0, page);
        executor.execute(() -> {
            int total = repository.countArticles(feedId, categoryId, keywordId, unread, favorites, query, dateRange[0], dateRange[1]);
            int maxPage = total <= 0 ? 0 : (total - 1) / pageSize;
            int safePage = Math.min(targetPage, maxPage);
            int safeOffset = safePage * pageSize;
            List<Article> loadedArticles = repository.getArticles(feedId, categoryId, keywordId, unread, favorites, query, dateRange[0], dateRange[1], sortBy, descending, pageSize, safeOffset);
            runOnUiThread(() -> {
                articles.clear();
                articles.addAll(loadedArticles);
                currentPage = safePage;
                currentTotal = total;
                updateArticleListPresentation();
                articleLoadRunning = false;
                if (pendingArticlePage != null) {
                    int nextPage = pendingArticlePage;
                    pendingArticlePage = null;
                    loadArticlesPage(nextPage);
                }
            });
        });
    }

    private void updateArticleListPresentation() {
        if (articleAdapter != null) {
            articleAdapter.notifyDataSetChanged();
        }
        if (statusText != null) {
            statusText.setText(statusLabel());
        }
        if (previousPageButton != null) {
            previousPageButton.setEnabled(currentPage > 0);
        }
        if (nextPageButton != null) {
            nextPageButton.setEnabled((currentPage + 1) * currentPageSize() < currentTotal);
        }
        if (pageInfoText != null) {
            int totalPages = totalPages();
            pageInfoText.setText(totalPages <= 0 ? "0 / 0" : (currentPage + 1) + " / " + totalPages);
        }
    }

    private int currentPageSize() {
        return settings == null ? 50 : settings.getArticlePageSize();
    }

    private int totalPages() {
        int pageSize = currentPageSize();
        return currentTotal <= 0 ? 0 : (currentTotal + pageSize - 1) / pageSize;
    }

    private void openArticle(Article article) {
        if (article == null) {
            return;
        }
        repository.markRead(article.id);
        article.read = true;
        updateArticleListPresentation();

        LinearLayout dialogRoot = new LinearLayout(this);
        dialogRoot.setOrientation(LinearLayout.VERTICAL);
        ScrollView scrollView = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(20), dp(16), dp(20), dp(16));
        scrollView.addView(content);

        LinearLayout titleRow = new LinearLayout(this);
        titleRow.setOrientation(LinearLayout.HORIZONTAL);
        titleRow.setGravity(Gravity.CENTER_VERTICAL);
        content.addView(titleRow);

        TextView title = new TextView(this);
        title.setText(articleTitle(article));
        title.setTextSize(22);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(30, 40, 37));
        titleRow.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button aiTranslateButton = new Button(this);
        aiTranslateButton.setText("AI翻译");
        aiTranslateButton.setTextSize(13);
        titleRow.addView(aiTranslateButton, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView topCloseButton = new TextView(this);
        topCloseButton.setText("×");
        topCloseButton.setTextSize(24);
        topCloseButton.setGravity(Gravity.CENTER);
        topCloseButton.setTextColor(Color.rgb(90, 98, 94));
        topCloseButton.setMinWidth(dp(44));
        topCloseButton.setMinHeight(dp(44));
        titleRow.addView(topCloseButton);

        TextView meta = new TextView(this);
        meta.setText(articleSubtitle(article));
        meta.setTextColor(Color.rgb(90, 98, 94));
        meta.setPadding(0, dp(8), 0, dp(16));
        content.addView(meta);

        LinearLayout actionRow = new LinearLayout(this);
        actionRow.setOrientation(LinearLayout.HORIZONTAL);
        actionRow.setGravity(Gravity.CENTER_VERTICAL);
        Button unreadButton = new Button(this);
        unreadButton.setText("标为未读");
        actionRow.addView(unreadButton);
        content.addView(actionRow);

        TextView body = new TextView(this);
        body.setTextSize(16);
        body.setTextColor(Color.rgb(30, 40, 37));
        body.setLineSpacing(0, 1.2f);
        setArticleBody(body, articleContent(article));
        content.addView(body);

        int screenHeight = getResources().getDisplayMetrics().heightPixels;
        int scrollHeight = Math.min(dp(620), Math.max(dp(280), (int) (screenHeight * 0.62f)));
        dialogRoot.addView(scrollView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                scrollHeight
        ));

        LinearLayout footer = new LinearLayout(this);
        footer.setOrientation(LinearLayout.HORIZONTAL);
        footer.setGravity(Gravity.CENTER_VERTICAL);
        footer.setPadding(dp(12), dp(8), dp(12), dp(12));
        Button favoriteButton = new Button(this);
        favoriteButton.setText(article.favorite ? "取消收藏" : "收藏");
        favoriteButton.setTextSize(13);
        favoriteButton.setSingleLine(true);
        footer.addView(favoriteButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button shareButton = new Button(this);
        shareButton.setText("分享");
        shareButton.setTextSize(13);
        shareButton.setSingleLine(true);
        footer.addView(shareButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button linkButton = new Button(this);
        linkButton.setText("网页");
        linkButton.setTextSize(13);
        linkButton.setSingleLine(true);
        footer.addView(linkButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button originalButton = new Button(this);
        originalButton.setText(article.showOriginal ? "译文" : "原文");
        originalButton.setTextSize(13);
        originalButton.setSingleLine(true);
        originalButton.setVisibility(hasTranslation(article) ? View.VISIBLE : View.GONE);
        footer.addView(originalButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        dialogRoot.addView(footer);

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setView(dialogRoot)
                .create();
        aiTranslateButton.setOnClickListener(v -> translateArticleManually(article, title, body, meta, originalButton));
        originalButton.setOnClickListener(v -> {
            article.showOriginal = !article.showOriginal;
            title.setText(articleTitle(article));
            setArticleBody(body, articleContent(article));
            meta.setText(articleSubtitle(article));
            originalButton.setText(article.showOriginal ? "译文" : "原文");
        });
        favoriteButton.setOnClickListener(v -> {
            boolean favorite = repository.toggleFavorite(article.id);
            article.favorite = favorite;
            updateArticleListPresentation();
            favoriteButton.setText(favorite ? "取消收藏" : "收藏");
        });
        linkButton.setOnClickListener(v -> {
            if (article.link != null && !article.link.trim().isEmpty()) {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(article.link)));
            }
        });
        shareButton.setOnClickListener(v -> shareArticle(article));
        topCloseButton.setOnClickListener(v -> dialog.dismiss());
        unreadButton.setOnClickListener(v -> {
            repository.markUnread(article.id);
            article.read = false;
            updateArticleListPresentation();
            Toast.makeText(this, "已标为未读", Toast.LENGTH_SHORT).show();
        });
        dialog.show();
        if (dialog.getWindow() != null) {
            int width = getResources().getDisplayMetrics().widthPixels - dp(24);
            dialog.getWindow().setLayout(width, ViewGroup.LayoutParams.WRAP_CONTENT);
        }
    }

    private void translateArticleManually(Article article, TextView titleView, TextView bodyView, TextView metaView, Button originalButton) {
        if (article == null) {
            return;
        }
        AiChannel channel = repository.getDefaultAiChannel();
        if (channel == null || channel.apiKey == null || channel.apiKey.trim().isEmpty() || channel.model == null || channel.model.trim().isEmpty()) {
            Toast.makeText(this, "请先在 AI 翻译设置里选择默认渠道和模型", Toast.LENGTH_LONG).show();
            return;
        }
        String targetLanguage = article.translationLanguage == null || article.translationLanguage.trim().isEmpty()
                ? settings.getDefaultTranslationLanguage()
                : article.translationLanguage;
        String originalTitle = hasTranslation(article) && article.originalTitle != null && !article.originalTitle.trim().isEmpty()
                ? article.originalTitle
                : (article.title == null ? "" : article.title);
        String originalContent = hasTranslation(article) && article.originalContent != null && !article.originalContent.trim().isEmpty()
                ? article.originalContent
                : (article.content == null ? "" : article.content);
        int sourceLength = (originalContent == null || originalContent.trim().isEmpty() ? originalTitle : originalContent).length();

        if (!manualAiRunning.compareAndSet(false, true)) {
            Toast.makeText(this, "已有手动 AI 翻译正在进行", Toast.LENGTH_SHORT).show();
            return;
        }
        ProgressDialog progress = new ProgressDialog(this);
        long startedAt = System.currentTimeMillis();
        progress.setMessage(manualAiMessage("准备请求", startedAt, sourceLength));
        progress.setCancelable(false);
        progress.show();
        AtomicBoolean manualTaskActive = new AtomicBoolean(true);
        manualAiExecutor.submit(() -> {
            try {
                TranslationJob job = new TranslationJob();
                job.articleId = article.id;
                job.feedId = article.feedId;
                job.title = originalTitle;
                job.content = originalContent;
                job.link = article.link;
                job.targetLanguage = targetLanguage;
                ArticleTranslation translation = new AiClient().translate(channel, job, stage ->
                        runOnUiThread(() -> {
                            if (manualTaskActive.get() && progress.isShowing()) {
                                progress.setMessage(manualAiMessage(stage, startedAt, sourceLength));
                            }
                        }));
                if (!manualTaskActive.get()) {
                    return;
                }
                runOnUiThread(() -> {
                    if (manualTaskActive.get() && progress.isShowing()) {
                        progress.setMessage(manualAiMessage("保存结果", startedAt, sourceLength));
                    }
                });
                if (!manualTaskActive.get()) {
                    return;
                }
                repository.saveTranslation(article.id, targetLanguage, translation, originalTitle, originalContent);
                if (!manualTaskActive.get()) {
                    return;
                }
                Article savedArticle = repository.getArticle(article.id);
                if (savedArticle == null || !hasTranslation(savedArticle)) {
                    throw new IllegalStateException("翻译结果保存后无法从本地数据库读取");
                }
                copyArticleState(article, savedArticle);
                article.showOriginal = false;
                runOnUiThread(() -> {
                    if (!manualTaskActive.compareAndSet(true, false)) {
                        return;
                    }
                    manualAiRunning.set(false);
                    progress.dismiss();
                    titleView.setText(articleTitle(article));
                    setArticleBody(bodyView, articleContent(article));
                    metaView.setText(articleSubtitle(article));
                    if (originalButton != null) {
                        originalButton.setText("原文");
                        originalButton.setVisibility(View.VISIBLE);
                    }
                    updateArticleListPresentation();
                    Toast.makeText(this, "AI 翻译完成，已保存到本地，用时 " + elapsedSeconds(startedAt) + " 秒", Toast.LENGTH_SHORT).show();
                });
            } catch (Exception e) {
                if (manualTaskActive.get()) {
                    repository.markTranslationFailed(article.id, e.getMessage());
                }
                runOnUiThread(() -> {
                    if (!manualTaskActive.compareAndSet(true, false)) {
                        return;
                    }
                    manualAiRunning.set(false);
                    progress.dismiss();
                    Toast.makeText(this, "AI 翻译失败：" + e.getMessage() + "（用时 " + elapsedSeconds(startedAt) + " 秒，正文 " + sourceLength + " 字符）", Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private String manualAiMessage(String stage, long startedAt, int sourceLength) {
        return "正在 AI 翻译：" + stage + "\n已用时 " + elapsedSeconds(startedAt) + " 秒，正文 " + sourceLength + " 字符";
    }

    private long elapsedSeconds(long startedAt) {
        return Math.max(0, (System.currentTimeMillis() - startedAt + 500) / 1000);
    }

    private void copyArticleState(Article target, Article source) {
        if (target == null || source == null) {
            return;
        }
        target.feedTitle = source.feedTitle;
        target.guid = source.guid;
        target.link = source.link;
        target.title = source.title;
        target.content = source.content;
        target.originalTitle = source.originalTitle;
        target.originalContent = source.originalContent;
        target.translationLanguage = source.translationLanguage;
        target.translationStatus = source.translationStatus;
        target.translationError = source.translationError;
        target.author = source.author;
        target.publishedAt = source.publishedAt;
        target.createdAt = source.createdAt;
        target.read = source.read;
        target.favorite = source.favorite;
    }

    private void setArticleBody(TextView body, String html) {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
            body.setText(Html.fromHtml(html, Html.FROM_HTML_MODE_LEGACY));
        } else {
            body.setText(Html.fromHtml(html));
        }
    }

    private void shareArticle(Article article) {
        if (article == null) {
            return;
        }
        StringBuilder text = new StringBuilder();
        String title = articleTitle(article);
        if (!title.trim().isEmpty()) {
            text.append(title.trim());
        }
        String subtitle = articleSubtitle(article);
        if (!subtitle.trim().isEmpty()) {
            if (text.length() > 0) {
                text.append("\n");
            }
            text.append(subtitle);
        }
        String summary = stripHtml(articleContent(article));
        if (!summary.trim().isEmpty()) {
            if (text.length() > 0) {
                text.append("\n\n");
            }
            text.append(summary);
        }
        if (article.link != null && !article.link.trim().isEmpty()) {
            if (text.length() > 0) {
                text.append("\n\n");
            }
            text.append(article.link.trim());
        }
        if (text.length() == 0) {
            text.append("MRSS 文章");
        }
        Intent sendIntent = new Intent(Intent.ACTION_SEND);
        sendIntent.setType("text/plain");
        sendIntent.putExtra(Intent.EXTRA_SUBJECT, title.isEmpty() ? "MRSS 文章" : title);
        sendIntent.putExtra(Intent.EXTRA_TEXT, text.toString());
        startActivity(Intent.createChooser(sendIntent, "分享文章"));
    }

    private boolean hasTranslation(Article article) {
        if (article == null) {
            return false;
        }
        if ("done".equals(article.translationStatus)) {
            return true;
        }
        return (article.originalContent != null && !article.originalContent.trim().isEmpty())
                || (article.originalTitle != null && !article.originalTitle.trim().isEmpty());
    }

    private String articleTitle(Article article) {
        if (article == null) {
            return "";
        }
        if (article.showOriginal && article.originalTitle != null && !article.originalTitle.trim().isEmpty()) {
            return article.originalTitle;
        }
        return article.title == null ? "" : article.title;
    }

    private String articleContent(Article article) {
        if (article == null) {
            return "";
        }
        if (article.showOriginal && article.originalContent != null && !article.originalContent.trim().isEmpty()) {
            return article.originalContent;
        }
        return article.content == null ? "" : article.content;
    }

    private void markAllRead() {
        executor.execute(() -> {
            int count;
            if (selectedKeywordId != null) {
                int total = repository.countArticles(null, null, selectedKeywordId, true, false, "", 0, 0);
                List<Article> matched = repository.getArticles(null, null, selectedKeywordId, true, false, "", 0, 0, "published_at", true, Math.max(total, 1), 0);
                count = 0;
                for (Article article : matched) {
                    repository.markRead(article.id);
                    count++;
                }
            } else {
                count = repository.markAllRead(selectedFeedId, selectedFeedId == null ? selectedCategoryId : null);
            }
            int markedCount = count;
            runOnUiThread(() -> {
                Toast.makeText(this, "已标记 " + markedCount + " 篇文章", Toast.LENGTH_SHORT).show();
                loadFiltersAndArticles();
            });
        });
    }

    private void pickOpmlFile() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, REQUEST_IMPORT_OPML);
    }

    private void createOpmlFile() {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/xml");
        intent.putExtra(Intent.EXTRA_TITLE, "mrss-subscriptions.opml");
        startActivityForResult(intent, REQUEST_EXPORT_OPML);
    }

    private void pickBackupFile() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        startActivityForResult(intent, REQUEST_IMPORT_BACKUP);
    }

    private void createBackupFile() {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("application/json");
        intent.putExtra(Intent.EXTRA_TITLE, "mrss-backup.json");
        startActivityForResult(intent, REQUEST_EXPORT_BACKUP);
    }

    private void importOpml(Uri uri) {
        ProgressDialog progress = ProgressDialog.show(this, "导入 OPML", "正在读取订阅列表...", true, false);
        executor.execute(() -> {
            try {
                String content = readText(uri);
                List<OpmlFeed> opmlFeeds = OpmlUtils.parse(content);
                int imported = repository.importOpmlFeeds(opmlFeeds, settings.getDefaultFetchIntervalSeconds());
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "已导入 " + imported + " 个订阅", Toast.LENGTH_LONG).show();
                    if (settings.isBackgroundSyncEnabled()) {
                        SyncScheduler.schedule(this);
                    }
                    loadFiltersAndArticles();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "导入失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void exportOpml(Uri uri) {
        ProgressDialog progress = ProgressDialog.show(this, "导出 OPML", "正在写入文件...", true, false);
        executor.execute(() -> {
            try {
                String content = OpmlUtils.generate(repository.getFeedsForExport());
                try (OutputStream output = getContentResolver().openOutputStream(uri)) {
                    if (output == null) {
                        throw new IllegalStateException("无法打开输出文件");
                    }
                    output.write(content.getBytes(StandardCharsets.UTF_8));
                }
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "OPML 已导出", Toast.LENGTH_SHORT).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "导出失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void exportBackup(Uri uri) {
        ProgressDialog progress = ProgressDialog.show(this, "导出备份", "正在写入完整备份...", true, false);
        executor.execute(() -> {
            try {
                String content = repository.exportBackupJson();
                try (OutputStream output = getContentResolver().openOutputStream(uri)) {
                    if (output == null) {
                        throw new IllegalStateException("无法打开输出文件");
                    }
                    output.write(content.getBytes(StandardCharsets.UTF_8));
                }
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "备份已导出", Toast.LENGTH_SHORT).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "导出失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void restoreBackup(Uri uri) {
        new AlertDialog.Builder(this)
                .setTitle("恢复备份")
                .setMessage("恢复会覆盖当前本地分类、订阅和文章。")
                .setNegativeButton("取消", null)
                .setPositiveButton("恢复", (dialog, which) -> {
                    ProgressDialog progress = ProgressDialog.show(this, "恢复备份", "正在恢复本地数据...", true, false);
                    executor.execute(() -> {
                        try {
                            repository.restoreBackupJson(readText(uri));
                            runOnUiThread(() -> {
                                progress.dismiss();
                                Toast.makeText(this, "备份已恢复", Toast.LENGTH_SHORT).show();
                                if (settings.isBackgroundSyncEnabled()) {
                                    SyncScheduler.schedule(this);
                                }
                                loadFiltersAndArticles();
                            });
                        } catch (Exception e) {
                            runOnUiThread(() -> {
                                progress.dismiss();
                                Toast.makeText(this, "恢复失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                            });
                        }
                    });
                })
                .show();
    }

    private void showStatsDialog() {
        executor.execute(() -> {
            Stats stats = repository.getStats();
            runOnUiThread(() -> {
                String latest = stats.latestArticleAt > 0
                        ? DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(new Date(stats.latestArticleAt))
                        : "暂无";
                String message = "分类：" + stats.categoryCount +
                        "\n订阅：" + stats.feedCount + "（启用 " + stats.activeFeedCount + "）" +
                        "\n文章：" + stats.articleCount +
                        "\n未读：" + stats.unreadCount +
                        "\n收藏：" + stats.favoriteCount +
                        "\n今天新增：" + stats.todayCount +
                        "\n最近 7 天：" + stats.lastSevenDaysCount +
                        "\n最新文章：" + latest;
                new AlertDialog.Builder(this)
                        .setTitle("本地统计")
                        .setMessage(message)
                        .setPositiveButton("确定", null)
                        .show();
            });
        });
    }

    private void showCategoryManagement() {
        executor.execute(() -> {
            List<Category> current = repository.getCategories();
            runOnUiThread(() -> {
                List<String> labels = new ArrayList<>();
                labels.add("新增分类");
                for (Category category : current) {
                    labels.add(category.name + " · " + category.feedCount + " 个订阅");
                }
                new AlertDialog.Builder(this)
                        .setTitle("分类管理")
                        .setItems(labels.toArray(new String[0]), (dialog, which) -> {
                            if (which == 0) {
                                showCategoryEditDialog(null);
                            } else {
                                showCategoryEditDialog(current.get(which - 1));
                            }
                        })
                        .show();
            });
        });
    }

    private AdapterView.OnItemSelectedListener simpleSelectionListener() {
        return new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                loadArticles();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        };
    }

    private void showCategoryEditDialog(Category category) {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("分类名称");
        if (category != null) {
            input.setText(category.name);
        }
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(category == null ? "新增分类" : "编辑分类")
                .setView(input)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存", null)
                .setNeutralButton(category == null ? null : "删除", null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String name = input.getText().toString().trim();
                if (name.isEmpty()) {
                    Toast.makeText(this, "分类名称不能为空", Toast.LENGTH_SHORT).show();
                    return;
                }
                executor.execute(() -> {
                    if (category == null) {
                        repository.createCategory(name);
                    } else {
                        repository.renameCategory(category.id, name);
                    }
                    runOnUiThread(() -> {
                        dialog.dismiss();
                        loadFiltersAndArticles();
                    });
                });
            });
            Button deleteButton = dialog.getButton(AlertDialog.BUTTON_NEUTRAL);
            if (deleteButton != null && category != null) {
                deleteButton.setOnClickListener(v -> confirmDeleteCategory(category, dialog));
            }
        });
        dialog.show();
    }

    private void confirmDeleteCategory(Category category, AlertDialog parentDialog) {
        new AlertDialog.Builder(this)
                .setTitle("删除分类")
                .setMessage("分类内订阅不会删除，只会变为未分类。")
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (confirm, which) -> executor.execute(() -> {
                    repository.deleteCategory(category.id);
                    runOnUiThread(() -> {
                        if (parentDialog != null) {
                            parentDialog.dismiss();
                        }
                        if (selectedCategoryId != null && selectedCategoryId == category.id) {
                            selectedCategoryId = null;
                            selectedFeedId = null;
                        }
                        Toast.makeText(this, "分类已删除", Toast.LENGTH_SHORT).show();
                        loadFiltersAndArticles();
                    });
                }))
                .show();
    }

    private void showFeedManagement() {
        executor.execute(() -> {
            List<Feed> current = repository.getFeeds();
            runOnUiThread(() -> {
                if (current.isEmpty()) {
                    Toast.makeText(this, "还没有订阅", Toast.LENGTH_SHORT).show();
                    return;
                }
                List<String> labels = new ArrayList<>();
                for (Feed feed : current) {
                    labels.add(feed.title + "\n" + feed.url);
                }
                new AlertDialog.Builder(this)
                        .setTitle("订阅管理")
                        .setItems(labels.toArray(new String[0]), (dialog, which) -> showFeedEditDialog(current.get(which)))
                        .show();
            });
        });
    }

    private void showKeywordManagement() {
        executor.execute(() -> {
            List<KeywordSubscription> current = repository.getKeywordSubscriptions();
            runOnUiThread(() -> {
                List<String> labels = new ArrayList<>();
                labels.add("新增关键词订阅");
                for (KeywordSubscription keyword : current) {
                    labels.add(keyword.toString() + " · " + keyword.keyword + (keyword.active ? "" : "（停用）"));
                }
                new AlertDialog.Builder(this)
                        .setTitle("关键词管理")
                        .setItems(labels.toArray(new String[0]), (dialog, which) -> {
                            if (which == 0) {
                                showKeywordEditDialog(null);
                            } else {
                                showKeywordDrawerActions(current.get(which - 1));
                            }
                        })
                        .show();
            });
        });
    }

    private void showFeedEditDialog(Feed feed) {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);

        EditText titleInput = new EditText(this);
        titleInput.setSingleLine(true);
        titleInput.setText(feed.title);
        form.addView(labeledView("标题", titleInput));

        TextView urlView = new TextView(this);
        urlView.setText(feed.url);
        urlView.setTextColor(Color.rgb(80, 88, 84));
        form.addView(labeledView("地址", urlView));

        List<Category> categoryOptions = categoryOptions(true);
        Spinner categoryInput = spinnerForCategories(categoryOptions);
        selectCategory(categoryInput, categoryOptions, feed.categoryId);
        form.addView(labeledView("分类", categoryInput));

        int[] intervals = intervalValues();
        Spinner intervalInput = spinnerForIntervals(intervals);
        selectInterval(intervalInput, intervals, feed.fetchIntervalSeconds);
        form.addView(labeledView("同步间隔", intervalInput));

        CheckBox activeInput = new CheckBox(this);
        activeInput.setText("启用自动同步");
        activeInput.setChecked(feed.active);
        form.addView(activeInput);

        CheckBox translateInput = new CheckBox(this);
        translateInput.setText("自动 AI 翻译");
        translateInput.setChecked(feed.translateEnabled);
        form.addView(translateInput);

        EditText languageInput = new EditText(this);
        languageInput.setSingleLine(true);
        languageInput.setText(feed.translationLanguage == null || feed.translationLanguage.trim().isEmpty() ? settings.getDefaultTranslationLanguage() : feed.translationLanguage);
        form.addView(labeledView("翻译为", languageInput));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("编辑订阅")
                .setView(form)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存", null)
                .setNeutralButton("删除", null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String title = titleInput.getText().toString().trim();
                Category category = categoryOptions.get(categoryInput.getSelectedItemPosition());
                Long categoryId = category.id <= 0 ? null : category.id;
                int interval = intervals[intervalInput.getSelectedItemPosition()];
                executor.execute(() -> {
                    repository.updateFeed(feed.id, title, categoryId, interval, activeInput.isChecked(), translateInput.isChecked(), languageInput.getText().toString().trim());
                    if (translateInput.isChecked()) {
                        repository.resetFailedTranslationsForFeed(feed.id);
                    }
                    runOnUiThread(() -> {
                        dialog.dismiss();
                        Toast.makeText(this, "订阅已保存", Toast.LENGTH_SHORT).show();
                        if (settings.isBackgroundSyncEnabled()) {
                            SyncScheduler.schedule(this);
                        }
                        loadFiltersAndArticles();
                        if (translateInput.isChecked()) {
                            scheduleAutoTranslation();
                        }
                    });
                });
            });
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v -> confirmDeleteFeed(feed, dialog));
        });
        dialog.show();
    }

    private void confirmDeleteFeed(Feed feed, AlertDialog parentDialog) {
        new AlertDialog.Builder(this)
                .setTitle("删除订阅")
                .setMessage("会同时删除该订阅下的本地文章。")
                .setNegativeButton("取消", null)
                .setPositiveButton("删除", (confirm, which) -> executor.execute(() -> {
                    repository.deleteFeed(feed.id);
                    runOnUiThread(() -> {
                        if (parentDialog != null) {
                            parentDialog.dismiss();
                        }
                        if (selectedFeedId != null && selectedFeedId == feed.id) {
                            selectedFeedId = null;
                        }
                        Toast.makeText(this, "订阅已删除", Toast.LENGTH_SHORT).show();
                        if (settings.isBackgroundSyncEnabled()) {
                            SyncScheduler.schedule(this);
                        }
                        loadFiltersAndArticles();
                    });
                }))
                .show();
    }

    private void showDataSyncDialog() {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);

        EditText tokenInput = new EditText(this);
        tokenInput.setSingleLine(true);
        tokenInput.setHint("GitHub Token（需要 gist 权限）");
        tokenInput.setText(settings.getGithubToken());
        form.addView(labeledView("GitHub Token", tokenInput));

        EditText gistInput = new EditText(this);
        gistInput.setSingleLine(true);
        gistInput.setHint("首次上传可留空，上传后会自动保存");
        gistInput.setText(settings.getGistId());
        form.addView(labeledView("Gist ID", gistInput));

        EditText filenameInput = new EditText(this);
        filenameInput.setSingleLine(true);
        filenameInput.setText(settings.getGistFilename());
        form.addView(labeledView("文件名", filenameInput));

        TextView hint = new TextView(this);
        hint.setText("数据同步只上传分类和订阅源，不上传已保存文章。适合电脑端和手机端共享订阅配置。");
        hint.setTextColor(Color.rgb(80, 88, 84));
        hint.setTextSize(13);
        form.addView(hint);

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("数据同步")
                .setView(form)
                .setNegativeButton("关闭", null)
                .setNeutralButton("下载合并", null)
                .setPositiveButton("上传", null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String token = tokenInput.getText().toString().trim();
                String gistId = gistInput.getText().toString().trim();
                String filename = filenameInput.getText().toString().trim();
                if (validateGistForm(token, filename)) {
                    uploadSubscriptionSync(token, gistId, filename, dialog);
                }
            });
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v -> {
                String token = tokenInput.getText().toString().trim();
                String gistId = gistInput.getText().toString().trim();
                String filename = filenameInput.getText().toString().trim();
                if (validateGistForm(token, filename)) {
                    if (gistId.isEmpty()) {
                        Toast.makeText(this, "下载需要填写 Gist ID", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    downloadSubscriptionSync(token, gistId, filename, dialog);
                }
            });
        });
        dialog.show();
    }

    private boolean validateGistForm(String token, String filename) {
        if (token.isEmpty()) {
            Toast.makeText(this, "请填写 GitHub Token", Toast.LENGTH_SHORT).show();
            return false;
        }
        if (filename.isEmpty()) {
            Toast.makeText(this, "请填写文件名", Toast.LENGTH_SHORT).show();
            return false;
        }
        return true;
    }

    private void uploadSubscriptionSync(String token, String gistId, String filename, AlertDialog dialog) {
        ProgressDialog progress = ProgressDialog.show(this, "数据同步", "正在上传分类和订阅源...", true, false);
        syncExecutor.execute(() -> {
            try {
                String content = repository.exportSubscriptionSyncJson();
                String newGistId = new GistClient().upload(token, gistId, filename, content);
                settings.setGistSettings(token, newGistId, filename);
                runOnUiThread(() -> {
                    progress.dismiss();
                    dialog.dismiss();
                    Toast.makeText(this, "已上传到 GitHub Gist：" + newGistId, Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "上传失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void downloadSubscriptionSync(String token, String gistId, String filename, AlertDialog dialog) {
        ProgressDialog progress = ProgressDialog.show(this, "数据同步", "正在下载并合并订阅...", true, false);
        syncExecutor.execute(() -> {
            try {
                String content = new GistClient().download(token, gistId, filename);
                int changed = repository.importSubscriptionSyncJson(content);
                settings.setGistSettings(token, gistId, filename);
                runOnUiThread(() -> {
                    progress.dismiss();
                    dialog.dismiss();
                    if (settings.isBackgroundSyncEnabled()) {
                        SyncScheduler.schedule(this);
                    }
                    loadFiltersAndArticles();
                    Toast.makeText(this, "已合并同步数据：" + changed + " 项", Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "下载失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void showSettingsDialog() {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);

        int[] intervals = intervalValues();
        Spinner intervalInput = spinnerForIntervals(intervals);
        selectInterval(intervalInput, intervals, settings.getDefaultFetchIntervalSeconds());
        form.addView(labeledView("新订阅默认同步间隔", intervalInput));

        int[] pageSizes = articlePageSizeValues();
        Spinner pageSizeInput = spinnerForPageSizes(pageSizes);
        selectPageSize(pageSizeInput, pageSizes, settings.getArticlePageSize());
        form.addView(labeledView("文章每页数量", pageSizeInput));

        EditText defaultLanguageInput = new EditText(this);
        defaultLanguageInput.setSingleLine(true);
        defaultLanguageInput.setText(settings.getDefaultTranslationLanguage());
        form.addView(labeledView("默认翻译语言", defaultLanguageInput));

        CheckBox backgroundSync = new CheckBox(this);
        backgroundSync.setText("启用后台定时同步");
        backgroundSync.setChecked(settings.isBackgroundSyncEnabled());
        form.addView(backgroundSync);

        TextView exactAlarmHint = new TextView(this);
        exactAlarmHint.setText("如需尽量准点同步，可在系统中允许 MRSS 使用精准闹钟，并关闭电池优化。");
        exactAlarmHint.setTextColor(Color.rgb(80, 88, 84));
        exactAlarmHint.setTextSize(13);
        form.addView(exactAlarmHint);

        new AlertDialog.Builder(this)
                .setTitle("刷新设置")
                .setView(form)
                .setNegativeButton("取消", null)
                .setNeutralButton("系统权限", (dialog, which) -> openSyncSystemSettings())
                .setPositiveButton("保存", (dialog, which) -> {
                    settings.setDefaultFetchIntervalSeconds(intervals[intervalInput.getSelectedItemPosition()]);
                    settings.setArticlePageSize(pageSizes[pageSizeInput.getSelectedItemPosition()]);
                    settings.setDefaultTranslationLanguage(defaultLanguageInput.getText().toString().trim());
                    settings.setBackgroundSyncEnabled(backgroundSync.isChecked());
                    if (backgroundSync.isChecked()) {
                        SyncScheduler.schedule(this);
                    } else {
                        SyncScheduler.cancel(this);
                    }
                    loadArticles();
                    Toast.makeText(this, "设置已保存", Toast.LENGTH_SHORT).show();
                })
                .show();
    }

    private void showAiDefaultModelDialog() {
        executor.execute(() -> {
            List<AiChannel> channels = repository.getAiChannels();
            runOnUiThread(() -> showAiDefaultModelPanel(channels));
        });
    }

    private void showAiDefaultModelPanel(List<AiChannel> channels) {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(18), dp(8), dp(18), 0);

        TextView title = new TextView(this);
        title.setText("当前默认");
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextSize(15);
        title.setTextColor(Color.rgb(15, 23, 42));
        form.addView(title);

        TextView currentSummary = new TextView(this);
        currentSummary.setTextSize(15);
        currentSummary.setTextColor(Color.rgb(15, 23, 42));
        currentSummary.setLineSpacing(dp(2), 1.0f);
        currentSummary.setPadding(dp(12), dp(10), dp(12), dp(10));
        currentSummary.setBackgroundColor(Color.rgb(239, 247, 244));
        form.addView(currentSummary, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView section = new TextView(this);
        section.setText("设置默认模型");
        section.setTypeface(Typeface.DEFAULT_BOLD);
        section.setTextSize(15);
        section.setTextColor(Color.rgb(15, 23, 42));
        section.setPadding(0, dp(16), 0, 0);
        form.addView(section);

        Spinner defaultChannelInput = new Spinner(this);
        List<String> channelLabels = new ArrayList<>();
        if (channels.isEmpty()) {
            channelLabels.add("暂无渠道，请先新增");
        } else {
            for (AiChannel channel : channels) {
                channelLabels.add(aiChannelLabel(channel));
            }
        }
        defaultChannelInput.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, channelLabels));
        int defaultIndex = 0;
        for (int i = 0; i < channels.size(); i++) {
            if (channels.get(i).isDefault) {
                defaultIndex = i;
                break;
            }
        }
        if (!channels.isEmpty()) {
            defaultChannelInput.setSelection(defaultIndex);
        }
        form.addView(labeledView("默认渠道", defaultChannelInput));

        Spinner defaultModelInput = new Spinner(this);
        List<String> modelOptions = new ArrayList<>();
        modelOptions.add("请先在渠道管理中拉取模型");
        defaultModelInput.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, modelOptions));
        defaultModelInput.setEnabled(false);
        form.addView(labeledView("默认模型", defaultModelInput));

        EditText customModelInput = new EditText(this);
        customModelInput.setSingleLine(true);
        customModelInput.setHint("可手动填写模型名或豆包接入点 ID");
        form.addView(labeledView("自定义模型", customModelInput));

        Button saveDefaultButton = new Button(this);
        saveDefaultButton.setText("保存默认");
        saveDefaultButton.setAllCaps(false);
        saveDefaultButton.setEnabled(!channels.isEmpty());
        form.addView(saveDefaultButton);

        Runnable refreshDefaultModelText = () -> {
            if (channels.isEmpty()) {
                currentSummary.setText("默认渠道：未设置\n默认模型：未设置\n默认翻译语言：" + settings.getDefaultTranslationLanguage());
                modelOptions.clear();
                modelOptions.add("请先新增渠道");
                ((ArrayAdapter<?>) defaultModelInput.getAdapter()).notifyDataSetChanged();
                return;
            }
            AiChannel active = defaultAiChannel(channels);
            AiChannel selected = channels.get(defaultChannelInput.getSelectedItemPosition());
            currentSummary.setText("默认渠道：" + active.name + "（" + aiProviderLabel(active.provider) + "）\n默认模型：" + (TextUtils.isEmpty(active.model) ? "未选择" : active.model) + "\n默认翻译语言：" + settings.getDefaultTranslationLanguage());
            customModelInput.setText(selected.model == null ? "" : selected.model);
            modelOptions.clear();
            if (selected.models == null || selected.models.isEmpty()) {
                modelOptions.add("该渠道未拉取模型，请到渠道管理拉取");
                defaultModelInput.setEnabled(false);
                saveDefaultButton.setEnabled(true);
            } else {
                modelOptions.addAll(selected.models);
                defaultModelInput.setEnabled(true);
                saveDefaultButton.setEnabled(true);
            }
            ((ArrayAdapter<?>) defaultModelInput.getAdapter()).notifyDataSetChanged();
            defaultModelInput.setSelection(modelIndex(modelOptions, selected.model));
        };
        refreshDefaultModelText.run();

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("AI 默认模型")
                .setView(form)
                .setNeutralButton("渠道管理", null)
                .setNegativeButton("关闭", null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v -> {
                dialog.dismiss();
                showAiChannelManagementDialog();
            });
            defaultChannelInput.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
                @Override
                public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                    refreshDefaultModelText.run();
                }

                @Override
                public void onNothingSelected(AdapterView<?> parent) {
                }
            });
            saveDefaultButton.setOnClickListener(v -> {
                if (channels.isEmpty()) {
                    Toast.makeText(this, "请先新增 AI 渠道", Toast.LENGTH_SHORT).show();
                    return;
                }
                AiChannel selected = channels.get(defaultChannelInput.getSelectedItemPosition());
                String customModel = customModelInput.getText().toString().trim();
                if (!customModel.isEmpty()) {
                    selected.model = customModel;
                    if (selected.models == null) {
                        selected.models = new ArrayList<>();
                    }
                    if (!selected.models.contains(customModel)) {
                        selected.models.add(0, customModel);
                    }
                } else if (defaultModelInput.isEnabled() && !modelOptions.isEmpty() && !modelOptions.get(0).contains("未拉取")) {
                    selected.model = modelOptions.get(defaultModelInput.getSelectedItemPosition());
                } else {
                    Toast.makeText(this, "请填写或选择默认模型", Toast.LENGTH_SHORT).show();
                    return;
                }
                saveDefaultAiModel(channels, selected, refreshDefaultModelText);
            });
        });
        dialog.show();
    }

    private void saveDefaultAiModel(List<AiChannel> channels, AiChannel selected, Runnable onSaved) {
        if (selected == null || TextUtils.isEmpty(selected.model)) {
            Toast.makeText(this, "请先选择模型", Toast.LENGTH_SHORT).show();
            return;
        }
        for (AiChannel channel : channels) {
            channel.isDefault = channel == selected;
        }
        executor.execute(() -> {
            repository.saveAiChannels(channels);
            runOnUiThread(() -> {
                Toast.makeText(this, "默认模型已保存", Toast.LENGTH_SHORT).show();
                if (onSaved != null) {
                    onSaved.run();
                }
            });
        });
    }

    private void showAiChannelManagementDialog() {
        executor.execute(() -> {
            List<AiChannel> channels = repository.getAiChannels();
            runOnUiThread(() -> showAiChannelManagementPanel(channels));
        });
    }

    private void showAiChannelManagementPanel(List<AiChannel> channels) {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(18), dp(8), dp(18), 0);

        TextView hint = new TextView(this);
        hint.setText("OpenAI、Gemini、千问、豆包、DeepSeek、Kimi、智谱已内置地址，只需要填写 API Key。第三方中转站请选择 OpenAI 兼容并填写 Base URL。");
        hint.setTextColor(Color.rgb(80, 88, 84));
        hint.setTextSize(13);
        hint.setPadding(0, 0, 0, dp(8));
        form.addView(hint);

        ListView channelList = new ListView(this);
        channelList.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, manageLabelsForChannels(channels)));
        channelList.setDividerHeight(1);
        form.addView(channelList, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(320)));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("AI 渠道管理")
                .setView(form)
                .setNeutralButton("默认模型", null)
                .setNegativeButton("关闭", null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v -> {
                dialog.dismiss();
                showAiDefaultModelDialog();
            });
            channelList.setOnItemClickListener((parent, view, position, id) -> {
                dialog.dismiss();
                if (position == 0) {
                    showAiChannelEditDialog(channels, null);
                } else {
                    showAiChannelEditDialog(channels, channels.get(position - 1));
                }
            });
        });
        dialog.show();
    }

    private List<String> manageLabelsForChannels(List<AiChannel> channels) {
        List<String> labels = new ArrayList<>();
        labels.add("新增渠道");
        for (AiChannel channel : channels) {
            labels.add(aiChannelLabel(channel));
        }
        return labels;
    }

    private String aiChannelLabel(AiChannel channel) {
        if (channel == null) {
            return "AI 渠道";
        }
        String name = TextUtils.isEmpty(channel.name) ? "AI 渠道" : channel.name;
        String model = TextUtils.isEmpty(channel.model) ? "未选择模型" : channel.model;
        return name + " · " + aiProviderLabel(channel.provider) + " · " + model + (channel.isDefault ? " · 默认" : "");
    }

    private String aiProviderLabel(String provider) {
        if ("gemini".equals(provider)) {
            return "Gemini 官方";
        }
        if ("qwen".equals(provider)) {
            return "通义千问";
        }
        if ("doubao".equals(provider)) {
            return "豆包";
        }
        if ("deepseek".equals(provider)) {
            return "DeepSeek";
        }
        if ("kimi".equals(provider)) {
            return "Kimi";
        }
        if ("zhipu".equals(provider)) {
            return "智谱";
        }
        if ("openai_compatible".equals(provider)) {
            return "OpenAI 兼容";
        }
        return "OpenAI 官方";
    }

    private AiChannel defaultAiChannel(List<AiChannel> channels) {
        for (AiChannel channel : channels) {
            if (channel.isDefault) {
                return channel;
            }
        }
        return channels.get(0);
    }

    private int modelIndex(List<String> models, String selectedModel) {
        if (models == null || models.isEmpty()) {
            return 0;
        }
        for (int i = 0; i < models.size(); i++) {
            if (models.get(i).equals(selectedModel)) {
                return i;
            }
        }
        return 0;
    }

    private void showAiChannelEditDialog(List<AiChannel> existingChannels, AiChannel channel) {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);

        EditText nameInput = new EditText(this);
        nameInput.setSingleLine(true);
        nameInput.setText(channel == null ? "OpenAI 官方" : channel.name);
        form.addView(labeledView("渠道名称", nameInput));

        Spinner providerInput = new Spinner(this);
        List<String> providers = new ArrayList<>();
        providers.add("OpenAI 官方");
        providers.add("Gemini 官方");
        providers.add("通义千问");
        providers.add("豆包");
        providers.add("DeepSeek");
        providers.add("Kimi");
        providers.add("智谱");
        providers.add("OpenAI 兼容");
        providerInput.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, providers));
        providerInput.setSelection(providerIndex(channel == null ? "openai" : channel.provider));
        form.addView(labeledView("类型", providerInput));

        EditText baseUrlInput = new EditText(this);
        baseUrlInput.setSingleLine(true);
        baseUrlInput.setText(channel == null ? "" : channel.baseUrl);
        LinearLayout baseUrlRow = labeledView("Base URL", baseUrlInput);
        form.addView(baseUrlRow);

        EditText keyInput = new EditText(this);
        keyInput.setSingleLine(true);
        keyInput.setText(channel == null ? "" : channel.apiKey);
        form.addView(labeledView("API Key", keyInput));

        TextView hintView = new TextView(this);
        hintView.setTextColor(Color.rgb(100, 116, 139));
        hintView.setTextSize(12);
        hintView.setPadding(0, dp(6), 0, 0);
        form.addView(hintView);

        TextView modelsView = new TextView(this);
        modelsView.setTextColor(Color.rgb(15, 23, 42));
        modelsView.setTextSize(13);
        modelsView.setPadding(0, dp(8), 0, dp(8));
        form.addView(modelsView);

        Button fetchModelsButton = new Button(this);
        fetchModelsButton.setText("拉取并保存模型");
        fetchModelsButton.setAllCaps(false);
        form.addView(fetchModelsButton);

        AlertDialog.Builder builder = new AlertDialog.Builder(this)
                .setTitle(channel == null ? "新增 AI 渠道" : "编辑 AI 渠道")
                .setView(form)
                .setNegativeButton("取消", null)
                .setPositiveButton("保存", null);
        if (channel != null) {
            builder.setNeutralButton("删除", null);
        }
        AlertDialog dialog = builder.create();
        dialog.setOnShowListener(d -> {
            Runnable updateProviderUi = () -> {
                String provider = providerValue(providerInput.getSelectedItemPosition());
                boolean custom = "openai_compatible".equals(provider);
                baseUrlRow.setVisibility(custom ? View.VISIBLE : View.GONE);
                if (!custom) {
                    baseUrlInput.setText("");
                }
                if ("gemini".equals(provider)) {
                    hintView.setText("Gemini 官方渠道使用 Google 官方地址，只需要填写 Gemini API Key，然后拉取模型。");
                } else if ("qwen".equals(provider)) {
                    hintView.setText("通义千问使用阿里云 DashScope OpenAI 兼容地址，只需要填写 DashScope API Key。");
                } else if ("doubao".equals(provider)) {
                    hintView.setText("豆包使用火山方舟 OpenAI 兼容地址。模型通常是方舟控制台创建的接入点 ID。");
                } else if ("deepseek".equals(provider)) {
                    hintView.setText("DeepSeek 官方渠道已内置 API 地址，只需要填写 DeepSeek API Key。");
                } else if ("kimi".equals(provider)) {
                    hintView.setText("Kimi 使用 Moonshot 官方 OpenAI 兼容地址，只需要填写 Moonshot API Key。");
                } else if ("zhipu".equals(provider)) {
                    hintView.setText("智谱使用 BigModel 官方 OpenAI 兼容地址，只需要填写智谱 API Key。");
                } else if (custom) {
                    hintView.setText("OpenAI 兼容渠道用于第三方中转站，填写完整 Base URL，例如 https://example.com/v1。");
                } else {
                    hintView.setText("OpenAI 官方渠道内置 https://api.openai.com/v1，只需要填写 OpenAI API Key，然后拉取模型。");
                }
            };
            Runnable updateModelsText = () -> {
                List<String> cachedModels = channel == null ? new ArrayList<>() : channel.models;
                if (cachedModels == null || cachedModels.isEmpty()) {
                    modelsView.setText("已缓存模型：0 个");
                } else {
                    modelsView.setText("已缓存模型：" + cachedModels.size() + " 个\n当前默认：" + (TextUtils.isEmpty(channel.model) ? "未选择" : channel.model));
                }
            };
            providerInput.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
                @Override
                public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                    updateProviderUi.run();
                }

                @Override
                public void onNothingSelected(AdapterView<?> parent) {
                }
            });
            updateProviderUi.run();
            updateModelsText.run();
            fetchModelsButton.setOnClickListener(v -> {
                String name = nameInput.getText().toString().trim();
                if (name.isEmpty()) {
                    Toast.makeText(this, "渠道名称不能为空", Toast.LENGTH_SHORT).show();
                    return;
                }
                AiChannel target = channel == null ? new AiChannel() : channel;
                target.name = name;
                target.provider = providerValue(providerInput.getSelectedItemPosition());
                target.baseUrl = "openai_compatible".equals(target.provider) ? baseUrlInput.getText().toString().trim() : "";
                target.apiKey = keyInput.getText().toString();
                if (TextUtils.isEmpty(target.apiKey)) {
                    Toast.makeText(this, "请先填写 API Key", Toast.LENGTH_SHORT).show();
                    return;
                }
                if ("openai_compatible".equals(target.provider) && TextUtils.isEmpty(target.baseUrl)) {
                    Toast.makeText(this, "OpenAI 兼容渠道需要填写 Base URL", Toast.LENGTH_SHORT).show();
                    return;
                }
                fetchAndCacheModels(existingChannels, target, channel == null, dialog);
            });
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String name = nameInput.getText().toString().trim();
                if (name.isEmpty()) {
                    Toast.makeText(this, "渠道名称不能为空", Toast.LENGTH_SHORT).show();
                    return;
                }
                AiChannel target = channel == null ? new AiChannel() : channel;
                target.name = name;
                target.provider = providerValue(providerInput.getSelectedItemPosition());
                target.baseUrl = "openai_compatible".equals(target.provider) ? baseUrlInput.getText().toString().trim() : "";
                target.apiKey = keyInput.getText().toString();
                if (channel == null) {
                    target.model = "";
                    target.models = new ArrayList<>();
                    target.isDefault = existingChannels.isEmpty();
                }
                List<AiChannel> next = new ArrayList<>(existingChannels);
                if (channel == null) {
                    next.add(target);
                }
                executor.execute(() -> {
                    repository.saveAiChannels(next);
                    runOnUiThread(() -> {
                        dialog.dismiss();
                        Toast.makeText(this, "AI 设置已保存", Toast.LENGTH_SHORT).show();
                        showAiChannelManagementDialog();
                    });
                });
            });
            if (channel != null) {
                dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v -> {
                    existingChannels.remove(channel);
                    executor.execute(() -> {
                        repository.saveAiChannels(existingChannels);
                        runOnUiThread(() -> {
                            dialog.dismiss();
                            Toast.makeText(this, "渠道已删除", Toast.LENGTH_SHORT).show();
                            showAiChannelManagementDialog();
                        });
                    });
                });
            }
        });
        dialog.show();
    }

    private void fetchAndCacheModels(List<AiChannel> existingChannels, AiChannel target, boolean isNewChannel, AlertDialog dialog) {
        ProgressDialog progress = new ProgressDialog(this);
        progress.setMessage("正在拉取模型...");
        progress.setCancelable(false);
        progress.show();
        executor.execute(() -> {
            try {
                List<String> models = new AiClient().fetchModels(target);
                if (models.isEmpty()) {
                    throw new IllegalStateException("没有拉取到模型");
                }
                target.models = new ArrayList<>(models);
                if (TextUtils.isEmpty(target.model) || !target.models.contains(target.model)) {
                    target.model = target.models.get(0);
                }
                if (isNewChannel) {
                    target.isDefault = existingChannels.isEmpty();
                }
                List<AiChannel> next = new ArrayList<>(existingChannels);
                if (isNewChannel && !next.contains(target)) {
                    next.add(target);
                }
                repository.saveAiChannels(next);
                runOnUiThread(() -> {
                    progress.dismiss();
                    if (dialog != null) {
                        dialog.dismiss();
                    }
                    Toast.makeText(this, "已拉取并保存 " + models.size() + " 个模型", Toast.LENGTH_SHORT).show();
                    showAiChannelManagementDialog();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, "拉取失败：" + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private int providerIndex(String provider) {
        if ("gemini".equals(provider)) {
            return 1;
        }
        if ("qwen".equals(provider)) {
            return 2;
        }
        if ("doubao".equals(provider)) {
            return 3;
        }
        if ("deepseek".equals(provider)) {
            return 4;
        }
        if ("kimi".equals(provider)) {
            return 5;
        }
        if ("zhipu".equals(provider)) {
            return 6;
        }
        if ("openai_compatible".equals(provider)) {
            return 7;
        }
        return 0;
    }

    private String providerValue(int index) {
        if (index == 1) {
            return "gemini";
        }
        if (index == 2) {
            return "qwen";
        }
        if (index == 3) {
            return "doubao";
        }
        if (index == 4) {
            return "deepseek";
        }
        if (index == 5) {
            return "kimi";
        }
        if (index == 6) {
            return "zhipu";
        }
        if (index == 7) {
            return "openai_compatible";
        }
        return "openai";
    }

    private void openSyncSystemSettings() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                Intent intent = new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM);
                intent.setData(Uri.parse("package:" + getPackageName()));
                startActivity(intent);
                return;
            } catch (Exception ignored) {
            }
        }
        try {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            intent.setData(Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        } catch (Exception e) {
            Toast.makeText(this, "无法打开系统设置", Toast.LENGTH_SHORT).show();
        }
    }

    private List<Category> categoryOptions(boolean includeUncategorized) {
        List<Category> options = new ArrayList<>();
        if (includeUncategorized) {
            Category none = new Category();
            none.id = 0;
            none.name = "未分类";
            options.add(none);
        }
        for (Category category : categories) {
            if (category.id > 0) {
                options.add(category);
            }
        }
        return options;
    }

    private Spinner spinnerForCategories(List<Category> options) {
        Spinner spinner = new Spinner(this);
        ArrayAdapter<Category> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, options);
        spinner.setAdapter(adapter);
        return spinner;
    }

    private Spinner spinnerForIntervals(int[] intervals) {
        Spinner spinner = new Spinner(this);
        List<String> labels = new ArrayList<>();
        for (int interval : intervals) {
            labels.add(intervalLabel(interval));
        }
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, labels));
        return spinner;
    }

    private Spinner spinnerForPageSizes(int[] pageSizes) {
        Spinner spinner = new Spinner(this);
        List<String> labels = new ArrayList<>();
        for (int pageSize : pageSizes) {
            labels.add(pageSize + " 篇 / 页");
        }
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, labels));
        return spinner;
    }

    private LinearLayout labeledView(String label, View child) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(0, dp(6), 0, dp(6));
        TextView labelView = new TextView(this);
        labelView.setText(label);
        labelView.setTextColor(Color.rgb(80, 88, 84));
        labelView.setTextSize(13);
        box.addView(labelView);
        box.addView(child);
        return box;
    }

    private int[] intervalValues() {
        return new int[]{300, 900, 1800, 3600, 7200, 14400, 43200, 86400};
    }

    private int[] articlePageSizeValues() {
        return new int[]{30, 50, 100, 200};
    }

    private void selectInterval(Spinner spinner, int[] intervals, int value) {
        int selected = 0;
        for (int i = 0; i < intervals.length; i++) {
            if (intervals[i] == value) {
                selected = i;
                break;
            }
        }
        spinner.setSelection(selected);
    }

    private void selectPageSize(Spinner spinner, int[] pageSizes, int value) {
        int selected = 1;
        for (int i = 0; i < pageSizes.length; i++) {
            if (pageSizes[i] == value) {
                selected = i;
                break;
            }
        }
        spinner.setSelection(selected);
    }

    private void selectCategory(Spinner spinner, List<Category> options, Long categoryId) {
        int selected = 0;
        for (int i = 0; i < options.size(); i++) {
            Category category = options.get(i);
            if (categoryId != null && category.id == categoryId) {
                selected = i;
                break;
            }
        }
        spinner.setSelection(selected);
    }

    private String intervalLabel(int seconds) {
        if (seconds < 3600) {
            return (seconds / 60) + " 分钟";
        }
        if (seconds < 86400) {
            return (seconds / 3600) + " 小时";
        }
        return "24 小时";
    }

    private String selectedSortBy() {
        int position = sortSpinner == null ? 0 : sortSpinner.getSelectedItemPosition();
        if (position == 1) {
            return "created_at";
        }
        if (position == 2) {
            return "title";
        }
        return "published_at";
    }

    private long[] selectedDateRange() {
        int position = dateSpinner == null ? 0 : dateSpinner.getSelectedItemPosition();
        if (position == 0) {
            return new long[]{0, 0};
        }
        Calendar calendar = Calendar.getInstance();
        calendar.set(Calendar.HOUR_OF_DAY, 0);
        calendar.set(Calendar.MINUTE, 0);
        calendar.set(Calendar.SECOND, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        long todayStart = calendar.getTimeInMillis();
        if (position == 1) {
            return new long[]{todayStart, todayStart + 86400000L - 1};
        }
        if (position == 2) {
            return new long[]{todayStart - 86400000L, todayStart - 1};
        }
        return new long[]{todayStart - 6L * 86400000L, 0};
    }

    private String readText(Uri uri) throws Exception {
        try (InputStream input = getContentResolver().openInputStream(uri)) {
            if (input == null) {
                throw new IllegalStateException("无法打开文件");
            }
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) {
                output.write(buffer, 0, read);
            }
            return output.toString("UTF-8");
        }
    }

    private String categoryLabel(Category category) {
        if (category == null) {
            return "";
        }
        if (category.unreadCount > 0) {
            return category.name + " (" + category.unreadCount + ")";
        }
        return category.name;
    }

    private String feedLabel(Feed feed) {
        if (feed == null) {
            return "";
        }
        if (feed.unreadCount > 0) {
            return feed.title + " (" + feed.unreadCount + ")";
        }
        return feed.title;
    }

    private String articleSubtitle(Article article) {
        if (article == null) {
            return "";
        }
        StringBuilder builder = new StringBuilder();
        if (article.feedTitle != null) {
            builder.append(article.feedTitle);
        }
        long date = article.publishedAt > 0 ? article.publishedAt : article.createdAt;
        if (date > 0) {
            if (builder.length() > 0) {
                builder.append(" · ");
            }
            builder.append(DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(new Date(date)));
        }
        if (article.author != null && !article.author.trim().isEmpty()) {
            builder.append(" · ").append(article.author);
        }
        return builder.toString();
    }

    private String statusLabel() {
        int total = articles.size();
        int unread = 0;
        for (Article article : articles) {
            if (!article.read) {
                unread++;
            }
        }
        String prefix = "";
        if (selectedKeywordId != null) {
            KeywordSubscription keyword = selectedKeyword();
            prefix = keyword == null ? "关键词订阅 · " : "关键词订阅「" + keyword.toString() + "」 · ";
        }
        if (currentTotal == 0) {
            return prefix + "暂无文章。添加或导入订阅后，MRSS 会在手机本地抓取和保存。";
        }
        int start = currentPage * currentPageSize() + 1;
        int end = Math.min(currentTotal, start + Math.max(total, 1) - 1);
        return prefix + "第 " + (currentPage + 1) + " / " + totalPages() + " 页，" + start + "-" + end + " / " + currentTotal + " 篇，当前页未读 " + unread + " 篇";
    }

    private KeywordSubscription selectedKeyword() {
        if (selectedKeywordId == null) {
            return null;
        }
        for (KeywordSubscription keyword : keywordSubscriptions) {
            if (keyword.id == selectedKeywordId) {
                return keyword;
            }
        }
        return repository.getKeywordSubscription(selectedKeywordId);
    }

    private String stripHtml(String html) {
        if (html == null || html.trim().isEmpty()) {
            return "";
        }
        String text;
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
            text = Html.fromHtml(html, Html.FROM_HTML_MODE_LEGACY).toString();
        } else {
            text = Html.fromHtml(html).toString();
        }
        text = text.replaceAll("\\s+", " ").trim();
        return text.length() > 180 ? text.substring(0, 180) + "..." : text;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private int statusBarHeight() {
        int resourceId = getResources().getIdentifier("status_bar_height", "dimen", "android");
        if (resourceId > 0) {
            return getResources().getDimensionPixelSize(resourceId);
        }
        return 0;
    }
}
