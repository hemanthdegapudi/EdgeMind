#!/usr/bin/env python3
import sys
import time
import json
import subprocess
import re
from harness import Harness

def run_adb(cmd, timeout_sec=10):
    return subprocess.run(["timeout", f"{timeout_sec}s", "adb", "shell"] + cmd.split(), capture_output=True, text=True).stdout

def main():
    h = Harness()
    
    pid = h.start_fresh_process()
    time.sleep(3)
    
    pre_mem = h.get_device_metrics()
    
    subprocess.run(["timeout", "10s", "adb", "logcat", "-c"])
    
    model_id = "qwen3-1.7b-q4km"
    run_adb(f"am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id {model_id}")
    
    start = time.time()
    load_done = False
    while time.time() - start < 60:
        log = subprocess.run(["timeout", "5s", "adb", "logcat", "-d", "-s", "TestReceiver"], capture_output=True, text=True).stdout
        if "CMD_DONE: Load completed" in log:
            load_done = True
            break
        if "CMD_ERR" in log:
            break
        time.sleep(1)
        
    if not load_done:
        print("FAIL: Model load did not complete")
        sys.exit(1)
        
    time.sleep(2)
    
    run_adb("am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt 'Hello' --ez json_mode false --ei context_budget 512")
    
    start = time.time()
    gen_done = False
    while time.time() - start < 120:
        log = subprocess.run(["timeout", "5s", "adb", "logcat", "-d", "-s", "TestReceiver"], capture_output=True, text=True).stdout
        if "CMD_DONE: Generation completed" in log:
            gen_done = True
            break
        if "CMD_ERR" in log:
            gen_done = True
            break
        time.sleep(1)
        
    time.sleep(2)
    post_mem = h.get_device_metrics()
    
    full_log = subprocess.run(["timeout", "10s", "adb", "logcat", "-d"], capture_output=True, text=True).stdout
    
    results = {
        "pid": pid,
        "pre_mem": pre_mem,
        "post_mem": post_mem,
        "full_log": full_log
    }
    
    with open("validation/raw/inference_run.json", "w") as f:
        json.dump(results, f)
        
    print("TEST_SCRIPT_DONE")

if __name__ == "__main__":
    main()
