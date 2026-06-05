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
import com.mrss.app.model.StandardTranslationSettings;
import com.mrss.app.model.TranslationJob;
import com.mrss.app.network.AiClient;
import com.mrss.app.network.FeedParser;
import com.mrss.app.network.GistClient;
import com.mrss.app.network.StandardTranslationClient;
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
import java.util.Locale;
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

    private interface Translator {
        ArticleTranslation translate(TranslationJob job) throws Exception;
    }
    private FeedRepository repository;
    private AppSettings settings;
    private final List<Category> categories = new ArrayList<>();
    private final List<Feed> feeds = new ArrayList<>();
    private final List<KeywordSubscription> keywordSubscriptions = new ArrayList<>();
    private final List<Article> articles = new ArrayList<>();
    private ArrayAdapter<Category> categoryAdapter;
    private ArrayAdapter<Feed> feedAdapter;
    private ArrayAdapter<Article> articleAdapter;
    private ListView articleListView;
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
    private String appLanguage = "zh";
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
        appLanguage = settings.getAppLanguage();
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

        TextView menuButton = headerButton("☰ " + ui("nav_categories"));
        menuButton.setContentDescription(ui("open_category_menu"));
        menuButton.setOnClickListener(v -> showCategoryDrawer());
        header.addView(menuButton);

        TextView title = new TextView(this);
        title.setText("MRSS");
        title.setTextColor(Color.WHITE);
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        TextView addButton = headerButton(ui("add"));
        addButton.setContentDescription(ui("add_feed"));
        addButton.setOnClickListener(v -> showAddFeedDialog());
        header.addView(addButton);

        TextView refreshButton = headerButton(ui("refresh"));
        refreshButton.setContentDescription(ui("refresh_feeds"));
        refreshButton.setOnClickListener(v -> refreshAllFeeds());
        header.addView(refreshButton);

        TextView moreButton = headerButton(ui("more"));
        moreButton.setContentDescription(ui("more_features"));
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
        searchInput.setHint(ui("search_hint"));
        searchRow.addView(searchInput, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button searchButton = new Button(this);
        searchButton.setText(ui("search"));
        searchButton.setOnClickListener(v -> loadArticles());
        searchRow.addView(searchButton);
        filters.addView(searchRow);

        LinearLayout toggles = new LinearLayout(this);
        toggles.setOrientation(LinearLayout.HORIZONTAL);
        unreadOnlyCheckbox = new CheckBox(this);
        unreadOnlyCheckbox.setText(ui("unread"));
        unreadOnlyCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> loadArticles());
        toggles.addView(unreadOnlyCheckbox);
        favoritesOnlyCheckbox = new CheckBox(this);
        favoritesOnlyCheckbox.setText(ui("favorite"));
        favoritesOnlyCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> loadArticles());
        toggles.addView(favoritesOnlyCheckbox);
        sortDescendingCheckbox = new CheckBox(this);
        sortDescendingCheckbox.setText(ui("descending"));
        sortDescendingCheckbox.setChecked(true);
        sortDescendingCheckbox.setOnCheckedChangeListener((buttonView, isChecked) -> loadArticles());
        toggles.addView(sortDescendingCheckbox);
        Button markAllReadButton = new Button(this);
        markAllReadButton.setText(ui("mark_all_read"));
        markAllReadButton.setOnClickListener(v -> markAllRead());
        toggles.addView(markAllReadButton);
        filters.addView(toggles);

        LinearLayout sortDateRow = new LinearLayout(this);
        sortDateRow.setOrientation(LinearLayout.HORIZONTAL);
        sortDateRow.setGravity(Gravity.CENTER_VERTICAL);
        sortSpinner = new Spinner(this);
        sortSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{ui("sort_published"), ui("sort_created"), ui("sort_title")}));
        sortSpinner.setOnItemSelectedListener(simpleSelectionListener());
        sortDateRow.addView(sortSpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        dateSpinner = new Spinner(this);
        dateSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{ui("all_dates"), ui("today"), ui("yesterday"), ui("last_7_days")}));
        dateSpinner.setOnItemSelectedListener(simpleSelectionListener());
        sortDateRow.addView(dateSpinner, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        filters.addView(sortDateRow);

        statusText = new TextView(this);
        statusText.setTextColor(Color.rgb(80, 88, 84));
        statusText.setPadding(0, dp(6), 0, 0);
        filters.addView(statusText);
        root.addView(filters);

        articleListView = new ListView(this);
        articleListView.setDivider(null);
        articleListView.setDividerHeight(dp(8));
        articleListView.setPadding(dp(10), dp(4), dp(10), dp(8));
        articleListView.setClipToPadding(false);
        articleAdapter = new ArrayAdapter<Article>(this, android.R.layout.simple_list_item_2, android.R.id.text1, articles) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                Article article = getItem(position);
                return articleRowView(article, parent);
            }
        };
        articleListView.setAdapter(articleAdapter);
        articleListView.setOnItemClickListener((parent, view, position, id) -> openArticle(articles.get(position)));
        root.addView(articleListView, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        LinearLayout pagerBar = new LinearLayout(this);
        pagerBar.setOrientation(LinearLayout.HORIZONTAL);
        pagerBar.setGravity(Gravity.CENTER_VERTICAL);
        pagerBar.setPadding(dp(10), dp(6), dp(10), dp(8));
        previousPageButton = new Button(this);
        previousPageButton.setText(ui("previous_page"));
        previousPageButton.setOnClickListener(v -> loadPreviousPage());
        pagerBar.addView(previousPageButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        pageInfoText = new TextView(this);
        pageInfoText.setTextColor(Color.rgb(80, 88, 84));
        pageInfoText.setTextSize(14);
        pageInfoText.setGravity(Gravity.CENTER);
        pagerBar.addView(pageInfoText, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        nextPageButton = new Button(this);
        nextPageButton.setText(ui("next_page"));
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
            Toast.makeText(this, ui("auto_updated") + totalNew + ui("articles_count_suffix") + ui("translated_prefix") + translated + ui("articles_count_suffix"), Toast.LENGTH_SHORT).show();
        } else if (translated > 0 || translationFailed > 0) {
            Toast.makeText(this, ui("auto_translation_done") + ui("success_prefix") + translated + ui("failed_prefix") + translationFailed, Toast.LENGTH_SHORT).show();
        } else if (fromResume && candidates > 0 && failed > 0) {
            Toast.makeText(this, ui("sync_done") + ui("success_prefix") + success + ui("failed_prefix") + failed, Toast.LENGTH_SHORT).show();
        }
    }

    private void showMoreMenu() {
        String[] actions = {
                ui("stats"),
                ui("import_opml"),
                ui("export_opml"),
                ui("export_backup"),
                ui("restore_backup"),
                ui("category_management"),
                ui("feed_management"),
                ui("keyword_management"),
                ui("data_sync"),
                ui("translation_settings"),
                ui("ai_default_model"),
                ui("ai_channels"),
                ui("settings")
        };
        new AlertDialog.Builder(this)
                .setTitle(ui("more"))
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
                        showTranslationSettingsDialog();
                    } else if (which == 10) {
                        showAiDefaultModelDialog();
                    } else if (which == 11) {
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

        TextView loading = drawerSection(ui("loading_categories"));
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
        title.setText(ui("nav_categories"));
        title.setTextColor(Color.rgb(30, 40, 37));
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView closeButton = drawerAction(ui("close"));
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

        TextView allItem = drawerItem(ui("all_articles"), totalArticles, totalUnread, selectedCategoryId == null && selectedFeedId == null && selectedKeywordId == null, 16);
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
                    content.addView(drawerSection(ui("uncategorized_feeds")));
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

        content.addView(drawerSection(ui("keyword_subscriptions")));
        if (loadedKeywords.isEmpty()) {
            TextView empty = drawerItem(ui("add_keyword_subscription"), 0, 0, false, 16);
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
        TextView addFeed = drawerAction(ui("add_feed"));
        addFeed.setOnClickListener(v -> {
            closeCategoryDrawer();
            showAddFeedDialog();
        });
        actions.addView(addFeed, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView manage = drawerAction(ui("manage_categories"));
        manage.setOnClickListener(v -> {
            closeCategoryDrawer();
            showCategoryManagement();
        });
        actions.addView(manage, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        TextView addKeyword = drawerAction(ui("keywords"));
        addKeyword.setOnClickListener(v -> {
            closeCategoryDrawer();
            showKeywordEditDialog(null);
        });
        actions.addView(addKeyword, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        drawerPanel.addView(actions);
    }

    private TextView drawerItem(String title, int count, int unread, boolean selected, int leftPadding) {
        TextView item = new TextView(this);
        StringBuilder label = new StringBuilder(title == null || title.trim().isEmpty() ? ui("unnamed") : title);
        if (unread > 0) {
            label.append("  ").append(unread).append(" ").append(ui("unread"));
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
        String[] actions = {ui("open_category"), ui("rename_category"), ui("delete_category")};
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
        String[] actions = {ui("open_feed"), ui("edit_feed"), ui("delete_feed")};
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
        String[] actions = {ui("open_keyword"), ui("edit_keyword"), ui("delete_keyword")};
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
        nameInput.setHint(ui("keyword_name_hint"));
        nameInput.setText(keyword == null ? "" : keyword.name);
        form.addView(labeledView(ui("name"), nameInput));

        EditText keywordInput = new EditText(this);
        keywordInput.setSingleLine(true);
        keywordInput.setHint(ui("keyword_hint"));
        keywordInput.setText(keyword == null ? "" : keyword.keyword);
        form.addView(labeledView(ui("keyword"), keywordInput));

        CheckBox activeInput = new CheckBox(this);
        activeInput.setText(ui("enable_keyword_subscription"));
        activeInput.setChecked(keyword == null || keyword.active);
        form.addView(activeInput);

        new AlertDialog.Builder(this)
                .setTitle(keyword == null ? ui("new_keyword_subscription") : ui("edit_keyword_subscription"))
                .setView(form)
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("save"), (dialog, which) -> {
                    String keywordText = keywordInput.getText().toString().trim();
                    String name = nameInput.getText().toString().trim();
                    if (keywordText.isEmpty()) {
                        Toast.makeText(this, ui("enter_keyword"), Toast.LENGTH_SHORT).show();
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
                                Toast.makeText(this, ui("keyword_saved"), Toast.LENGTH_SHORT).show();
                                loadFiltersAndArticles();
                            });
                        } catch (Exception e) {
                            runOnUiThread(() -> Toast.makeText(this, ui("save_failed") + localizeError(e), Toast.LENGTH_LONG).show());
                        }
                    });
                })
                .show();
    }

    private void confirmDeleteKeyword(KeywordSubscription keyword) {
        new AlertDialog.Builder(this)
                .setTitle(ui("delete_keyword_subscription"))
                .setMessage(ui("delete_keyword_confirm_prefix") + keyword.toString() + ui("delete_keyword_confirm_suffix"))
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("delete"), (dialog, which) -> executor.execute(() -> {
                    repository.deleteKeywordSubscription(keyword.id);
                    runOnUiThread(() -> {
                        if (selectedKeywordId != null && selectedKeywordId == keyword.id) {
                            selectedKeywordId = null;
                        }
                        Toast.makeText(this, ui("keyword_deleted"), Toast.LENGTH_SHORT).show();
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
        form.addView(labeledView(ui("category"), categoryInput));

        int[] intervals = intervalValues();
        Spinner intervalInput = spinnerForIntervals(intervals);
        selectInterval(intervalInput, intervals, settings.getDefaultFetchIntervalSeconds());
        form.addView(labeledView(ui("sync_interval"), intervalInput));

        Spinner translationModeInput = spinnerForTranslationModes();
        selectTranslationMode(translationModeInput, settings.getDefaultTranslationMode());
        form.addView(labeledView(ui("translation_mode"), translationModeInput));

        EditText languageInput = new EditText(this);
        languageInput.setSingleLine(true);
        languageInput.setText(displayLanguageName(settings.getDefaultTranslationLanguage()));
        form.addView(labeledView(ui("translate_to"), languageInput));

        new AlertDialog.Builder(this)
                .setTitle(ui("add_feed"))
                .setView(form)
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("add"), (dialog, which) -> {
                    String url = input.getText().toString().trim();
                    if (!url.startsWith("http://") && !url.startsWith("https://")) {
                        Toast.makeText(this, ui("enter_full_url"), Toast.LENGTH_SHORT).show();
                        return;
                    }
                    Category selectedCategory = categoryOptions.get(categoryInput.getSelectedItemPosition());
                    Long categoryId = selectedCategory.id <= 0 ? null : selectedCategory.id;
                    int interval = intervals[intervalInput.getSelectedItemPosition()];
                    addFeed(url, categoryId, interval, selectedTranslationMode(translationModeInput), normalizeLanguageInput(languageInput.getText().toString().trim()));
                })
                .show();
    }

    private void addFeed(String url, Long categoryId, int intervalSeconds, String translationMode, String translationLanguage) {
        ProgressDialog progress = ProgressDialog.show(this, ui("add_feed"), ui("fetching_rss"), true, false);
        syncExecutor.execute(() -> {
            try {
                ParsedFeed parsedFeed = new FeedParser().fetchAndParse(url);
                repository.addFeed(url, parsedFeed, categoryId, intervalSeconds, translationMode, translationLanguage);
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("feed_added"), Toast.LENGTH_SHORT).show();
                    if (settings.isBackgroundSyncEnabled()) {
                        SyncScheduler.schedule(this);
                    }
                    loadFiltersAndArticles();
                });
                if (isTranslationEnabled(translationMode)) {
                    scheduleAutoTranslation();
                }
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("add_failed") + localizeError(e), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void autoRefreshOnLaunch() {
        if (launchRefreshRunning) {
            return;
        }
        launchRefreshRunning = true;
        statusText.setText(ui("background_syncing"));
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
                    statusText.setText(ui("startup_sync_done") + ui("success_prefix") + result.success + ui("failed_prefix") + result.failed + ui("new_prefix") + result.inserted + ui("articles_count_suffix"));
                }
            });
            if (result.inserted > 0) {
                scheduleAutoTranslation();
            }
        });
    }

    private void refreshAllFeeds() {
        ProgressDialog progress = ProgressDialog.show(this, ui("refresh_feeds"), ui("syncing_local_feeds"), true, false);
        syncExecutor.execute(() -> {
            RefreshResult result = refreshFeedsInScope(selectedCategoryId, selectedFeedId);
            runOnUiThread(() -> {
                progress.dismiss();
                settings.markSyncCompleted(result.inserted, result.success, result.failed, result.candidates);
                lastHandledSyncCompletedAt = settings.getLastSyncCompletedAt();
                if (result.candidates == 0) {
                    Toast.makeText(this, ui("no_feeds_to_refresh"), Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(this, ui("refresh_done") + ui("success_prefix") + result.success + ui("failed_prefix") + result.failed + ui("new_prefix") + result.inserted, Toast.LENGTH_LONG).show();
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
        int[] ai = translateAiPendingArticles();
        int[] standard = translateStandardPendingArticles();
        int translated = ai[0] + standard[0];
        int failed = ai[1] + standard[1];
        runOnUiThread(() -> {
            if (translated > 0 || failed > 0) {
                loadFiltersAndArticles();
                Toast.makeText(this, ui("auto_translation_done") + ui("success_prefix") + translated + ui("failed_prefix") + failed, Toast.LENGTH_LONG).show();
            }
        });
    }

    private int[] translateAiPendingArticles() {
        if (repository.countPendingTranslationJobs("ai") <= 0) {
            return new int[]{0, 0};
        }
        AiChannel channel = repository.getDefaultAiChannel();
        if (channel == null || channel.apiKey == null || channel.apiKey.trim().isEmpty() || channel.model == null || channel.model.trim().isEmpty()) {
            runOnUiThread(() -> statusText.setText(ui("auto_translate_skipped_no_model")));
            return new int[]{0, 0};
        }
        AiClient client = new AiClient();
        return translatePendingBatch("ai", 5, job -> client.translate(channel, job));
    }

    private int[] translateStandardPendingArticles() {
        if (repository.countPendingTranslationJobs("standard") <= 0) {
            return new int[]{0, 0};
        }
        StandardTranslationClient client = new StandardTranslationClient();
        StandardTranslationSettings translationSettings = standardTranslationSettings();
        return translatePendingBatch("standard", 8, job -> client.translate(translationSettings, job));
    }

    private int[] translatePendingBatch(String mode, int batchSize, Translator translator) {
        int translated = 0;
        int failed = 0;
        while (true) {
            List<TranslationJob> jobs = repository.pendingTranslationJobs(mode, batchSize);
            if (jobs.isEmpty()) {
                return new int[]{translated, failed};
            }
            for (TranslationJob job : jobs) {
                try {
                    ArticleTranslation translation = translator.translate(job);
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
        runOnUiThread(() -> statusText.setText(ui("auto_ai_translating")));
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
            allCategory.name = ui("all_categories");
            loadedCategories.add(0, allCategory);

            List<Feed> loadedFeeds = repository.getFeeds();
            List<KeywordSubscription> loadedKeywords = repository.getKeywordSubscriptions();
            Feed allFeed = new Feed();
            allFeed.id = 0;
            allFeed.title = selectedKeywordId == null ? ui("all_articles") : ui("keyword_articles");
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
            allFeed.title = selectedCategoryId == null ? ui("all_articles") : ui("category_all_articles");
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
                scrollArticleListToTop();
                articleLoadRunning = false;
                if (pendingArticlePage != null) {
                    int nextPage = pendingArticlePage;
                    pendingArticlePage = null;
                    loadArticlesPage(nextPage);
                }
            });
        });
    }

    private void scrollArticleListToTop() {
        if (articleListView == null) {
            return;
        }
        articleListView.post(() -> articleListView.setSelectionFromTop(0, 0));
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
        aiTranslateButton.setText(ui("ai_translate"));
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
        unreadButton.setText(ui("mark_unread"));
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
        favoriteButton.setText(article.favorite ? ui("unfavorite") : ui("favorite"));
        favoriteButton.setTextSize(13);
        favoriteButton.setSingleLine(true);
        footer.addView(favoriteButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button shareButton = new Button(this);
        shareButton.setText(ui("share"));
        shareButton.setTextSize(13);
        shareButton.setSingleLine(true);
        footer.addView(shareButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button linkButton = new Button(this);
        linkButton.setText(ui("webpage"));
        linkButton.setTextSize(13);
        linkButton.setSingleLine(true);
        footer.addView(linkButton, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button originalButton = new Button(this);
        originalButton.setText(article.showOriginal ? ui("translation") : ui("original"));
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
            originalButton.setText(article.showOriginal ? ui("translation") : ui("original"));
        });
        favoriteButton.setOnClickListener(v -> {
            boolean favorite = repository.toggleFavorite(article.id);
            article.favorite = favorite;
            updateArticleListPresentation();
            favoriteButton.setText(favorite ? ui("unfavorite") : ui("favorite"));
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
            Toast.makeText(this, ui("marked_unread"), Toast.LENGTH_SHORT).show();
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
        String manualMode = manualTranslationMode(article);
        AiChannel channel = null;
        StandardTranslationSettings translationSettings = null;
        if ("ai".equals(manualMode)) {
            channel = repository.getDefaultAiChannel();
            if (channel == null || channel.apiKey == null || channel.apiKey.trim().isEmpty() || channel.model == null || channel.model.trim().isEmpty()) {
                Toast.makeText(this, ui("select_default_ai_first"), Toast.LENGTH_LONG).show();
                return;
            }
        } else {
            translationSettings = standardTranslationSettings();
        }
        if (!isTranslationEnabled(manualMode)) {
            Toast.makeText(this, ui("select_translation_mode_first"), Toast.LENGTH_LONG).show();
            return;
        }
        final AiChannel selectedChannel = channel;
        final StandardTranslationSettings selectedTranslationSettings = translationSettings;
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
            Toast.makeText(this, ui("manual_ai_running"), Toast.LENGTH_SHORT).show();
            return;
        }
        ProgressDialog progress = new ProgressDialog(this);
        long startedAt = System.currentTimeMillis();
        progress.setMessage(manualAiMessage(ui("stage_prepare_request"), startedAt, sourceLength));
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
                job.translationMode = manualMode;
                job.targetLanguage = targetLanguage;
                ArticleTranslation translation;
                if ("ai".equals(manualMode)) {
                    translation = new AiClient().translate(selectedChannel, job, stage ->
                            runOnUiThread(() -> {
                                if (manualTaskActive.get() && progress.isShowing()) {
                                    progress.setMessage(manualAiMessage(localizeAiStage(stage), startedAt, sourceLength));
                                }
                            }));
                } else {
                    runOnUiThread(() -> {
                        if (manualTaskActive.get() && progress.isShowing()) {
                            progress.setMessage(manualAiMessage(ui("stage_standard_translate"), startedAt, sourceLength));
                        }
                    });
                    translation = new StandardTranslationClient().translate(selectedTranslationSettings, job);
                }
                if (!manualTaskActive.get()) {
                    return;
                }
                runOnUiThread(() -> {
                    if (manualTaskActive.get() && progress.isShowing()) {
                        progress.setMessage(manualAiMessage(ui("stage_save_result"), startedAt, sourceLength));
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
                    throw new IllegalStateException(ui("translation_readback_failed"));
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
                        originalButton.setText(ui("original"));
                        originalButton.setVisibility(View.VISIBLE);
                    }
                    updateArticleListPresentation();
                    Toast.makeText(this, ui("ai_translation_saved") + elapsedSeconds(startedAt) + ui("seconds_suffix"), Toast.LENGTH_SHORT).show();
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
                    Toast.makeText(this, ui("ai_translation_failed") + localizeError(e) + ui("elapsed_prefix") + elapsedSeconds(startedAt) + ui("seconds_body_prefix") + sourceLength + ui("chars_suffix"), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private String manualAiMessage(String stage, long startedAt, int sourceLength) {
        return ui("manual_ai_progress") + stage + "\n" + ui("elapsed_time") + elapsedSeconds(startedAt) + ui("seconds_body_prefix") + sourceLength + ui("chars_suffix");
    }

    private String manualTranslationMode(Article article) {
        if (article != null && isTranslationEnabled(article.feedTranslationMode)) {
            return article.feedTranslationMode;
        }
        return settings.getDefaultTranslationMode();
    }

    private StandardTranslationSettings standardTranslationSettings() {
        StandardTranslationSettings value = new StandardTranslationSettings();
        value.provider = settings.getStandardTranslationProvider();
        value.baiduAppId = settings.getBaiduTranslateAppId();
        value.baiduSecret = settings.getBaiduTranslateSecret();
        value.tencentSecretId = settings.getTencentTranslateSecretId();
        value.tencentSecretKey = settings.getTencentTranslateSecretKey();
        value.tencentRegion = settings.getTencentTranslateRegion();
        value.googleApiKey = settings.getGoogleTranslateApiKey();
        value.microsoftKey = settings.getMicrosoftTranslateKey();
        value.microsoftRegion = settings.getMicrosoftTranslateRegion();
        return value;
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
            text.append(ui("mrss_article"));
        }
        Intent sendIntent = new Intent(Intent.ACTION_SEND);
        sendIntent.setType("text/plain");
        sendIntent.putExtra(Intent.EXTRA_SUBJECT, title.isEmpty() ? ui("mrss_article") : title);
        sendIntent.putExtra(Intent.EXTRA_TEXT, text.toString());
        startActivity(Intent.createChooser(sendIntent, ui("share_article")));
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
                Toast.makeText(this, ui("marked_articles_prefix") + markedCount + ui("articles_count_suffix"), Toast.LENGTH_SHORT).show();
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
        ProgressDialog progress = ProgressDialog.show(this, ui("import_opml"), ui("reading_subscriptions"), true, false);
        executor.execute(() -> {
            try {
                String content = readText(uri);
                List<OpmlFeed> opmlFeeds = OpmlUtils.parse(content);
                int imported = repository.importOpmlFeeds(opmlFeeds, settings.getDefaultFetchIntervalSeconds());
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("imported_prefix") + imported + ui("feeds_count_suffix"), Toast.LENGTH_LONG).show();
                    if (settings.isBackgroundSyncEnabled()) {
                        SyncScheduler.schedule(this);
                    }
                    loadFiltersAndArticles();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("import_failed") + localizeError(e), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void exportOpml(Uri uri) {
        ProgressDialog progress = ProgressDialog.show(this, ui("export_opml"), ui("writing_file"), true, false);
        executor.execute(() -> {
            try {
                String content = OpmlUtils.generate(repository.getFeedsForExport());
                try (OutputStream output = getContentResolver().openOutputStream(uri)) {
                    if (output == null) {
                        throw new IllegalStateException(ui("cannot_open_output"));
                    }
                    output.write(content.getBytes(StandardCharsets.UTF_8));
                }
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("opml_exported"), Toast.LENGTH_SHORT).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("export_failed") + localizeError(e), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void exportBackup(Uri uri) {
        ProgressDialog progress = ProgressDialog.show(this, ui("export_backup"), ui("writing_backup"), true, false);
        executor.execute(() -> {
            try {
                String content = repository.exportBackupJson();
                try (OutputStream output = getContentResolver().openOutputStream(uri)) {
                    if (output == null) {
                        throw new IllegalStateException(ui("cannot_open_output"));
                    }
                    output.write(content.getBytes(StandardCharsets.UTF_8));
                }
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("backup_exported"), Toast.LENGTH_SHORT).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("export_failed") + localizeError(e), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void restoreBackup(Uri uri) {
        new AlertDialog.Builder(this)
                .setTitle(ui("restore_backup"))
                .setMessage(ui("restore_backup_confirm"))
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("restore"), (dialog, which) -> {
                    ProgressDialog progress = ProgressDialog.show(this, ui("restore_backup"), ui("restoring_local_data"), true, false);
                    executor.execute(() -> {
                        try {
                            repository.restoreBackupJson(readText(uri));
                            runOnUiThread(() -> {
                                progress.dismiss();
                                Toast.makeText(this, ui("backup_restored"), Toast.LENGTH_SHORT).show();
                                if (settings.isBackgroundSyncEnabled()) {
                                    SyncScheduler.schedule(this);
                                }
                                loadFiltersAndArticles();
                            });
                        } catch (Exception e) {
                            runOnUiThread(() -> {
                                progress.dismiss();
                                Toast.makeText(this, ui("restore_failed") + localizeError(e), Toast.LENGTH_LONG).show();
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
                        ? dateTimeFormat().format(new Date(stats.latestArticleAt))
                        : ui("none");
                String message = ui("stats_categories") + stats.categoryCount +
                        "\n" + ui("stats_feeds") + stats.feedCount + ui("stats_active_prefix") + stats.activeFeedCount + ui("stats_active_suffix") +
                        "\n" + ui("stats_articles") + stats.articleCount +
                        "\n" + ui("stats_unread") + stats.unreadCount +
                        "\n" + ui("stats_favorites") + stats.favoriteCount +
                        "\n" + ui("stats_today") + stats.todayCount +
                        "\n" + ui("stats_last_7_days") + stats.lastSevenDaysCount +
                        "\n" + ui("stats_latest") + latest;
                new AlertDialog.Builder(this)
                        .setTitle(ui("local_stats"))
                        .setMessage(message)
                        .setPositiveButton(ui("ok"), null)
                        .show();
            });
        });
    }

    private void showCategoryManagement() {
        executor.execute(() -> {
            List<Category> current = repository.getCategories();
            runOnUiThread(() -> {
                List<String> labels = new ArrayList<>();
                labels.add(ui("new_category"));
                for (Category category : current) {
                    labels.add(category.name + " · " + category.feedCount + ui("feeds_count_suffix"));
                }
                new AlertDialog.Builder(this)
                        .setTitle(ui("category_management"))
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
        input.setHint(ui("category_name"));
        if (category != null) {
            input.setText(category.name);
        }
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(category == null ? ui("new_category") : ui("edit_category"))
                .setView(input)
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("save"), null)
                .setNeutralButton(category == null ? null : ui("delete"), null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String name = input.getText().toString().trim();
                if (name.isEmpty()) {
                    Toast.makeText(this, ui("category_name_required"), Toast.LENGTH_SHORT).show();
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
                .setTitle(ui("delete_category"))
                .setMessage(ui("delete_category_confirm"))
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("delete"), (confirm, which) -> executor.execute(() -> {
                    repository.deleteCategory(category.id);
                    runOnUiThread(() -> {
                        if (parentDialog != null) {
                            parentDialog.dismiss();
                        }
                        if (selectedCategoryId != null && selectedCategoryId == category.id) {
                            selectedCategoryId = null;
                            selectedFeedId = null;
                        }
                        Toast.makeText(this, ui("category_deleted"), Toast.LENGTH_SHORT).show();
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
                    Toast.makeText(this, ui("no_feeds_yet"), Toast.LENGTH_SHORT).show();
                    return;
                }
                List<String> labels = new ArrayList<>();
                for (Feed feed : current) {
                    labels.add(feed.title + "\n" + feed.url);
                }
                new AlertDialog.Builder(this)
                        .setTitle(ui("feed_management"))
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
                labels.add(ui("new_keyword_subscription"));
                for (KeywordSubscription keyword : current) {
                    labels.add(keyword.toString() + " · " + keyword.keyword + (keyword.active ? "" : ui("disabled_suffix")));
                }
                new AlertDialog.Builder(this)
                        .setTitle(ui("keyword_management"))
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
        form.addView(labeledView(ui("title"), titleInput));

        TextView urlView = new TextView(this);
        urlView.setText(feed.url);
        urlView.setTextColor(Color.rgb(80, 88, 84));
        form.addView(labeledView(ui("address"), urlView));

        List<Category> categoryOptions = categoryOptions(true);
        Spinner categoryInput = spinnerForCategories(categoryOptions);
        selectCategory(categoryInput, categoryOptions, feed.categoryId);
        form.addView(labeledView(ui("category"), categoryInput));

        int[] intervals = intervalValues();
        Spinner intervalInput = spinnerForIntervals(intervals);
        selectInterval(intervalInput, intervals, feed.fetchIntervalSeconds);
        form.addView(labeledView(ui("sync_interval"), intervalInput));

        CheckBox activeInput = new CheckBox(this);
        activeInput.setText(ui("enable_auto_sync"));
        activeInput.setChecked(feed.active);
        form.addView(activeInput);

        Spinner translationModeInput = spinnerForTranslationModes();
        selectTranslationMode(translationModeInput, feed.translateEnabled ? feed.translationMode : "off");
        form.addView(labeledView(ui("translation_mode"), translationModeInput));

        EditText languageInput = new EditText(this);
        languageInput.setSingleLine(true);
        languageInput.setText(displayLanguageName(feed.translationLanguage == null || feed.translationLanguage.trim().isEmpty() ? settings.getDefaultTranslationLanguage() : feed.translationLanguage));
        form.addView(labeledView(ui("translate_to"), languageInput));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(ui("edit_feed"))
                .setView(form)
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("save"), null)
                .setNeutralButton(ui("delete"), null)
                .create();
        dialog.setOnShowListener(d -> {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String title = titleInput.getText().toString().trim();
                Category category = categoryOptions.get(categoryInput.getSelectedItemPosition());
                Long categoryId = category.id <= 0 ? null : category.id;
                int interval = intervals[intervalInput.getSelectedItemPosition()];
                String translationMode = selectedTranslationMode(translationModeInput);
                executor.execute(() -> {
                    repository.updateFeed(feed.id, title, categoryId, interval, activeInput.isChecked(), translationMode, normalizeLanguageInput(languageInput.getText().toString().trim()));
                    if (isTranslationEnabled(translationMode)) {
                        repository.resetFailedTranslationsForFeed(feed.id);
                    }
                    runOnUiThread(() -> {
                        dialog.dismiss();
                        Toast.makeText(this, ui("feed_saved"), Toast.LENGTH_SHORT).show();
                        if (settings.isBackgroundSyncEnabled()) {
                            SyncScheduler.schedule(this);
                        }
                        loadFiltersAndArticles();
                        if (isTranslationEnabled(translationMode)) {
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
                .setTitle(ui("delete_feed"))
                .setMessage(ui("delete_feed_confirm"))
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("delete"), (confirm, which) -> executor.execute(() -> {
                    repository.deleteFeed(feed.id);
                    runOnUiThread(() -> {
                        if (parentDialog != null) {
                            parentDialog.dismiss();
                        }
                        if (selectedFeedId != null && selectedFeedId == feed.id) {
                            selectedFeedId = null;
                        }
                        Toast.makeText(this, ui("feed_deleted"), Toast.LENGTH_SHORT).show();
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
        tokenInput.setHint(ui("github_token_hint"));
        tokenInput.setText(settings.getGithubToken());
        form.addView(labeledView(ui("github_token_label"), tokenInput));

        EditText gistInput = new EditText(this);
        gistInput.setSingleLine(true);
        gistInput.setHint(ui("gist_id_hint"));
        gistInput.setText(settings.getGistId());
        form.addView(labeledView(ui("gist_id_label"), gistInput));

        EditText filenameInput = new EditText(this);
        filenameInput.setSingleLine(true);
        filenameInput.setText(settings.getGistFilename());
        form.addView(labeledView(ui("filename"), filenameInput));

        TextView hint = new TextView(this);
        hint.setText(ui("data_sync_hint"));
        hint.setTextColor(Color.rgb(80, 88, 84));
        hint.setTextSize(13);
        form.addView(hint);

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(ui("data_sync"))
                .setView(form)
                .setNegativeButton(ui("close"), null)
                .setNeutralButton(ui("download_merge"), null)
                .setPositiveButton(ui("upload"), null)
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
                        Toast.makeText(this, ui("gist_id_required_for_download"), Toast.LENGTH_SHORT).show();
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
            Toast.makeText(this, ui("github_token_required"), Toast.LENGTH_SHORT).show();
            return false;
        }
        if (filename.isEmpty()) {
            Toast.makeText(this, ui("filename_required"), Toast.LENGTH_SHORT).show();
            return false;
        }
        return true;
    }

    private void uploadSubscriptionSync(String token, String gistId, String filename, AlertDialog dialog) {
        ProgressDialog progress = ProgressDialog.show(this, ui("data_sync"), ui("uploading_subscriptions"), true, false);
        syncExecutor.execute(() -> {
            try {
                String content = repository.exportSubscriptionSyncJson();
                String newGistId = new GistClient().upload(token, gistId, filename, content);
                settings.setGistSettings(token, newGistId, filename);
                runOnUiThread(() -> {
                    progress.dismiss();
                    dialog.dismiss();
                    Toast.makeText(this, ui("uploaded_to_gist") + newGistId, Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("upload_failed") + localizeError(e), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void downloadSubscriptionSync(String token, String gistId, String filename, AlertDialog dialog) {
        ProgressDialog progress = ProgressDialog.show(this, ui("data_sync"), ui("downloading_merging"), true, false);
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
                    Toast.makeText(this, ui("merged_sync_data") + changed + ui("items_count_suffix"), Toast.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("download_failed") + localizeError(e), Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private void showSettingsDialog() {
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);

        Spinner appLanguageInput = new Spinner(this);
        String[] appLanguageValues = {"zh", "en"};
        appLanguageInput.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{ui("language_chinese"), ui("language_english")}));
        appLanguageInput.setSelection("en".equals(settings.getAppLanguage()) ? 1 : 0);
        form.addView(labeledView(ui("app_language"), appLanguageInput));

        int[] intervals = intervalValues();
        Spinner intervalInput = spinnerForIntervals(intervals);
        selectInterval(intervalInput, intervals, settings.getDefaultFetchIntervalSeconds());
        form.addView(labeledView(ui("default_sync_interval"), intervalInput));

        int[] pageSizes = articlePageSizeValues();
        Spinner pageSizeInput = spinnerForPageSizes(pageSizes);
        selectPageSize(pageSizeInput, pageSizes, settings.getArticlePageSize());
        form.addView(labeledView(ui("page_size"), pageSizeInput));

        EditText defaultLanguageInput = new EditText(this);
        defaultLanguageInput.setSingleLine(true);
        defaultLanguageInput.setText(displayLanguageName(settings.getDefaultTranslationLanguage()));
        form.addView(labeledView(ui("default_translation_language"), defaultLanguageInput));

        CheckBox backgroundSync = new CheckBox(this);
        backgroundSync.setText(ui("enable_background_sync"));
        backgroundSync.setChecked(settings.isBackgroundSyncEnabled());
        form.addView(backgroundSync);

        TextView exactAlarmHint = new TextView(this);
        exactAlarmHint.setText(ui("exact_alarm_hint"));
        exactAlarmHint.setTextColor(Color.rgb(80, 88, 84));
        exactAlarmHint.setTextSize(13);
        form.addView(exactAlarmHint);

        new AlertDialog.Builder(this)
                .setTitle(ui("settings"))
                .setView(form)
                .setNegativeButton(ui("cancel"), null)
                .setNeutralButton(ui("system_permissions"), (dialog, which) -> openSyncSystemSettings())
                .setPositiveButton(ui("save"), (dialog, which) -> {
                    String oldLanguage = settings.getAppLanguage();
                    String newLanguage = appLanguageValues[appLanguageInput.getSelectedItemPosition()];
                    settings.setAppLanguage(newLanguage);
                    appLanguage = settings.getAppLanguage();
                    settings.setDefaultFetchIntervalSeconds(intervals[intervalInput.getSelectedItemPosition()]);
                    settings.setArticlePageSize(pageSizes[pageSizeInput.getSelectedItemPosition()]);
                    settings.setDefaultTranslationLanguage(normalizeLanguageInput(defaultLanguageInput.getText().toString().trim()));
                    settings.setBackgroundSyncEnabled(backgroundSync.isChecked());
                    if (backgroundSync.isChecked()) {
                        SyncScheduler.schedule(this);
                    } else {
                        SyncScheduler.cancel(this);
                    }
                    if (!oldLanguage.equals(appLanguage)) {
                        buildUi();
                        loadFiltersAndArticles();
                    } else {
                        loadArticles();
                    }
                    Toast.makeText(this, ui("settings_saved"), Toast.LENGTH_SHORT).show();
                })
                .show();
    }

    private void showTranslationSettingsDialog() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(dp(16), dp(8), dp(16), 0);
        scroll.addView(form);

        Spinner modeInput = spinnerForTranslationModes();
        selectTranslationMode(modeInput, settings.getDefaultTranslationMode());
        form.addView(labeledView(ui("default_translation_mode"), modeInput));

        EditText defaultLanguageInput = new EditText(this);
        defaultLanguageInput.setSingleLine(true);
        defaultLanguageInput.setText(displayLanguageName(settings.getDefaultTranslationLanguage()));
        form.addView(labeledView(ui("default_translation_language"), defaultLanguageInput));

        Spinner providerInput = spinnerForStandardProviders();
        selectStandardProvider(providerInput, settings.getStandardTranslationProvider());
        form.addView(labeledView(ui("standard_provider"), providerInput));

        EditText baiduAppId = new EditText(this);
        baiduAppId.setSingleLine(true);
        baiduAppId.setText(settings.getBaiduTranslateAppId());
        form.addView(labeledView(ui("baidu_app_id"), baiduAppId));

        EditText baiduSecret = new EditText(this);
        baiduSecret.setSingleLine(true);
        baiduSecret.setText(settings.getBaiduTranslateSecret());
        form.addView(labeledView(ui("baidu_secret"), baiduSecret));

        EditText tencentSecretId = new EditText(this);
        tencentSecretId.setSingleLine(true);
        tencentSecretId.setText(settings.getTencentTranslateSecretId());
        form.addView(labeledView(ui("tencent_secret_id"), tencentSecretId));

        EditText tencentSecretKey = new EditText(this);
        tencentSecretKey.setSingleLine(true);
        tencentSecretKey.setText(settings.getTencentTranslateSecretKey());
        form.addView(labeledView(ui("tencent_secret_key"), tencentSecretKey));

        EditText tencentRegion = new EditText(this);
        tencentRegion.setSingleLine(true);
        tencentRegion.setText(settings.getTencentTranslateRegion());
        form.addView(labeledView(ui("tencent_region"), tencentRegion));

        EditText googleApiKey = new EditText(this);
        googleApiKey.setSingleLine(true);
        googleApiKey.setText(settings.getGoogleTranslateApiKey());
        form.addView(labeledView(ui("google_api_key"), googleApiKey));

        EditText microsoftKey = new EditText(this);
        microsoftKey.setSingleLine(true);
        microsoftKey.setText(settings.getMicrosoftTranslateKey());
        form.addView(labeledView(ui("microsoft_key"), microsoftKey));

        EditText microsoftRegion = new EditText(this);
        microsoftRegion.setSingleLine(true);
        microsoftRegion.setText(settings.getMicrosoftTranslateRegion());
        form.addView(labeledView(ui("microsoft_region"), microsoftRegion));

        TextView hint = new TextView(this);
        hint.setText(ui("standard_translation_hint"));
        hint.setTextColor(Color.rgb(80, 88, 84));
        hint.setTextSize(12);
        hint.setPadding(0, dp(8), 0, 0);
        form.addView(hint);

        new AlertDialog.Builder(this)
                .setTitle(ui("translation_settings"))
                .setView(scroll)
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("save"), (dialog, which) -> {
                    settings.setDefaultTranslationMode(selectedTranslationMode(modeInput));
                    settings.setDefaultTranslationLanguage(normalizeLanguageInput(defaultLanguageInput.getText().toString().trim()));
                    settings.setStandardTranslationProvider(selectedStandardProvider(providerInput));
                    settings.setBaiduTranslateSettings(baiduAppId.getText().toString(), baiduSecret.getText().toString());
                    settings.setTencentTranslateSettings(tencentSecretId.getText().toString(), tencentSecretKey.getText().toString(), tencentRegion.getText().toString());
                    settings.setGoogleTranslateApiKey(googleApiKey.getText().toString());
                    settings.setMicrosoftTranslateSettings(microsoftKey.getText().toString(), microsoftRegion.getText().toString());
                    Toast.makeText(this, ui("translation_settings_saved"), Toast.LENGTH_SHORT).show();
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
        title.setText(ui("current_default"));
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
        section.setText(ui("set_default_model"));
        section.setTypeface(Typeface.DEFAULT_BOLD);
        section.setTextSize(15);
        section.setTextColor(Color.rgb(15, 23, 42));
        section.setPadding(0, dp(16), 0, 0);
        form.addView(section);

        Spinner defaultChannelInput = new Spinner(this);
        List<String> channelLabels = new ArrayList<>();
        if (channels.isEmpty()) {
            channelLabels.add(ui("no_channels_add_first"));
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
        form.addView(labeledView(ui("default_channel"), defaultChannelInput));

        Spinner defaultModelInput = new Spinner(this);
        List<String> modelOptions = new ArrayList<>();
        modelOptions.add(ui("fetch_models_first"));
        defaultModelInput.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, modelOptions));
        defaultModelInput.setEnabled(false);
        form.addView(labeledView(ui("default_model"), defaultModelInput));

        EditText customModelInput = new EditText(this);
        customModelInput.setSingleLine(true);
        customModelInput.setHint(ui("custom_model_hint"));
        form.addView(labeledView(ui("custom_model"), customModelInput));

        Button saveDefaultButton = new Button(this);
        saveDefaultButton.setText(ui("save_default"));
        saveDefaultButton.setAllCaps(false);
        saveDefaultButton.setEnabled(!channels.isEmpty());
        form.addView(saveDefaultButton);

        Runnable refreshDefaultModelText = () -> {
            if (channels.isEmpty()) {
                currentSummary.setText(ui("default_channel_not_set") + "\n" + ui("default_model_not_set") + "\n" + ui("default_translation_language_summary") + displayLanguageName(settings.getDefaultTranslationLanguage()));
                modelOptions.clear();
                modelOptions.add(ui("add_channel_first"));
                ((ArrayAdapter<?>) defaultModelInput.getAdapter()).notifyDataSetChanged();
                return;
            }
            AiChannel active = defaultAiChannel(channels);
            AiChannel selected = channels.get(defaultChannelInput.getSelectedItemPosition());
            currentSummary.setText(ui("default_channel_summary") + active.name + " (" + aiProviderLabel(active.provider) + ")\n" + ui("default_model_summary") + (TextUtils.isEmpty(active.model) ? ui("not_selected") : active.model) + "\n" + ui("default_translation_language_summary") + displayLanguageName(settings.getDefaultTranslationLanguage()));
            customModelInput.setText(selected.model == null ? "" : selected.model);
            modelOptions.clear();
            if (selected.models == null || selected.models.isEmpty()) {
                modelOptions.add(ui("channel_models_not_fetched"));
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
                .setTitle(ui("ai_default_model"))
                .setView(form)
                .setNeutralButton(ui("channel_management"), null)
                .setNegativeButton(ui("close"), null)
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
                    Toast.makeText(this, ui("add_ai_channel_first"), Toast.LENGTH_SHORT).show();
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
                } else if (defaultModelInput.isEnabled() && !modelOptions.isEmpty() && !modelOptions.get(0).equals(ui("channel_models_not_fetched"))) {
                    selected.model = modelOptions.get(defaultModelInput.getSelectedItemPosition());
                } else {
                    Toast.makeText(this, ui("choose_or_enter_default_model"), Toast.LENGTH_SHORT).show();
                    return;
                }
                saveDefaultAiModel(channels, selected, refreshDefaultModelText);
            });
        });
        dialog.show();
    }

    private void saveDefaultAiModel(List<AiChannel> channels, AiChannel selected, Runnable onSaved) {
        if (selected == null || TextUtils.isEmpty(selected.model)) {
            Toast.makeText(this, ui("select_model_first"), Toast.LENGTH_SHORT).show();
            return;
        }
        for (AiChannel channel : channels) {
            channel.isDefault = channel == selected;
        }
        executor.execute(() -> {
            repository.saveAiChannels(channels);
            runOnUiThread(() -> {
                Toast.makeText(this, ui("default_model_saved"), Toast.LENGTH_SHORT).show();
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
        hint.setText(ui("ai_channel_hint"));
        hint.setTextColor(Color.rgb(80, 88, 84));
        hint.setTextSize(13);
        hint.setPadding(0, 0, 0, dp(8));
        form.addView(hint);

        ListView channelList = new ListView(this);
        channelList.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, manageLabelsForChannels(channels)));
        channelList.setDividerHeight(1);
        form.addView(channelList, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(320)));

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(ui("ai_channels"))
                .setView(form)
                .setNeutralButton(ui("default_model"), null)
                .setNegativeButton(ui("close"), null)
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
        labels.add(ui("new_channel"));
        for (AiChannel channel : channels) {
            labels.add(aiChannelLabel(channel));
        }
        return labels;
    }

    private String aiChannelLabel(AiChannel channel) {
        if (channel == null) {
            return ui("ai_channel");
        }
        String name = TextUtils.isEmpty(channel.name) ? ui("ai_channel") : displayChannelName(channel.name);
        String model = TextUtils.isEmpty(channel.model) ? ui("model_not_selected") : channel.model;
        return name + " · " + aiProviderLabel(channel.provider) + " · " + model + (channel.isDefault ? " · " + ui("default") : "");
    }

    private String aiProviderLabel(String provider) {
        if ("gemini".equals(provider)) {
            return isEnglish() ? "Gemini Official" : "Gemini 官方";
        }
        if ("qwen".equals(provider)) {
            return isEnglish() ? "Qwen" : "通义千问";
        }
        if ("doubao".equals(provider)) {
            return isEnglish() ? "Doubao" : "豆包";
        }
        if ("deepseek".equals(provider)) {
            return "DeepSeek";
        }
        if ("kimi".equals(provider)) {
            return "Kimi";
        }
        if ("zhipu".equals(provider)) {
            return isEnglish() ? "Zhipu" : "智谱";
        }
        if ("openai_compatible".equals(provider)) {
            return isEnglish() ? "OpenAI Compatible" : "OpenAI 兼容";
        }
        return isEnglish() ? "OpenAI Official" : "OpenAI 官方";
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
        nameInput.setText(channel == null ? aiProviderLabel("openai") : displayChannelName(channel.name));
        form.addView(labeledView(ui("channel_name"), nameInput));

        Spinner providerInput = new Spinner(this);
        List<String> providers = new ArrayList<>();
        providers.add(aiProviderLabel("openai"));
        providers.add(aiProviderLabel("gemini"));
        providers.add(aiProviderLabel("qwen"));
        providers.add(aiProviderLabel("doubao"));
        providers.add("DeepSeek");
        providers.add("Kimi");
        providers.add(aiProviderLabel("zhipu"));
        providers.add(aiProviderLabel("openai_compatible"));
        providerInput.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, providers));
        providerInput.setSelection(providerIndex(channel == null ? "openai" : channel.provider));
        form.addView(labeledView(ui("type"), providerInput));

        EditText baseUrlInput = new EditText(this);
        baseUrlInput.setSingleLine(true);
        baseUrlInput.setText(channel == null ? "" : channel.baseUrl);
        LinearLayout baseUrlRow = labeledView(ui("base_url"), baseUrlInput);
        form.addView(baseUrlRow);

        EditText keyInput = new EditText(this);
        keyInput.setSingleLine(true);
        keyInput.setText(channel == null ? "" : channel.apiKey);
        form.addView(labeledView(ui("api_key"), keyInput));

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
        fetchModelsButton.setText(ui("fetch_save_models"));
        fetchModelsButton.setAllCaps(false);
        form.addView(fetchModelsButton);

        AlertDialog.Builder builder = new AlertDialog.Builder(this)
                .setTitle(channel == null ? ui("new_ai_channel") : ui("edit_ai_channel"))
                .setView(form)
                .setNegativeButton(ui("cancel"), null)
                .setPositiveButton(ui("save"), null);
        if (channel != null) {
            builder.setNeutralButton(ui("delete"), null);
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
                    hintView.setText(ui("hint_gemini"));
                } else if ("qwen".equals(provider)) {
                    hintView.setText(ui("hint_qwen"));
                } else if ("doubao".equals(provider)) {
                    hintView.setText(ui("hint_doubao"));
                } else if ("deepseek".equals(provider)) {
                    hintView.setText(ui("hint_deepseek"));
                } else if ("kimi".equals(provider)) {
                    hintView.setText(ui("hint_kimi"));
                } else if ("zhipu".equals(provider)) {
                    hintView.setText(ui("hint_zhipu"));
                } else if (custom) {
                    hintView.setText(ui("hint_openai_compatible"));
                } else {
                    hintView.setText(ui("hint_openai"));
                }
            };
            Runnable updateModelsText = () -> {
                List<String> cachedModels = channel == null ? new ArrayList<>() : channel.models;
                if (cachedModels == null || cachedModels.isEmpty()) {
                    modelsView.setText(ui("cached_models") + "0");
                } else {
                    modelsView.setText(ui("cached_models") + cachedModels.size() + "\n" + ui("current_default_model") + (TextUtils.isEmpty(channel.model) ? ui("not_selected") : channel.model));
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
                    Toast.makeText(this, ui("channel_name_required"), Toast.LENGTH_SHORT).show();
                    return;
                }
                AiChannel target = channel == null ? new AiChannel() : channel;
                target.name = name;
                target.provider = providerValue(providerInput.getSelectedItemPosition());
                target.baseUrl = "openai_compatible".equals(target.provider) ? baseUrlInput.getText().toString().trim() : "";
                target.apiKey = keyInput.getText().toString();
                if (TextUtils.isEmpty(target.apiKey)) {
                    Toast.makeText(this, ui("api_key_required"), Toast.LENGTH_SHORT).show();
                    return;
                }
                if ("openai_compatible".equals(target.provider) && TextUtils.isEmpty(target.baseUrl)) {
                    Toast.makeText(this, ui("base_url_required"), Toast.LENGTH_SHORT).show();
                    return;
                }
                fetchAndCacheModels(existingChannels, target, channel == null, dialog);
            });
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
                String name = nameInput.getText().toString().trim();
                if (name.isEmpty()) {
                    Toast.makeText(this, ui("channel_name_required"), Toast.LENGTH_SHORT).show();
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
                        Toast.makeText(this, ui("ai_settings_saved"), Toast.LENGTH_SHORT).show();
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
                            Toast.makeText(this, ui("channel_deleted"), Toast.LENGTH_SHORT).show();
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
        progress.setMessage(ui("fetching_models"));
        progress.setCancelable(false);
        progress.show();
        executor.execute(() -> {
            try {
                List<String> models = new AiClient().fetchModels(target);
                if (models.isEmpty()) {
                    throw new IllegalStateException(ui("no_models_fetched"));
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
                    Toast.makeText(this, ui("models_fetched_saved_prefix") + models.size() + ui("models_count_suffix"), Toast.LENGTH_SHORT).show();
                    showAiChannelManagementDialog();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    progress.dismiss();
                    Toast.makeText(this, ui("fetch_failed") + localizeError(e), Toast.LENGTH_LONG).show();
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
            Toast.makeText(this, ui("cannot_open_system_settings"), Toast.LENGTH_SHORT).show();
        }
    }

    private List<Category> categoryOptions(boolean includeUncategorized) {
        List<Category> options = new ArrayList<>();
        if (includeUncategorized) {
            Category none = new Category();
            none.id = 0;
            none.name = ui("uncategorized");
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
            labels.add(pageSize + ui("articles_per_page_suffix"));
        }
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, labels));
        return spinner;
    }

    private Spinner spinnerForTranslationModes() {
        Spinner spinner = new Spinner(this);
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{
                ui("translation_off"),
                ui("translation_ai"),
                ui("translation_standard")
        }));
        return spinner;
    }

    private Spinner spinnerForStandardProviders() {
        Spinner spinner = new Spinner(this);
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{
                ui("provider_microsoft"),
                ui("provider_google"),
                ui("provider_baidu"),
                ui("provider_tencent")
        }));
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

    private void selectTranslationMode(Spinner spinner, String mode) {
        if ("ai".equals(mode)) {
            spinner.setSelection(1);
        } else if ("standard".equals(mode)) {
            spinner.setSelection(2);
        } else {
            spinner.setSelection(0);
        }
    }

    private String selectedTranslationMode(Spinner spinner) {
        int position = spinner == null ? 0 : spinner.getSelectedItemPosition();
        if (position == 1) {
            return "ai";
        }
        if (position == 2) {
            return "standard";
        }
        return "off";
    }

    private void selectStandardProvider(Spinner spinner, String provider) {
        if ("google".equals(provider)) {
            spinner.setSelection(1);
        } else if ("baidu".equals(provider)) {
            spinner.setSelection(2);
        } else if ("tencent".equals(provider)) {
            spinner.setSelection(3);
        } else {
            spinner.setSelection(0);
        }
    }

    private String selectedStandardProvider(Spinner spinner) {
        int position = spinner == null ? 0 : spinner.getSelectedItemPosition();
        if (position == 1) {
            return "google";
        }
        if (position == 2) {
            return "baidu";
        }
        if (position == 3) {
            return "tencent";
        }
        return "microsoft";
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
            return (seconds / 60) + " " + ui("minutes");
        }
        if (seconds < 86400) {
            return (seconds / 3600) + " " + ui("hours");
        }
        return "24 " + ui("hours");
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

    private boolean isTranslationEnabled(String mode) {
        return "ai".equals(mode) || "standard".equals(mode);
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
                throw new IllegalStateException(ui("cannot_open_file"));
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
            builder.append(dateTimeFormat().format(new Date(date)));
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
            prefix = keyword == null ? ui("keyword_subscriptions") + " · " : ui("keyword_subscriptions") + " \"" + keyword.toString() + "\" · ";
        }
        if (currentTotal == 0) {
            return prefix + ui("empty_articles");
        }
        int start = currentPage * currentPageSize() + 1;
        int end = Math.min(currentTotal, start + Math.max(total, 1) - 1);
        if (isEnglish()) {
            return prefix + "Page " + (currentPage + 1) + " / " + totalPages() + ", " + start + "-" + end + " / " + currentTotal + " articles, unread on this page " + unread;
        }
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

    private boolean isEnglish() {
        return "en".equals(appLanguage);
    }

    private DateFormat dateTimeFormat() {
        return DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT, isEnglish() ? Locale.US : Locale.CHINA);
    }

    private String displayLanguageName(String language) {
        if (language == null || language.trim().isEmpty()) {
            language = "中文";
        }
        String value = language.trim();
        if ("中文".equalsIgnoreCase(value) || "Chinese".equalsIgnoreCase(value)) {
            return isEnglish() ? "Chinese" : "中文";
        }
        if ("英文".equalsIgnoreCase(value) || "English".equalsIgnoreCase(value)) {
            return isEnglish() ? "English" : "英文";
        }
        return value;
    }

    private String normalizeLanguageInput(String language) {
        if (language == null || language.trim().isEmpty()) {
            return "中文";
        }
        String value = language.trim();
        if ("Chinese".equalsIgnoreCase(value) || "中文".equals(value)) {
            return "中文";
        }
        if ("英文".equals(value) || "English".equalsIgnoreCase(value)) {
            return "English";
        }
        return value;
    }

    private String displayChannelName(String name) {
        if ("OpenAI 官方".equals(name) || "OpenAI Official".equals(name)) {
            return aiProviderLabel("openai");
        }
        if ("Gemini 官方".equals(name) || "Gemini Official".equals(name)) {
            return aiProviderLabel("gemini");
        }
        if ("OpenAI 兼容".equals(name) || "OpenAI Compatible".equals(name)) {
            return aiProviderLabel("openai_compatible");
        }
        if ("AI 渠道".equals(name) || "AI Channel".equals(name)) {
            return ui("ai_channel");
        }
        return name;
    }

    private String localizeAiStage(String stage) {
        if (!isEnglish() || stage == null) {
            return stage;
        }
        if ("准备请求".equals(stage)) {
            return "Preparing request";
        }
        if ("发送请求".equals(stage)) {
            return "Sending request";
        }
        if ("等待 AI 响应".equals(stage)) {
            return "Waiting for AI response";
        }
        if ("读取响应".equals(stage)) {
            return "Reading response";
        }
        if ("解析响应".equals(stage)) {
            return "Parsing response";
        }
        if ("保存结果".equals(stage)) {
            return "Saving result";
        }
        return stage;
    }

    private String localizeError(Exception e) {
        String message = e == null ? "" : e.getMessage();
        if (message == null || message.trim().isEmpty() || !isEnglish()) {
            return message == null ? "" : message;
        }
        return message
                .replace("无法打开文件", "Cannot open file")
                .replace("无法打开输出文件", "Cannot open output file")
                .replace("翻译结果保存后无法从本地数据库读取", "Translation was saved but could not be read from the local database")
                .replace("没有拉取到模型", "No models were fetched")
                .replace("渠道名称不能为空", "Channel name is required")
                .replace("OpenAI 兼容渠道需要填写 Base URL", "OpenAI compatible channel requires Base URL")
                .replace("同步数据缺少 categories / feeds", "Sync data is missing categories / feeds")
                .replace("备份文件缺少 categories / feeds / articles", "Backup is missing categories / feeds / articles")
                .replace("翻译结果保存失败：文章不存在", "Failed to save translation: article does not exist")
                .replace("Gist ID 不能为空", "Gist ID is required")
                .replace("Gist 中没有找到文件：", "File not found in Gist: ")
                .replace("GitHub 请求失败", "GitHub request failed")
                .replace("拉取模型超时，请检查网络、代理或 API 地址。", "Fetching models timed out. Check network, proxy, or API URL.")
                .replace("AI 翻译网络超时，请检查网络/API 节点。", "AI translation timed out. Check network or API endpoint.")
                .replace("AI 请求失败", "AI request failed")
                .replace("服务器没有返回错误详情", "The server returned no error details")
                .replace("请填写火山方舟接入点 ID", "Enter Volcengine Ark endpoint ID");
    }

    private String ui(String key) {
        boolean en = isEnglish();
        switch (key) {
            case "nav_categories":
                return en ? "Categories" : "分类";
            case "open_category_menu":
                return en ? "Open category menu" : "打开分类菜单";
            case "add":
                return en ? "Add" : "添加";
            case "add_feed":
                return en ? "Add Feed" : "添加订阅";
            case "refresh":
                return en ? "Refresh" : "刷新";
            case "refresh_feeds":
                return en ? "Refresh feeds" : "刷新订阅";
            case "more":
                return en ? "More" : "更多";
            case "more_features":
                return en ? "More features" : "更多功能";
            case "search_hint":
                return en ? "Search title, content, or feed" : "搜索标题、内容或订阅源";
            case "search":
                return en ? "Search" : "搜索";
            case "unread":
                return en ? "Unread" : "未读";
            case "favorite":
                return en ? "Favorite" : "收藏";
            case "descending":
                return en ? "Desc" : "降序";
            case "mark_all_read":
                return en ? "Mark All Read" : "全部已读";
            case "sort_published":
                return en ? "Published" : "发布时间";
            case "sort_created":
                return en ? "Fetched" : "抓取时间";
            case "sort_title":
                return en ? "Title" : "标题";
            case "all_dates":
                return en ? "All Dates" : "全部日期";
            case "today":
                return en ? "Today" : "今天";
            case "yesterday":
                return en ? "Yesterday" : "昨天";
            case "last_7_days":
                return en ? "Last 7 Days" : "最近 7 天";
            case "previous_page":
                return en ? "Previous" : "上一页";
            case "next_page":
                return en ? "Next" : "下一页";
            case "stats":
                return en ? "Stats" : "统计";
            case "import_opml":
                return en ? "Import OPML" : "导入 OPML";
            case "export_opml":
                return en ? "Export OPML" : "导出 OPML";
            case "export_backup":
                return en ? "Export Backup" : "导出备份";
            case "restore_backup":
                return en ? "Restore Backup" : "恢复备份";
            case "category_management":
                return en ? "Category Management" : "分类管理";
            case "feed_management":
                return en ? "Feed Management" : "订阅管理";
            case "keyword_management":
                return en ? "Keyword Management" : "关键词管理";
            case "data_sync":
                return en ? "Data Sync" : "数据同步";
            case "translation_settings":
                return en ? "Translation Settings" : "翻译设置";
            case "ai_default_model":
                return en ? "AI Default Model" : "AI 默认模型";
            case "ai_channels":
                return en ? "AI Channels" : "AI 渠道管理";
            case "settings":
                return en ? "Settings" : "设置";
            case "loading_categories":
                return en ? "Loading categories..." : "正在加载分类...";
            case "close":
                return en ? "Close" : "关闭";
            case "all_articles":
                return en ? "All Articles" : "全部文章";
            case "category_all_articles":
                return en ? "All in Category" : "该分类全部文章";
            case "uncategorized_feeds":
                return en ? "Uncategorized Feeds" : "未分类订阅";
            case "keyword_subscriptions":
                return en ? "Keyword Subscriptions" : "关键词订阅";
            case "add_keyword_subscription":
                return en ? "Add Keyword Subscription" : "添加关键词订阅";
            case "manage_categories":
                return en ? "Manage Categories" : "管理分类";
            case "keywords":
                return en ? "Keywords" : "关键词";
            case "unnamed":
                return en ? "Unnamed" : "未命名";
            case "app_language":
                return en ? "App Language" : "界面语言";
            case "language_chinese":
                return en ? "Chinese" : "中文";
            case "language_english":
                return en ? "English" : "英文";
            case "default_sync_interval":
                return en ? "Default Sync Interval" : "新订阅默认同步间隔";
            case "page_size":
                return en ? "Articles Per Page" : "文章每页数量";
            case "default_translation_language":
                return en ? "Default Translation Language" : "默认翻译语言";
            case "enable_background_sync":
                return en ? "Enable Background Scheduled Sync" : "启用后台定时同步";
            case "exact_alarm_hint":
                return en ? "For more accurate sync timing, allow MRSS exact alarms in system settings and disable battery optimization." : "如需尽量准点同步，可在系统中允许 MRSS 使用精准闹钟，并关闭电池优化。";
            case "cancel":
                return en ? "Cancel" : "取消";
            case "system_permissions":
                return en ? "Permissions" : "系统权限";
            case "save":
                return en ? "Save" : "保存";
            case "settings_saved":
                return en ? "Settings saved" : "设置已保存";
            case "articles_per_page_suffix":
                return en ? " articles / page" : " 篇 / 页";
            case "minutes":
                return en ? "min" : "分钟";
            case "hours":
                return en ? "hours" : "小时";
            case "empty_articles":
                return en ? "No articles yet. Add or import feeds and MRSS will fetch and save them locally on this phone." : "暂无文章。添加或导入订阅后，MRSS 会在手机本地抓取和保存。";
            case "success_prefix":
                return en ? ": success " : "：成功 ";
            case "failed_prefix":
                return en ? ", failed " : "，失败 ";
            case "new_prefix":
                return en ? ", new " : "，新增 ";
            case "translated_prefix":
                return en ? ", translated " : "，翻译 ";
            case "articles_count_suffix":
                return en ? " articles" : " 篇";
            case "feeds_count_suffix":
                return en ? " feeds" : " 个订阅";
            case "items_count_suffix":
                return en ? " items" : " 项";
            case "models_count_suffix":
                return en ? " models" : " 个模型";
            case "auto_updated":
                return en ? "Auto updated: new " : "已自动更新：新增 ";
            case "auto_translation_done":
                return en ? "Auto translation complete" : "自动翻译完成";
            case "sync_done":
                return en ? "Sync complete" : "同步完成";
            case "open_category":
                return en ? "Open Category" : "打开分类";
            case "rename_category":
                return en ? "Rename Category" : "重命名分类";
            case "delete_category":
                return en ? "Delete Category" : "删除分类";
            case "open_feed":
                return en ? "Open Feed" : "打开订阅";
            case "edit_feed":
                return en ? "Edit Feed" : "编辑订阅";
            case "delete_feed":
                return en ? "Delete Feed" : "删除订阅";
            case "open_keyword":
                return en ? "Open Keyword" : "打开关键词";
            case "edit_keyword":
                return en ? "Edit Keyword" : "编辑关键词";
            case "delete_keyword":
                return en ? "Delete Keyword" : "删除关键词";
            case "keyword_name_hint":
                return en ? "Display name, e.g. Love" : "显示名称，如 爱情";
            case "name":
                return en ? "Name" : "名称";
            case "keyword_hint":
                return en ? "Keyword, e.g. Love" : "关键词，如 爱情";
            case "keyword":
                return en ? "Keyword" : "关键词";
            case "enable_keyword_subscription":
                return en ? "Enable keyword subscription" : "启用关键词订阅";
            case "new_keyword_subscription":
                return en ? "New Keyword Subscription" : "新增关键词订阅";
            case "edit_keyword_subscription":
                return en ? "Edit Keyword Subscription" : "编辑关键词订阅";
            case "enter_keyword":
                return en ? "Enter a keyword" : "请输入关键词";
            case "keyword_saved":
                return en ? "Keyword subscription saved" : "关键词订阅已保存";
            case "save_failed":
                return en ? "Save failed: " : "保存失败：";
            case "delete_keyword_subscription":
                return en ? "Delete Keyword Subscription" : "删除关键词订阅";
            case "delete_keyword_confirm_prefix":
                return en ? "Delete \"" : "删除“";
            case "delete_keyword_confirm_suffix":
                return en ? "\"? Articles will not be deleted." : "”？文章不会被删除。";
            case "delete":
                return en ? "Delete" : "删除";
            case "keyword_deleted":
                return en ? "Keyword subscription deleted" : "关键词订阅已删除";
            case "category":
                return en ? "Category" : "分类";
            case "sync_interval":
                return en ? "Sync Interval" : "同步间隔";
            case "auto_ai_translate":
                return en ? "Auto AI Translation" : "自动 AI 翻译";
            case "translation_mode":
                return en ? "Translation Mode" : "翻译方式";
            case "translation_off":
                return en ? "No Translation" : "不翻译";
            case "translation_ai":
                return en ? "AI Translation" : "AI 翻译";
            case "translation_standard":
                return en ? "Standard Translation" : "常规翻译";
            case "translate_to":
                return en ? "Translate To" : "翻译为";
            case "enter_full_url":
                return en ? "Enter a complete http/https URL" : "请输入完整的 http/https 地址";
            case "fetching_rss":
                return en ? "Fetching RSS..." : "正在抓取 RSS...";
            case "feed_added":
                return en ? "Feed added" : "订阅已添加";
            case "add_failed":
                return en ? "Add failed: " : "添加失败：";
            case "background_syncing":
                return en ? "Syncing in background. Local articles are shown first..." : "正在后台同步，已优先显示本地文章...";
            case "startup_sync_done":
                return en ? "Startup sync complete" : "启动同步完成";
            case "syncing_local_feeds":
                return en ? "Syncing local feeds..." : "正在同步本地订阅源...";
            case "no_feeds_to_refresh":
                return en ? "No feeds in the current scope can be refreshed. Add an RSS link first." : "当前范围没有可刷新的订阅，请先添加 RSS 链接。";
            case "refresh_done":
                return en ? "Refresh complete" : "刷新完成";
            case "auto_translate_skipped_no_model":
                return en ? "Auto translation skipped: set a default AI channel and model first" : "自动翻译未执行：请先设置默认 AI 渠道和模型";
            case "auto_ai_translating":
                return en ? "Auto AI translating pending articles..." : "正在自动 AI 翻译待处理文章...";
            case "all_categories":
                return en ? "All Categories" : "全部分类";
            case "keyword_articles":
                return en ? "Keyword Articles" : "关键词文章";
            case "ai_translate":
                return en ? "AI Translate" : "AI翻译";
            case "mark_unread":
                return en ? "Mark Unread" : "标为未读";
            case "unfavorite":
                return en ? "Unfavorite" : "取消收藏";
            case "share":
                return en ? "Share" : "分享";
            case "webpage":
                return en ? "Web" : "网页";
            case "original":
                return en ? "Original" : "原文";
            case "translation":
                return en ? "Translation" : "译文";
            case "marked_unread":
                return en ? "Marked as unread" : "已标为未读";
            case "select_default_ai_first":
                return en ? "Choose a default AI channel and model first" : "请先在 AI 翻译设置里选择默认渠道和模型";
            case "select_translation_mode_first":
                return en ? "Choose AI or standard translation in Translation Settings first" : "请先在翻译设置里选择 AI 或常规翻译";
            case "manual_ai_running":
                return en ? "Manual AI translation is already running" : "已有手动 AI 翻译正在进行";
            case "stage_prepare_request":
                return en ? "Preparing request" : "准备请求";
            case "stage_save_result":
                return en ? "Saving result" : "保存结果";
            case "stage_standard_translate":
                return en ? "Calling standard translation" : "正在调用常规翻译";
            case "translation_readback_failed":
                return en ? "Translation was saved but could not be read from the local database" : "翻译结果保存后无法从本地数据库读取";
            case "ai_translation_saved":
                return en ? "AI translation complete and saved locally. Time " : "AI 翻译完成，已保存到本地，用时 ";
            case "seconds_suffix":
                return en ? " sec" : " 秒";
            case "ai_translation_failed":
                return en ? "AI translation failed: " : "AI 翻译失败：";
            case "elapsed_prefix":
                return en ? " (time " : "（用时 ";
            case "seconds_body_prefix":
                return en ? " sec, body " : " 秒，正文 ";
            case "chars_suffix":
                return en ? " chars)" : " 字符）";
            case "manual_ai_progress":
                return en ? "AI translating: " : "正在 AI 翻译：";
            case "elapsed_time":
                return en ? "Elapsed " : "已用时 ";
            case "mrss_article":
                return en ? "MRSS Article" : "MRSS 文章";
            case "share_article":
                return en ? "Share Article" : "分享文章";
            case "marked_articles_prefix":
                return en ? "Marked " : "已标记 ";
            case "reading_subscriptions":
                return en ? "Reading subscriptions..." : "正在读取订阅列表...";
            case "imported_prefix":
                return en ? "Imported " : "已导入 ";
            case "import_failed":
                return en ? "Import failed: " : "导入失败：";
            case "writing_file":
                return en ? "Writing file..." : "正在写入文件...";
            case "cannot_open_output":
                return en ? "Cannot open output file" : "无法打开输出文件";
            case "opml_exported":
                return en ? "OPML exported" : "OPML 已导出";
            case "export_failed":
                return en ? "Export failed: " : "导出失败：";
            case "writing_backup":
                return en ? "Writing full backup..." : "正在写入完整备份...";
            case "backup_exported":
                return en ? "Backup exported" : "备份已导出";
            case "restore_backup_confirm":
                return en ? "Restore will overwrite local categories, feeds, and articles." : "恢复会覆盖当前本地分类、订阅和文章。";
            case "restore":
                return en ? "Restore" : "恢复";
            case "restoring_local_data":
                return en ? "Restoring local data..." : "正在恢复本地数据...";
            case "backup_restored":
                return en ? "Backup restored" : "备份已恢复";
            case "restore_failed":
                return en ? "Restore failed: " : "恢复失败：";
            case "none":
                return en ? "None" : "暂无";
            case "stats_categories":
                return en ? "Categories: " : "分类：";
            case "stats_feeds":
                return en ? "Feeds: " : "订阅：";
            case "stats_active_prefix":
                return en ? " (active " : "（启用 ";
            case "stats_active_suffix":
                return en ? ")" : "）";
            case "stats_articles":
                return en ? "Articles: " : "文章：";
            case "stats_unread":
                return en ? "Unread: " : "未读：";
            case "stats_favorites":
                return en ? "Favorites: " : "收藏：";
            case "stats_today":
                return en ? "New Today: " : "今天新增：";
            case "stats_last_7_days":
                return en ? "Last 7 Days: " : "最近 7 天：";
            case "stats_latest":
                return en ? "Latest Article: " : "最新文章：";
            case "local_stats":
                return en ? "Local Stats" : "本地统计";
            case "ok":
                return en ? "OK" : "确定";
            case "new_category":
                return en ? "New Category" : "新增分类";
            case "category_name":
                return en ? "Category Name" : "分类名称";
            case "edit_category":
                return en ? "Edit Category" : "编辑分类";
            case "category_name_required":
                return en ? "Category name is required" : "分类名称不能为空";
            case "delete_category_confirm":
                return en ? "Feeds in this category will not be deleted; they will become uncategorized." : "分类内订阅不会删除，只会变为未分类。";
            case "category_deleted":
                return en ? "Category deleted" : "分类已删除";
            case "no_feeds_yet":
                return en ? "No feeds yet" : "还没有订阅";
            case "disabled_suffix":
                return en ? " (disabled)" : "（停用）";
            case "title":
                return en ? "Title" : "标题";
            case "address":
                return en ? "Address" : "地址";
            case "enable_auto_sync":
                return en ? "Enable Auto Sync" : "启用自动同步";
            case "feed_saved":
                return en ? "Feed saved" : "订阅已保存";
            case "delete_feed_confirm":
                return en ? "Local articles under this feed will also be deleted." : "会同时删除该订阅下的本地文章。";
            case "feed_deleted":
                return en ? "Feed deleted" : "订阅已删除";
            case "github_token_hint":
                return en ? "GitHub Token (gist permission required)" : "GitHub 令牌（需要 gist 权限）";
            case "github_token_label":
                return en ? "GitHub Token" : "GitHub 令牌";
            case "gist_id_label":
                return en ? "Gist ID" : "Gist 标识";
            case "gist_id_hint":
                return en ? "Leave empty for first upload; it will be saved after upload" : "首次上传可留空，上传后会自动保存";
            case "filename":
                return en ? "Filename" : "文件名";
            case "data_sync_hint":
                return en ? "Data sync uploads only categories and feed sources, not locally saved articles. Use it to share subscriptions between desktop and phone." : "数据同步只上传分类和订阅源，不上传已保存文章。适合电脑端和手机端共享订阅配置。";
            case "download_merge":
                return en ? "Download & Merge" : "下载合并";
            case "upload":
                return en ? "Upload" : "上传";
            case "gist_id_required_for_download":
                return en ? "Gist ID is required for download" : "下载需要填写 Gist 标识";
            case "github_token_required":
                return en ? "Enter GitHub Token" : "请填写 GitHub 令牌";
            case "filename_required":
                return en ? "Enter filename" : "请填写文件名";
            case "uploading_subscriptions":
                return en ? "Uploading categories and feed sources..." : "正在上传分类和订阅源...";
            case "uploaded_to_gist":
                return en ? "Uploaded to GitHub Gist: " : "已上传到 GitHub Gist：";
            case "upload_failed":
                return en ? "Upload failed: " : "上传失败：";
            case "downloading_merging":
                return en ? "Downloading and merging subscriptions..." : "正在下载并合并订阅...";
            case "merged_sync_data":
                return en ? "Merged sync data: " : "已合并同步数据：";
            case "download_failed":
                return en ? "Download failed: " : "下载失败：";
            case "current_default":
                return en ? "Current Default" : "当前默认";
            case "set_default_model":
                return en ? "Set Default Model" : "设置默认模型";
            case "no_channels_add_first":
                return en ? "No channels. Add one first." : "暂无渠道，请先新增";
            case "default_channel":
                return en ? "Default Channel" : "默认渠道";
            case "fetch_models_first":
                return en ? "Fetch models in channel management first" : "请先在渠道管理中拉取模型";
            case "default_model":
                return en ? "Default Model" : "默认模型";
            case "custom_model":
                return en ? "Custom Model" : "自定义模型";
            case "custom_model_hint":
                return en ? "Enter model name or Doubao endpoint ID manually" : "可手动填写模型名或豆包接入点标识";
            case "save_default":
                return en ? "Save Default" : "保存默认";
            case "default_channel_not_set":
                return en ? "Default channel: not set" : "默认渠道：未设置";
            case "default_model_not_set":
                return en ? "Default model: not set" : "默认模型：未设置";
            case "default_translation_language_summary":
                return en ? "Default translation language: " : "默认翻译语言：";
            case "add_channel_first":
                return en ? "Add a channel first" : "请先新增渠道";
            case "default_channel_summary":
                return en ? "Default channel: " : "默认渠道：";
            case "default_model_summary":
                return en ? "Default model: " : "默认模型：";
            case "not_selected":
                return en ? "Not selected" : "未选择";
            case "channel_models_not_fetched":
                return en ? "Models not fetched. Fetch them in channel management." : "该渠道未拉取模型，请到渠道管理拉取";
            case "channel_management":
                return en ? "Channel Management" : "渠道管理";
            case "add_ai_channel_first":
                return en ? "Add an AI channel first" : "请先新增 AI 渠道";
            case "choose_or_enter_default_model":
                return en ? "Choose or enter a default model" : "请填写或选择默认模型";
            case "select_model_first":
                return en ? "Select a model first" : "请先选择模型";
            case "default_model_saved":
                return en ? "Default model saved" : "默认模型已保存";
            case "ai_channel_hint":
                return en ? "OpenAI, Gemini, Qwen, Doubao, DeepSeek, Kimi, and Zhipu have built-in addresses. Enter only the API Key. For third-party gateways, choose OpenAI Compatible and enter Base URL." : "OpenAI、Gemini、千问、豆包、DeepSeek、Kimi、智谱已内置地址，只需要填写 API 密钥。第三方中转站请选择 OpenAI 兼容并填写基础地址。";
            case "new_channel":
                return en ? "New Channel" : "新增渠道";
            case "ai_channel":
                return en ? "AI Channel" : "AI 渠道";
            case "model_not_selected":
                return en ? "No model selected" : "未选择模型";
            case "default":
                return en ? "Default" : "默认";
            case "channel_name":
                return en ? "Channel Name" : "渠道名称";
            case "type":
                return en ? "Type" : "类型";
            case "base_url":
                return en ? "Base URL" : "基础地址";
            case "api_key":
                return en ? "API Key" : "API 密钥";
            case "fetch_save_models":
                return en ? "Fetch and Save Models" : "拉取并保存模型";
            case "new_ai_channel":
                return en ? "New AI Channel" : "新增 AI 渠道";
            case "edit_ai_channel":
                return en ? "Edit AI Channel" : "编辑 AI 渠道";
            case "hint_gemini":
                return en ? "Gemini official channel uses Google's official address. Enter Gemini API Key, then fetch models." : "Gemini 官方渠道使用 Google 官方地址，只需要填写 Gemini API 密钥，然后拉取模型。";
            case "hint_qwen":
                return en ? "Qwen uses Alibaba Cloud DashScope OpenAI-compatible address. Enter DashScope API Key." : "通义千问使用阿里云 DashScope OpenAI 兼容地址，只需要填写 DashScope API 密钥。";
            case "hint_doubao":
                return en ? "Doubao uses Volcengine Ark OpenAI-compatible address. The model is usually the endpoint ID created in Ark console." : "豆包使用火山方舟 OpenAI 兼容地址。模型通常是方舟控制台创建的接入点标识。";
            case "hint_deepseek":
                return en ? "DeepSeek official channel has a built-in API address. Enter DeepSeek API Key." : "DeepSeek 官方渠道已内置 API 地址，只需要填写 DeepSeek API 密钥。";
            case "hint_kimi":
                return en ? "Kimi uses Moonshot official OpenAI-compatible address. Enter Moonshot API Key." : "Kimi 使用 Moonshot 官方 OpenAI 兼容地址，只需要填写 Moonshot API 密钥。";
            case "hint_zhipu":
                return en ? "Zhipu uses BigModel official OpenAI-compatible address. Enter Zhipu API Key." : "智谱使用 BigModel 官方 OpenAI 兼容地址，只需要填写智谱 API 密钥。";
            case "hint_openai_compatible":
                return en ? "OpenAI Compatible is for third-party gateways. Enter the full Base URL, e.g. https://example.com/v1." : "OpenAI 兼容渠道用于第三方中转站，填写完整基础地址，例如 https://example.com/v1。";
            case "hint_openai":
                return en ? "OpenAI official channel has built-in https://api.openai.com/v1. Enter OpenAI API Key, then fetch models." : "OpenAI 官方渠道内置 https://api.openai.com/v1，只需要填写 OpenAI API 密钥，然后拉取模型。";
            case "cached_models":
                return en ? "Cached models: " : "已缓存模型：";
            case "current_default_model":
                return en ? "Current default: " : "当前默认：";
            case "channel_name_required":
                return en ? "Channel name is required" : "渠道名称不能为空";
            case "api_key_required":
                return en ? "Enter API Key first" : "请先填写 API 密钥";
            case "base_url_required":
                return en ? "OpenAI compatible channel requires Base URL" : "OpenAI 兼容渠道需要填写基础地址";
            case "ai_settings_saved":
                return en ? "AI settings saved" : "AI 设置已保存";
            case "channel_deleted":
                return en ? "Channel deleted" : "渠道已删除";
            case "fetching_models":
                return en ? "Fetching models..." : "正在拉取模型...";
            case "no_models_fetched":
                return en ? "No models were fetched" : "没有拉取到模型";
            case "models_fetched_saved_prefix":
                return en ? "Fetched and saved " : "已拉取并保存 ";
            case "fetch_failed":
                return en ? "Fetch failed: " : "拉取失败：";
            case "cannot_open_system_settings":
                return en ? "Cannot open system settings" : "无法打开系统设置";
            case "uncategorized":
                return en ? "Uncategorized" : "未分类";
            case "cannot_open_file":
                return en ? "Cannot open file" : "无法打开文件";
            case "default_translation_mode":
                return en ? "Default Translation Mode" : "默认翻译方式";
            case "standard_provider":
                return en ? "Standard Translation Provider" : "常规翻译平台";
            case "provider_microsoft":
                return en ? "Microsoft Translator" : "微软翻译";
            case "provider_google":
                return en ? "Google Translate" : "谷歌翻译";
            case "provider_baidu":
                return en ? "Baidu Translate" : "百度翻译";
            case "provider_tencent":
                return en ? "Tencent Translate" : "腾讯翻译";
            case "baidu_app_id":
                return en ? "Baidu App ID" : "百度 App ID";
            case "baidu_secret":
                return en ? "Baidu Secret Key" : "百度密钥";
            case "tencent_secret_id":
                return en ? "Tencent SecretId" : "腾讯云 SecretId";
            case "tencent_secret_key":
                return en ? "Tencent SecretKey" : "腾讯云 SecretKey";
            case "tencent_region":
                return en ? "Tencent Region" : "腾讯云地域";
            case "google_api_key":
                return en ? "Google API Key" : "Google API 密钥";
            case "microsoft_key":
                return en ? "Microsoft Key" : "微软翻译 Key";
            case "microsoft_region":
                return en ? "Microsoft Region (global if empty)" : "微软区域（全局可填 global）";
            case "standard_translation_hint":
                return en ? "Standard translation is faster than AI. It translates text nodes and keeps HTML tags, links, line breaks, and article structure in place as much as possible." : "常规翻译速度通常比 AI 更快。MRSS 会尽量只翻译文本节点，保留 HTML 标签、链接、换行和文章结构。";
            case "translation_settings_saved":
                return en ? "Translation settings saved" : "翻译设置已保存";
            default:
                return key;
        }
    }
}
