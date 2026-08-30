#!/usr/bin/env python3
import sys
import json
import datetime
import time
import re
from harness import Harness

def run_adb(harness, cmd):
    return harness.run_cmd(["adb", "shell"] + cmd).stdout

def get_memory(harness):
    out = run_adb(harness, ["dumpsys", "meminfo", "com.edgemind.app"])
    rss_match = re.search(r"TOTAL RSS:\s+(\d+)", out)
    pss_match = re.search(r"TOTAL PSS:\s+(\d+)", out)
    
    procmem = run_adb(harness, ["cat", "/proc/meminfo"])
    avail_match = re.search(r"MemAvailable:\s+(\d+)\s+kB", procmem)
    
    rss = int(rss_match.group(1)) if rss_match else 0
    pss = int(pss_match.group(1)) if pss_match else 0
    avail = int(avail_match.group(1)) if avail_match else 0
    
    return {"rss_kb": rss, "pss_kb": pss, "avail_kb": avail}

def clear_logcat(harness):
    harness.run_cmd(["adb", "logcat", "-c"])

def wait_for_logcat(harness, pattern, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        out = harness.run_cmd(["adb", "logcat", "-d", "-s", "TestReceiver"]).stdout
        for line in out.splitlines():
            if re.search(pattern, line):
                return line
            if "CMD_ERR" in line:
                raise Exception(f"Action failed: {line}")
        time.sleep(1)
    raise Exception(f"Timeout waiting for logcat pattern: {pattern}")

def perform_switch(harness, model_id, is_json):
    cycle_metrics = {}
    
    # 1. Base memory
    time.sleep(2)
    base_mem = get_memory(harness)
    cycle_metrics["memory_before_load"] = base_mem
    
    # 2. Load Model
    harness.log(f"Loading model {model_id}...")
    clear_logcat(harness)
    run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_LOAD_MODEL", "-n", "com.edgemind.app/.TestReceiver", "--es", "model_id", model_id])
    
    line = wait_for_logcat(harness, r"CMD_DONE: Load completed")
    match = re.search(r"in (\d+)ms", line)
    cycle_metrics["load_time_ms"] = int(match.group(1)) if match else 0
    
    time.sleep(2)
    loaded_mem = get_memory(harness)
    cycle_metrics["memory_after_load"] = loaded_mem
    
    # 3. Generate
    harness.log("Generating response...")
    clear_logcat(harness)
    
    if is_json:
        prompt = "'Generate a JSON object with a single key \"status\" and value \"ok\". Do not output any markdown formatting.'"
        run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_GENERATE", "-n", "com.edgemind.app/.TestReceiver", "--es", "prompt", prompt, "--ez", "json_mode", "true"])
    else:
        prompt = "'What is the capital of France?'"
        run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_GENERATE", "-n", "com.edgemind.app/.TestReceiver", "--es", "prompt", prompt])

    line = wait_for_logcat(harness, r"CMD_DONE: Generation completed")
    match = re.search(r"Tokens: (\d+), TotalTime: (\d+)ms, TTFT/Prefill: (\d+)ms, DecodeTPS: ([\d\.]+)", line)
    if match:
        cycle_metrics["tokens"] = int(match.group(1))
        cycle_metrics["total_time_ms"] = int(match.group(2))
        cycle_metrics["ttft_ms"] = int(match.group(3))
        cycle_metrics["decode_tps"] = float(match.group(4))
    
    gen_mem = get_memory(harness)
    cycle_metrics["memory_after_generation"] = gen_mem
    
    # 4. Unload Model
    harness.log("Unloading model...")
    clear_logcat(harness)
    run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_UNLOAD_MODEL", "-n", "com.edgemind.app/.TestReceiver"])
    wait_for_logcat(harness, r"CMD_DONE: Unload completed")
    
    time.sleep(3) # wait for GC
    unloaded_mem = get_memory(harness)
    cycle_metrics["memory_after_unload"] = unloaded_mem
    
    return cycle_metrics

def main():
    harness = Harness()
    stage = "GATE_3_SWITCHING"
    
    if not harness.begin_stage(stage):
        return

    try:
        harness.start_heartbeat(stage, interval=5)
        
        # Ensure unloaded
        clear_logcat(harness)
        run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_UNLOAD_MODEL", "-n", "com.edgemind.app/.TestReceiver"])
        time.sleep(2)
        
        models = ["deepseek-r1-distill-qwen-1.5b-q5km", "qwen3-1.7b-q4km"]
        all_metrics = []
        
        for i in range(5):
            model_id = models[i % 2]
            is_json = (i % 2 != 0) # Test JSON on every other run
            
            harness.log(f"--- Switch {i+1}/5: {model_id} (JSON mode: {is_json}) ---")
            metrics = perform_switch(harness, model_id, is_json)
            metrics["model_id"] = model_id
            metrics["iteration"] = i + 1
            metrics["json_mode"] = is_json
            all_metrics.append(metrics)
            
        timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        raw_path = f"validation/raw/{timestamp}_gate3.json"
        with open(raw_path, 'w') as f:
            json.dump(all_metrics, f, indent=2)
            
        harness.log(f"Gate 3 metrics saved to {raw_path}")
        harness.end_stage(stage, True)
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        # Capture dmesg for OOM killer logs
        dmesg_out = harness.run_cmd(["adb", "shell", "dmesg"]).stdout
        oom_logs = [line for line in dmesg_out.splitlines() if "Out of memory" in line or "Killed process" in line or "oom_reaper" in line]
        if oom_logs:
            harness.log("OOM Killer detected in dmesg!")
            timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            with open(f"validation/raw/{timestamp}_oom_dmesg.log", "w") as f:
                f.write("\n".join(oom_logs))
        harness.end_stage(stage, False)
    finally:
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
