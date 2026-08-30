#!/bin/bash
export JAVA_HOME=$(pwd)/.toolchain/jdk-17.0.2
export PATH=$JAVA_HOME/bin:$PATH
cd edgemind-app && ./gradlew assembleDebug && cd ..
adb push edgemind-app/app/build/outputs/apk/debug/app-debug.apk /data/local/tmp/app.apk
adb shell pm install -r -t -g /data/local/tmp/app.apk
adb shell appops set com.edgemind.app MANAGE_EXTERNAL_STORAGE allow
adb shell pm grant com.edgemind.app android.permission.READ_EXTERNAL_STORAGE
adb logcat -c
adb shell am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService
echo "Waiting for model load..."
sleep 15
echo "Sending to background (HOME)..."
adb shell input keyevent 3
sleep 8
echo "Turning screen off (POWER)..."
adb shell input keyevent 26
sleep 10
echo "Waking up..."
adb shell input keyevent 224
sleep 1
adb shell input keyevent 82
sleep 5
adb logcat -d | grep -iE "P10.4|token:|Run [0-9]+ completed" > phase10.4_test2.log
echo "Done."
