package com.mrss.app.sync;

import android.content.Context;
import android.content.Intent;

import com.mrss.app.data.AppSettings;
import com.mrss.app.data.FeedRepository;
import com.mrss.app.model.AiChannel;
import com.mrss.app.model.ArticleTranslation;
import com.mrss.app.model.Feed;
import com.mrss.app.model.ParsedFeed;
import com.mrss.app.model.StandardTranslationSettings;
import com.mrss.app.model.TranslationJob;
import com.mrss.app.network.AiClient;
import com.mrss.app.network.FeedParser;
import com.mrss.app.network.StandardTranslationClient;

import java.util.List;

public final class SyncEngine {
    public static final String ACTION_SYNC_COMPLETED = "com.mrss.app.SYNC_COMPLETED";
    public static final String EXTRA_TOTAL_NEW = "total_new";
    public static final String EXTRA_SUCCESS = "success";
    public static final String EXTRA_FAILED = "failed";
    public static final String EXTRA_CANDIDATES = "candidates";
    public static final String EXTRA_TRANSLATED = "translated";
    public static final String EXTRA_TRANSLATION_FAILED = "translation_failed";

    private SyncEngine() {
    }

    public static Result syncDueFeeds(Context context) {
        Context appContext = context.getApplicationContext();
        AppSettings settings = new AppSettings(appContext);
        if (!settings.isBackgroundSyncEnabled()) {
            SyncScheduler.cancel(appContext);
            return new Result(0, 0, 0, 0, 0, 0);
        }

        FeedRepository repository = new FeedRepository(appContext);
        FeedParser parser = new FeedParser();
        List<Feed> feeds = repository.getDueFeeds(System.currentTimeMillis());
        int totalNew = 0;
        int success = 0;
        int failed = 0;
        int candidates = feeds.size();
        for (Feed feed : feeds) {
            try {
                ParsedFeed parsedFeed = parser.fetchAndParse(feed.url);
                totalNew += repository.refreshFeed(feed, parsedFeed);
                success++;
            } catch (Exception e) {
                repository.markFeedError(feed.id, e.getMessage());
                failed++;
            }
        }

        TranslationResult translation = translatePending(repository, settings);

        long nextDueAt = repository.getNextDueAt(System.currentTimeMillis());
        if (nextDueAt > 0) {
            SyncScheduler.schedule(appContext, nextDueAt);
        } else {
            SyncScheduler.cancel(appContext);
        }
        Result result = new Result(totalNew, success, failed, candidates, translation.translated, translation.failed);
        settings.markSyncCompleted(result.totalNew, result.success, result.failed, result.candidates);
        sendSyncCompletedBroadcast(appContext, result);
        return result;
    }

    private static TranslationResult translatePending(FeedRepository repository, AppSettings settings) {
        TranslationResult ai = translateAiPending(repository);
        TranslationResult standard = translateStandardPending(repository, settings);
        return new TranslationResult(ai.translated + standard.translated, ai.failed + standard.failed);
    }

    private static TranslationResult translateAiPending(FeedRepository repository) {
        AiChannel channel = repository.getDefaultAiChannel();
        if (channel == null || channel.apiKey == null || channel.apiKey.trim().isEmpty() || channel.model == null || channel.model.trim().isEmpty()) {
            return new TranslationResult(0, 0);
        }
        return translateJobs(repository, "ai", 5, job -> new AiClient().translate(channel, job));
    }

    private static TranslationResult translateStandardPending(FeedRepository repository, AppSettings settings) {
        StandardTranslationSettings translationSettings = standardSettings(settings);
        return translateJobs(repository, "standard", 8, job -> new StandardTranslationClient().translate(translationSettings, job));
    }

    private static TranslationResult translateJobs(FeedRepository repository, String mode, int batchSize, Translator translator) {
        if (repository.countPendingTranslationJobs(mode) <= 0) {
            return new TranslationResult(0, 0);
        }
        int translated = 0;
        int failed = 0;
        while (true) {
            List<TranslationJob> jobs = repository.pendingTranslationJobs(mode, batchSize);
            if (jobs.isEmpty()) {
                return new TranslationResult(translated, failed);
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

    private static StandardTranslationSettings standardSettings(AppSettings settings) {
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

    private static void sendSyncCompletedBroadcast(Context context, Result result) {
        Intent intent = new Intent(ACTION_SYNC_COMPLETED);
        intent.setPackage(context.getPackageName());
        intent.putExtra(EXTRA_TOTAL_NEW, result.totalNew);
        intent.putExtra(EXTRA_SUCCESS, result.success);
        intent.putExtra(EXTRA_FAILED, result.failed);
        intent.putExtra(EXTRA_CANDIDATES, result.candidates);
        intent.putExtra(EXTRA_TRANSLATED, result.translated);
        intent.putExtra(EXTRA_TRANSLATION_FAILED, result.translationFailed);
        context.sendBroadcast(intent);
    }

    public static final class Result {
        public final int totalNew;
        public final int success;
        public final int failed;
        public final int candidates;
        public final int translated;
        public final int translationFailed;

        private Result(int totalNew, int success, int failed, int candidates, int translated, int translationFailed) {
            this.totalNew = totalNew;
            this.success = success;
            this.failed = failed;
            this.candidates = candidates;
            this.translated = translated;
            this.translationFailed = translationFailed;
        }
    }

    private static final class TranslationResult {
        final int translated;
        final int failed;

        TranslationResult(int translated, int failed) {
            this.translated = translated;
            this.failed = failed;
        }
    }

    private interface Translator {
        ArticleTranslation translate(TranslationJob job) throws Exception;
    }
}
