#!/bin/bash
export ANDROID_HOME=/home/tilaksijju/Documents/EdgeMind/.toolchain/android-sdk
export PATH=$ANDROID_HOME/platform-tools:$PATH
adb logcat -c
adb reboot
adb wait-for-device
while [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" != "1" ]; do
  sleep 0.5
done
adb logcat -c
echo "Boot completed. Starting observation window..."
# Loop for 45 seconds to get a solid window of measurements
for i in {1..45}; do
  adb shell am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService > /dev/null 2>&1
  sleep 1
done
echo "Observation window finished. Collecting logs."
adb logcat -d | grep -i "Memory refresh" > trackA_mem.log
cat trackA_mem.log
