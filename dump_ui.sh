#!/bin/bash
export ANDROID_HOME=/home/tilaksijju/Documents/EdgeMind/.toolchain/android-sdk
export PATH=$ANDROID_HOME/platform-tools:$PATH
adb shell pm install -r -t -g /data/local/tmp/app.apk &
sleep 2
adb shell uiautomator dump /data/local/tmp/uidump.xml
adb pull /data/local/tmp/uidump.xml .
cat uidump.xml
wait
