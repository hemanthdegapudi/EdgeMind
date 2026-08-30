#!/usr/bin/env python3
import sys
import json
import datetime
import subprocess
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

def test_model(harness, model_id):
    harness.log(f"Testing model {model_id}...")
    metrics = []
    
    for i in range(3):
        harness.log(f"Iteration {i+1}/3")
        cycle_metrics = {}
        
        # Base memory
        time.sleep(2)
        # Ensure no models are loaded initially
        clear_logcat(harness)
        run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_UNLOAD_MODEL", "-n", "com.edgemind.app/.TestReceiver"])
        time.sleep(2)
        base_mem = get_memory(harness)
        cycle_metrics["memory_before_load"] = base_mem
        
        # Load Model
        harness.log("Loading model...")
        clear_logcat(harness)
        run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_LOAD_MODEL", "-n", "com.edgemind.app/.TestReceiver", "--es", "model_id", model_id])
        
        line = wait_for_logcat(harness, r"CMD_DONE: Load completed")
        match = re.search(r"in (\d+)ms", line)
        cycle_metrics["load_time_ms"] = int(match.group(1)) if match else 0
        
        time.sleep(2)
        loaded_mem = get_memory(harness)
        cycle_metrics["memory_after_load"] = loaded_mem
        
        # Generate
        harness.log("Generating response...")
        clear_logcat(harness)
        run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_GENERATE", "-n", "com.edgemind.app/.TestReceiver", "--es", "prompt", "'What is artificial intelligence? Explain briefly.'"])
        
        line = wait_for_logcat(harness, r"CMD_DONE: Generation completed")
        # Log.i("TestReceiver", "CMD_DONE: Generation completed. Tokens: $tokenCount, TotalTime: ${totalTime}ms, TTFT/Prefill: ${prefill}ms, DecodeTPS: $decodeTps")
        match = re.search(r"Tokens: (\d+), TotalTime: (\d+)ms, TTFT/Prefill: (\d+)ms, DecodeTPS: ([\d\.]+)", line)
        if match:
            cycle_metrics["tokens"] = int(match.group(1))
            cycle_metrics["total_time_ms"] = int(match.group(2))
            cycle_metrics["ttft_ms"] = int(match.group(3))
            cycle_metrics["decode_tps"] = float(match.group(4))
        
        # Memory after generation
        gen_mem = get_memory(harness)
        cycle_metrics["memory_after_generation"] = gen_mem
        
        # Unload Model
        harness.log("Unloading model...")
        clear_logcat(harness)
        run_adb(harness, ["am", "broadcast", "-a", "com.edgemind.ACTION_UNLOAD_MODEL", "-n", "com.edgemind.app/.TestReceiver"])
        wait_for_logcat(harness, r"CMD_DONE: Unload completed")
        
        time.sleep(5) # wait for GC
        unloaded_mem = get_memory(harness)
        cycle_metrics["memory_after_unload"] = unloaded_mem
        
        metrics.append(cycle_metrics)
        
    return metrics

def main():
    harness = Harness()
    stage = "GATE_2_INDEPENDENT"
    
    if not harness.begin_stage(stage):
        return

    try:
        harness.start_heartbeat(stage, interval=5)
        
        models = ["deepseek-r1-distill-qwen-1.5b-q5km", "qwen3-1.7b-q4km"]
        all_metrics = {}
        
        for model in models:
            metrics = test_model(harness, model)
            all_metrics[model] = metrics
            
        timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        raw_path = f"validation/raw/{timestamp}_gate2.json"
        with open(raw_path, 'w') as f:
            json.dump(all_metrics, f, indent=2)
            
        harness.log(f"Gate 2 metrics saved to {raw_path}")
        harness.end_stage(stage, "PASSED")
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        harness.end_stage(stage, "FAILED")
    finally:
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
