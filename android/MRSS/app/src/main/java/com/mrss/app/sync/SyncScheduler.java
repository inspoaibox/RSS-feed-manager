package com.mrss.app.sync;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import com.mrss.app.data.FeedRepository;

public final class SyncScheduler {
    private static final long MIN_DELAY_MS = 60 * 1000L;
    private static final long FALLBACK_INTERVAL_MS = 15 * 60 * 1000L;

    private SyncScheduler() {
    }

    public static void schedule(Context context) {
        long now = System.currentTimeMillis();
        long nextDueAt = new FeedRepository(context).getNextDueAt(now);
        schedule(context, nextDueAt > 0 ? nextDueAt : now + FALLBACK_INTERVAL_MS);
    }

    public static void schedule(Context context, long requestedTriggerAt) {
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        PendingIntent pendingIntent = pendingIntent(context);
        long triggerAt = Math.max(requestedTriggerAt, System.currentTimeMillis() + MIN_DELAY_MS);
        if (alarmManager == null) {
            return;
        }
        if (canUseExactAlarms(alarmManager)) {
            alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
        } else {
            alarmManager.set(AlarmManager.RTC_WAKEUP, triggerAt, pendingIntent);
        }
    }

    public static void cancel(Context context) {
        AlarmManager alarmManager = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarmManager != null) {
            alarmManager.cancel(pendingIntent(context));
        }
    }

    private static PendingIntent pendingIntent(Context context) {
        Intent intent = new Intent(context, SyncReceiver.class);
        intent.setAction(SyncReceiver.ACTION_SYNC_FEEDS);
        return PendingIntent.getBroadcast(
                context,
                1001,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }

    private static boolean canUseExactAlarms(AlarmManager alarmManager) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return alarmManager.canScheduleExactAlarms();
        }
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.M;
    }
}
