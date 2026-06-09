package com.mrss.mobile.sync;

import android.content.Context;

import com.mrss.mobile.api.ServerApi;
import com.mrss.mobile.data.AppSettings;
import com.mrss.mobile.data.MobileRepository;
import com.mrss.mobile.model.PendingAction;
import com.mrss.mobile.model.SyncResult;

import java.util.List;

public final class SyncEngine {
    private static final int PAGE_SIZE = 200;

    private SyncEngine() {
    }

    public static Result sync(Context context, boolean fullRefresh) throws Exception {
        Context appContext = context.getApplicationContext();
        AppSettings settings = new AppSettings(appContext);
        if (!settings.isLoggedIn()) {
            throw new IllegalStateException("请先登录");
        }

        MobileRepository repository = new MobileRepository(appContext);
        ServerApi api = new ServerApi(settings);

        List<PendingAction> pendingActions = repository.getPendingActions(100);
        if (!pendingActions.isEmpty()) {
            api.uploadActions(pendingActions);
            repository.deletePendingActions(pendingActions);
        }

        if (fullRefresh) {
            repository.clearCachedContent();
        }

        String since = fullRefresh ? "" : settings.getLastSyncAt();
        int offset = 0;
        int totalArticles = 0;
        int pageCount = 0;
        String serverTime = null;
        boolean replaceMetadata = true;

        while (true) {
            SyncResult result = api.sync(since, offset, PAGE_SIZE);
            repository.applySyncResult(result, replaceMetadata);
            replaceMetadata = false;
            pageCount++;
            totalArticles += result.articles.size();
            if (result.serverTime != null && !result.serverTime.trim().isEmpty()) {
                serverTime = result.serverTime;
            }
            if (!result.hasMore || result.nextOffset == null) {
                break;
            }
            offset = result.nextOffset;
        }

        if (serverTime != null) {
            settings.setLastSyncAt(serverTime);
        }
        SyncScheduler.schedule(appContext);
        return new Result(totalArticles, pendingActions.size(), pageCount, serverTime);
    }

    public static final class Result {
        public final int articles;
        public final int uploadedActions;
        public final int pages;
        public final String serverTime;

        Result(int articles, int uploadedActions, int pages, String serverTime) {
            this.articles = articles;
            this.uploadedActions = uploadedActions;
            this.pages = pages;
            this.serverTime = serverTime;
        }
    }
}
