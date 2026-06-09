package com.mrss.mobile.sync;

import android.app.job.JobParameters;
import android.app.job.JobService;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SyncJobService extends JobService {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    public boolean onStartJob(JobParameters params) {
        executor.execute(() -> {
            boolean needsReschedule = false;
            try {
                SyncEngine.sync(this, false);
            } catch (Exception e) {
                needsReschedule = true;
            }
            jobFinished(params, needsReschedule);
        });
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return true;
    }
}
