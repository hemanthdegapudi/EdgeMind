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
for i in {1..10}; do
  for x in 700 800 900; do
    for y in 2000 2050 2100 2150 2200 2250; do
      adb shell input tap $x $y
    done
  done
  sleep 1
done
wait
cat install.log
