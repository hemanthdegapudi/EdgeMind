#!/bin/bash
export ANDROID_HOME=/home/tilaksijju/Documents/EdgeMind/.toolchain/android-sdk
export PATH=$ANDROID_HOME/platform-tools:$PATH
adb shell pm install -r -t -g /data/local/tmp/app.apk > install.log 2>&1 &
for i in {1..10}; do
  sleep 1
  adb shell input tap 750 2000
done
wait
cat install.log
