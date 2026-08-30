#!/bin/bash
export ANDROID_HOME=/home/tilaksijju/Documents/EdgeMind/.toolchain/android-sdk
export PATH=$ANDROID_HOME/platform-tools:$PATH
adb shell pm install -r -t -g /data/local/tmp/app.apk > install.log 2>&1 &
for i in {1..15}; do
  sleep 0.5
  adb shell input keyevent 61  # TAB
  adb shell input keyevent 66  # ENTER
  adb shell input tap 800 2150 # Another possible coordinate for "Install"
done
wait
cat install.log
