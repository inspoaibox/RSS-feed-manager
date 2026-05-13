package com.mrss.app.sync;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.mrss.app.data.AppSettings;

public class SyncReceiver extends BroadcastReceiver {
    public static final String ACTION_SYNC_FEEDS = "com.mrss.app.SYNC_FEEDS";

    @Override
    public void onReceive(Context context, Intent intent) {
        Context appContext = context.getApplicationContext();
        AppSettings settings = new AppSettings(appContext);
        if (!settings.isBackgroundSyncEnabled()) {
            SyncScheduler.cancel(appContext);
            return;
        }
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            SyncScheduler.schedule(appContext);
            return;
        }
        try {
            SyncService.start(appContext);
        } catch (RuntimeException e) {
            SyncJobService.scheduleNow(appContext);
        }
    }
}
