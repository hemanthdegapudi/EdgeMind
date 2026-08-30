#!/bin/bash
adb shell pm install -r -t -g /data/local/tmp/app.apk > install.log 2>&1 &
for i in {1..20}; do
  sleep 1
  adb shell input tap 750 2000
  adb shell input tap 750 2100
  adb shell input tap 540 2100
done
wait
cat install.log
