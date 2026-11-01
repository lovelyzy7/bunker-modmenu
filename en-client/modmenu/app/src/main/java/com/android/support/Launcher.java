package com.android.support;

import android.app.Activity;
import android.app.ActivityManager;
import android.app.Application;
import android.app.Service;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.view.View;

public class Launcher extends Service {

    Menu menu;
    private Handler handler;
    private final Runnable ticker = new Runnable() {
        public void run() {
            Thread();
            handler.postDelayed(this, 1000);
        }
    };
    // 息屏/切软件回来后按钮消失的修复（一）：拿到 Activity 恢复事件就立即重挂/显示，
    // 不再只靠 1 秒轮询的进程重要性推断。
    private boolean activityVisible;
    private Application.ActivityLifecycleCallbacks lifecycle;

    //When this Class is called the code in this function will be executed
    @Override
    public void onCreate() {
        super.onCreate();

        startMenu();

        //Create a handler for this Class
        handler = new Handler();
        handler.post(ticker);

        lifecycle = new Application.ActivityLifecycleCallbacks() {
            @Override
            public void onActivityCreated(Activity activity, Bundle savedInstanceState) {
            }

            @Override
            public void onActivityStarted(Activity activity) {
            }

            @Override
            public void onActivityResumed(Activity activity) {
                activityVisible = true;
                if (menu != null) menu.show();
            }

            @Override
            public void onActivityPaused(Activity activity) {
                activityVisible = false;
            }

            @Override
            public void onActivityStopped(Activity activity) {
            }

            @Override
            public void onActivitySaveInstanceState(Activity activity, Bundle outState) {
            }

            @Override
            public void onActivityDestroyed(Activity activity) {
            }
        };
        getApplication().registerActivityLifecycleCallbacks(lifecycle);
    }

    /** 挂浮窗 + 构建功能列表。服务被系统回收重建时也要能整套重来。 */
    private void startMenu() {
        menu = new Menu(this);
        menu.SetWindowManagerWindowService();
        menu.ShowMenu();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    //Check if we are still in the game. If now our menu and menu button will dissapear
    private boolean isNotInGame() {
        // 修复（二）：原来要求 importance 恰好 == 100（FOREGROUND）才算“在游戏里”。
        // 真机上息屏/切回来后进程常报 125（前台服务）/130（可见）等值，菜单会被一直
        // 判为“不在游戏”而隐藏——按钮就此消失。只要还在屏幕上（<= VISIBLE）就不隐藏。
        if (activityVisible) return false;
        ActivityManager.RunningAppProcessInfo runningAppProcessInfo = new ActivityManager.RunningAppProcessInfo();
        ActivityManager.getMyMemoryState(runningAppProcessInfo);
        return runningAppProcessInfo.importance > ActivityManager.RunningAppProcessInfo.IMPORTANCE_VISIBLE;
    }

    private void Thread() {
        if (menu == null) return;
        if (isNotInGame()) {
            menu.setVisibility(View.INVISIBLE);
        } else {
            // 修复（三）：显示时顺带把浮窗挂回 WindowManager（被系统/生命周期摘掉后自愈）
            // 并强制重绘，避免“可见性改回来了但窗口不重绘”的假恢复。
            menu.show();
        }
    }

    //Destroy our View
    public void onDestroy() {
        super.onDestroy();
        if (handler != null) handler.removeCallbacks(ticker);
        if (lifecycle != null) {
            getApplication().unregisterActivityLifecycleCallbacks(lifecycle);
            lifecycle = null;
        }
        menu.onDestroy();
    }

    //Same as above so it wont crash in the background and therefore use alot of Battery life
    public void onTaskRemoved(Intent intent) {
        super.onTaskRemoved(intent);
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
        stopSelf();
    }

    //Override our Start Command so the Service doesnt try to recreate itself when the App is closed
    // 修复（四）：服务被系统低内存回收后不再彻底消失（START_STICKY 重建时 onCreate 整套重来）。
    public int onStartCommand(Intent intent, int i, int i2) {
        return Service.START_STICKY;
    }
}
