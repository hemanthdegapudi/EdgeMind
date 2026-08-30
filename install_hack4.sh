adb shell input keyevent 224
adb shell input keyevent 82
adb shell input keyevent 3
sleep 1
adb shell pm install -r -g -t /data/local/tmp/app.apk &
PID=$!
sleep 1
for i in {1..10}; do
  adb shell input tap 750 2150
  sleep 0.5
done
wait $PID
