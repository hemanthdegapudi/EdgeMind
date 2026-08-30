adb shell pm install -r -g -t /data/local/tmp/app.apk &
PID=$!
for i in {1..20}; do
    sleep 0.5
    # Tap standard MIUI install button locations
    adb shell input tap 700 2150
    adb shell input tap 700 2200
    adb shell input tap 540 2150
    adb shell input tap 800 2200
    # Tap the switch from the previous dump just in case
    adb shell input tap 900 580
done
wait $PID
