adb shell pm install -r -g -t /data/local/tmp/app.apk &
PID=$!
for i in {1..15}; do
    sleep 1
    adb shell uiautomator dump /data/local/tmp/uidump.xml > /dev/null 2>&1
    if adb shell cat /data/local/tmp/uidump.xml 2>/dev/null | grep -i "install"; then
        # Just tap a few likely spots for "Install" button on a Redmi K20 Pro (1080x2340)
        adb shell input tap 700 2200
        adb shell input tap 800 2200
        adb shell input tap 500 2200
    fi
done
wait $PID
