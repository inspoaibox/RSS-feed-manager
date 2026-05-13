package com.mrss.app.sync;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SyncJobService extends JobService {
    private static final int JOB_ID = 4001;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    public static void scheduleNow(Context context) {
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler == null) {
            return;
        }
        JobInfo jobInfo = new JobInfo.Builder(JOB_ID, new ComponentName(context, SyncJobService.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setMinimumLatency(0)
                .setOverrideDeadline(60 * 1000L)
                .build();
        scheduler.schedule(jobInfo);
    }

    @Override
    public boolean onStartJob(JobParameters params) {
        executor.execute(() -> {
            SyncEngine.syncDueFeeds(this);
            jobFinished(params, false);
        });
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return true;
    }

    @Override
    public void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
