package com.mrss.mobile.sync;

import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.os.Build;

public final class SyncScheduler {
    private static final int JOB_ID = 73041;
    private static final long PERIOD_MS = 15L * 60L * 1000L;

    private SyncScheduler() {
    }

    public static void schedule(Context context) {
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler == null) {
            return;
        }
        ComponentName component = new ComponentName(context, SyncJobService.class);
        JobInfo.Builder builder = new JobInfo.Builder(JOB_ID, component)
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            builder.setPeriodic(PERIOD_MS, 5L * 60L * 1000L);
        } else {
            builder.setPeriodic(PERIOD_MS);
        }
        scheduler.schedule(builder.build());
    }

    public static void cancel(Context context) {
        JobScheduler scheduler = (JobScheduler) context.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (scheduler != null) {
            scheduler.cancel(JOB_ID);
        }
    }
}
