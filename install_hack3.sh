adb shell input keyevent 224
adb shell input keyevent 82
sleep 1
adb shell pm install -r -g -t /data/local/tmp/app.apk &
PID=$!
sleep 2
adb shell uiautomator dump /data/local/tmp/uidump.xml
adb shell cat /data/local/tmp/uidump.xml
# tap right bottom "Install" button
adb shell input tap 850 2200
adb shell input tap 750 2150
sleep 2
wait $PID
