package com.mrss.mobile.sync;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import com.mrss.mobile.data.AppSettings;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            AppSettings settings = new AppSettings(context);
            if (settings.isLoggedIn()) {
                SyncScheduler.schedule(context);
            }
        }
    }
}
