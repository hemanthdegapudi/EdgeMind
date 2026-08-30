#!/bin/bash
adb shell pm install -t -g /data/local/tmp/app.apk &
PID=$!
sleep 1
for i in {1..10}; do
  adb shell uiautomator dump /data/local/tmp/uidump.xml
  adb shell cat /data/local/tmp/uidump.xml | grep -i "install" || true
  # Just send a bunch of TABs and ENTER to hopefully click install, or find coords
  # In MIUI, the "Install" button might have a timer.
  # Let's try to parse bounds and tap. Or just tap the bottom right area.
  sleep 1
done
wait $PID
