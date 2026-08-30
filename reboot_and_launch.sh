#!/bin/bash
export ANDROID_HOME=/home/tilaksijju/Documents/EdgeMind/.toolchain/android-sdk
export PATH=$ANDROID_HOME/platform-tools:$PATH
adb reboot
adb wait-for-device
while true; do
  BOOT=$(adb shell getprop sys.boot_completed | tr -d '\r')
  if [ "$BOOT" = "1" ]; then
    break
  fi
  sleep 0.5
done
adb logcat -c
for i in {1..30}; do
  adb shell am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService > /dev/null 2>&1
  sleep 1
done
adb logcat -d | grep -i MemoryGuard
