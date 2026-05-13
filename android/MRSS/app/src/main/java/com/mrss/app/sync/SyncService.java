package com.mrss.app.sync;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import com.mrss.app.MainActivity;
import com.mrss.app.R;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SyncService extends Service {
    private static final String CHANNEL_ID = "mrss_sync";
    private static final int RUNNING_NOTIFICATION_ID = 3000;
    private static final int RESULT_NOTIFICATION_ID = 3001;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private boolean running = false;

    public static void start(Context context) {
        Intent intent = new Intent(context, SyncService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(RUNNING_NOTIFICATION_ID, buildNotification("MRSS 正在同步", "正在检查到期订阅源...", false));
        if (running) {
            return START_NOT_STICKY;
        }
        running = true;
        executor.execute(() -> {
            try {
                syncDueFeeds();
            } finally {
                running = false;
                stopForeground(true);
                stopSelf(startId);
            }
        });
        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void syncDueFeeds() {
        SyncEngine.Result result = SyncEngine.syncDueFeeds(this);
        if (result.totalNew > 0) {
            showResultNotification(
                    "MRSS 有新文章",
                    "新增 " + result.totalNew + " 篇，已翻译 " + result.translated + " 篇"
            );
        } else if (result.translated > 0 || result.translationFailed > 0) {
            showResultNotification("MRSS 自动翻译完成", "成功 " + result.translated + " 篇，失败 " + result.translationFailed + " 篇");
        } else if (result.failed > 0) {
            showResultNotification("MRSS 同步完成", "成功 " + result.success + " 个，失败 " + result.failed + " 个");
        }
    }

    private android.app.Notification buildNotification(String title, String text, boolean autoCancel) {
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                2001,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        android.app.Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new android.app.Notification.Builder(this, CHANNEL_ID)
                : new android.app.Notification.Builder(this);
        return builder.setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(text)
                .setContentIntent(pendingIntent)
                .setAutoCancel(autoCancel)
                .build();
    }

    private void showResultNotification(String title, String text) {
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(RESULT_NOTIFICATION_ID, buildNotification(title, text, true));
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager == null) {
                return;
            }
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "MRSS 同步",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("订阅源后台同步状态和结果");
            manager.createNotificationChannel(channel);
        }
    }
}
