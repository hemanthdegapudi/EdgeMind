#!/bin/bash
echo "=== STEP 0.1 ==="
adb devices
echo "=== STEP 0.2 ==="
adb shell getprop ro.product.model
adb shell getprop ro.product.codename
echo "=== STEP 0.3 ==="
adb shell getprop ro.build.version.release
echo "=== STEP 0.4 ==="
adb shell cat /sys/devices/system/cpu/online
echo "=== STEP 0.5 ==="
adb shell 'for z in /sys/class/thermal/thermal_zone*; do printf "%s | type=%-25s | temp=%s\n" "$z" "$(cat $z/type 2>/dev/null)" "$(cat $z/temp 2>/dev/null)"; done'
echo "=== STEP 0.6 ==="
adb shell ls -la /data/local/tmp/llama-cli
echo "=== STEP 0.7 ==="
adb shell ls -lh /sdcard/models/qwen2.5-3b-instruct-q4_k_m.gguf
echo "=== STEP 0.8 ==="
adb shell which taskset
echo "=== STEP 0.9 ==="
adb shell mkdir -p /sdcard/edgemind_phase9_logs
echo "=== STEP 0.10 ==="
adb shell cat /proc/meminfo | grep -E 'MemTotal|MemAvailable|SwapTotal|SwapFree'
adb shell getprop ro.product.board
adb shell cat /sys/devices/system/cpu/cpu7/cpufreq/cpuinfo_max_freq
