#!/bin/bash
export ANDROID_HOME=/home/tilaksijju/Documents/EdgeMind/.toolchain/android-sdk
export PATH=$ANDROID_HOME/platform-tools:$PATH
adb shell input keyevent 224
sleep 1
adb shell input swipe 500 2000 500 500
sleep 1
adb shell input keyevent 82
sleep 1
adb shell pm install -r -t -g /data/local/tmp/app.apk > install.log 2>&1 &
for i in {1..20}; do
  sleep 0.5
  adb shell uiautomator dump /data/local/tmp/uidump.xml >/dev/null 2>&1
  adb shell cat /data/local/tmp/uidump.xml | grep -i "install" >/dev/null 2>&1
  adb shell input tap 750 2050
  adb shell input tap 750 2150
  adb shell input tap 750 1950
done
wait
cat install.log
