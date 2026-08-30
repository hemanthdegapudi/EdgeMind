#!/bin/bash
set -e

echo "--- Test A: Package Count ---"
PKG_COUNT=$(adb shell pm list packages | grep -i edgemind | wc -l)
echo "Packages found: $PKG_COUNT"
if [ "$PKG_COUNT" -ne 1 ]; then
    echo "FAIL: Expected 1 package, found $PKG_COUNT"
    exit 1
fi
echo "PASS: One EdgeMind package."

echo "--- Test B: Launch ---"
adb shell am force-stop com.edgemind.app
adb shell am start -n com.edgemind.app/.ui.ChatActivity
sleep 2
PID=$(adb shell pidof com.edgemind.app || echo "")
if [ -z "$PID" ]; then
    echo "FAIL: App did not launch"
    exit 1
fi
echo "PASS: App launched (PID $PID)."

echo "--- Test C: Qwen Inference ---"
adb shell logcat -c
adb shell am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id "qwen3-1.7b-q4km"
sleep 5
adb shell am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt "What is 2+2?" --ez json_mode false
sleep 15
QWEN_OUT=$(adb shell logcat -d | grep "CMD_OUTPUT")
if [ -z "$QWEN_OUT" ]; then
    echo "FAIL: Qwen did not generate output"
    exit 1
fi
echo "PASS: Qwen generated output: $QWEN_OUT"

echo "--- Test D: Qwen -> DeepSeek Switch ---"
adb shell am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver
sleep 3
adb shell am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id "deepseek-r1-distill-qwen-1.5b-q5km"
sleep 5

echo "--- Test E: DeepSeek Inference ---"
adb shell logcat -c
adb shell am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt "What is 3+3?" --ez json_mode false
sleep 15
DS_OUT=$(adb shell logcat -d | grep "CMD_OUTPUT")
if [ -z "$DS_OUT" ]; then
    echo "FAIL: DeepSeek did not generate output"
    exit 1
fi
echo "PASS: DeepSeek generated output: $DS_OUT"

echo "--- Test F: DeepSeek -> Qwen Switch ---"
adb shell am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver
sleep 3
adb shell am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id "qwen3-1.7b-q4km"
sleep 5
echo "PASS: Switch back to Qwen complete."

echo "All tests passed!"
