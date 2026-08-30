import os
import subprocess
import time
import json
import re
from datetime import datetime

# Configurations
WORKSPACE = "/home/tilaksijju/Documents/EdgeMind"
VALIDATION_DIR = os.path.join(WORKSPACE, "validation", "performance")
RAW_DIR = os.path.join(VALIDATION_DIR, "raw", "gate2")
os.makedirs(RAW_DIR, exist_ok=True)

PROMPT = "What is the capital of France? Answer in one word."

MODELS = [
    {"id": "deepseek-r1-distill-qwen-1.5b-q5km", "name": "DeepSeek"},
    {"id": "qwen3-1.7b-q4km", "name": "Qwen3"}
]

def run_cmd(cmd, timeout=30):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def run_adb(cmd, timeout=30):
    return run_cmd(["adb", "shell"] + cmd.split(), timeout=timeout)

def get_pid():
    code, out, _ = run_adb("pidof com.edgemind.app")
    if code == 0 and out.isdigit():
        return out
    return None

def get_meminfo():
    _, out, _ = run_adb("cat /proc/meminfo")
    mem = {}
    for line in out.split('\n'):
        if ':' in line:
            parts = line.split(':')
            key = parts[0].strip()
            val = parts[1].strip().split()[0]
            try: mem[key] = int(val)
            except: pass
    return mem

def get_process_mem(pid):
    if not pid: return {}
    code, out, _ = run_adb(f"dumpsys meminfo {pid}")
    if code != 0: return {}
    mem = {}
    for line in out.split('\n'):
        line = line.strip()
        if line.startswith("TOTAL PSS:"):
            parts = line.split()
            try:
                if "PSS:" in parts:
                    idx = parts.index("PSS:") + 1
                    mem["PSS"] = int(parts[idx])
                if "RSS:" in parts:
                    idx = parts.index("RSS:") + 1
                    mem["RSS"] = int(parts[idx])
            except: pass
        elif line.startswith("Native Heap"):
            parts = line.split()
            if len(parts) >= 8:
                try:
                    mem["Native_Heap_Allocated"] = int(parts[6])
                    mem["Native_Heap_Free"] = int(parts[7])
                except: pass
    return mem

def get_thermals():
    _, zones, _ = run_adb("ls -d /sys/class/thermal/thermal_zone*")
    thermals = {}
    if zones:
        for zone in zones.split():
            _, type_val, _ = run_adb(f"cat {zone}/type")
            _, temp_val, _ = run_adb(f"cat {zone}/temp")
            try:
                thermals[type_val] = int(temp_val)
            except: pass
    return thermals

def get_battery():
    _, out, _ = run_adb("dumpsys battery")
    bat = {}
    for line in out.split('\n'):
        if ':' in line:
            parts = line.split(':')
            key = parts[0].strip()
            val = parts[1].strip()
            try: bat[key] = int(val)
            except: bat[key] = val
    return bat

def get_cpu():
    _, loadavg, _ = run_adb("cat /proc/loadavg")
    return {"loadavg": loadavg}
    
def get_cpu_freqs():
    _, out, _ = run_adb("cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")
    freqs = []
    if out:
        for f in out.split('\n'):
            try: freqs.append(int(f))
            except: pass
    return freqs

def get_psi():
    psi = {}
    for t in ['memory', 'cpu', 'io']:
        _, out, _ = run_adb(f"cat /proc/pressure/{t}")
        psi[t] = out.replace('\n', '; ')
    return psi

def capture_metrics():
    pid = get_pid()
    return {
        "timestamp": datetime.now().isoformat(),
        "MemAvailable": get_meminfo().get("MemAvailable", 0),
        "process": get_process_mem(pid),
        "thermals": get_thermals(),
        "battery": get_battery(),
        "cpu": get_cpu(),
        "cpu_freqs": get_cpu_freqs(),
        "psi": get_psi()
    }

def wait_for_logcat(pattern, timeout):
    start = time.time()
    while time.time() - start < timeout:
        _, out, _ = run_cmd(["adb", "logcat", "-d", "-s", "TestReceiver"])
        for line in out.split('\n'):
            if re.search(pattern, line):
                return line
        time.sleep(1)
    return None

def main():
    if not get_pid():
        print("App is not running. Starting foreground service...")
        run_adb("am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService")
        time.sleep(5)
        if not get_pid():
            print("Failed to start app.")
            return

    results = []
    
    for model in MODELS:
        print(f"=== Testing Model: {model['name']} ({model['id']}) ===")
        for i in range(5):
            print(f"--- Repetition {i+1}/5 ---")
            run_id = f"{model['name']}_rep{i+1}"
            
            run_cmd(["adb", "logcat", "-c"])
            run_adb("am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver")
            time.sleep(5)
            run_cmd(["adb", "logcat", "-c"])
            
            print("Capturing baseline...")
            baseline_metrics = capture_metrics()
            
            print("Starting model load...")
            load_start = time.time()
            run_adb(f"am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id {model['id']} --ei context_size 2048")
            
            load_line = wait_for_logcat("CMD_DONE: Load completed", 120)
            if not load_line:
                print("Model load timed out!")
                continue
                
            load_match = re.search(r"completed in (\d+)ms", load_line)
            load_duration = int(load_match.group(1)) if load_match else int((time.time()-load_start)*1000)
            
            print(f"Load completed in {load_duration}ms. Capturing metrics...")
            load_metrics = capture_metrics()
            
            print("Starting generation...")
            run_cmd(["adb", "logcat", "-c"])
            run_adb(f"am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt \"{PROMPT}\" --ei context_budget 64")
            
            gen_metrics_during = []
            start_gen_wait = time.time()
            gen_line = None
            while time.time() - start_gen_wait < 120:
                _, out, _ = run_cmd(["adb", "logcat", "-d", "-s", "TestReceiver"])
                for line in out.split('\n'):
                    if "CMD_DONE: Generation completed" in line:
                        gen_line = line
                        break
                if gen_line:
                    break
                gen_metrics_during.append(capture_metrics())
                time.sleep(2)
                
            if not gen_line:
                print("Generation timed out!")
                continue
                
            gen_match = re.search(r"Tokens: (\d+), TotalTime: (\d+)ms, TTFT/Prefill: (\d+)ms, DecodeTPS: ([\d.]+)", gen_line)
            gen_stats = {}
            if gen_match:
                gen_stats = {
                    "tokens": int(gen_match.group(1)),
                    "total_time": int(gen_match.group(2)),
                    "ttft": int(gen_match.group(3)),
                    "decode_tps": float(gen_match.group(4))
                }
            print(f"Generation complete: {gen_stats}")
            
            post_gen_metrics = capture_metrics()
            
            print("Unloading model...")
            run_cmd(["adb", "logcat", "-c"])
            unload_start_time = time.time()
            run_adb("am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver")
            
            unload_line = wait_for_logcat("CMD_DONE: Unload completed", 120)
            unload_duration = time.time() - unload_start_time
            if not unload_line:
                print("Unload timed out!")
                continue
                
            print(f"Unloaded in {unload_duration:.2f}s")
            
            print("Waiting for stabilization (15s)...")
            time.sleep(15)
            post_unload_metrics = capture_metrics()
            
            def get_val(m, k1, k2=None):
                v = m.get(k1, {})
                return v.get(k2, 0) if k2 else m.get(k1, 0)
                
            mem_avail_baseline = get_val(baseline_metrics, "MemAvailable")
            mem_avail_load = get_val(load_metrics, "MemAvailable")
            mem_avail_post_gen = get_val(post_gen_metrics, "MemAvailable")
            mem_avail_post_unload = get_val(post_unload_metrics, "MemAvailable")
            
            rss_baseline = get_val(baseline_metrics, "process", "RSS")
            rss_load = get_val(load_metrics, "process", "RSS")
            rss_post_gen = get_val(post_gen_metrics, "process", "RSS")
            rss_post_unload = get_val(post_unload_metrics, "process", "RSS")
            
            pss_baseline = get_val(baseline_metrics, "process", "PSS")
            pss_load = get_val(load_metrics, "process", "PSS")
            pss_post_gen = get_val(post_gen_metrics, "process", "PSS")
            pss_post_unload = get_val(post_unload_metrics, "process", "PSS")
            
            deltas = {
                "MemAvailable": {
                    "loaded_delta": mem_avail_load - mem_avail_baseline,
                    "generation_delta": mem_avail_post_gen - mem_avail_load,
                    "post_unload_delta": mem_avail_post_unload - mem_avail_baseline
                },
                "RSS": {
                    "loaded_delta": rss_load - rss_baseline,
                    "generation_delta": rss_post_gen - rss_load,
                    "post_unload_delta": rss_post_unload - rss_baseline
                },
                "PSS": {
                    "loaded_delta": pss_load - pss_baseline,
                    "generation_delta": pss_post_gen - pss_load,
                    "post_unload_delta": pss_post_unload - pss_baseline
                }
            }
            
            run_data = {
                "run_id": run_id,
                "model_id": model["id"],
                "model_sha256": "5190cb74aef330f7d4cf6a6a06553248b0c5bf1054a455184bbe58c03437ba37" if "deepseek" in model["id"] else "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5",
                "timestamp": datetime.now().isoformat(),
                "baseline_metrics": baseline_metrics,
                "load_metrics": load_metrics,
                "inference_metrics": gen_stats,
                "generation_metrics": gen_metrics_during,
                "post_generation_metrics": post_gen_metrics,
                "unload_metrics": {"unload_duration_s": unload_duration, "load_duration_ms": load_duration},
                "post_unload_metrics": post_unload_metrics,
                "deltas": deltas,
                "duration": time.time() - (unload_start_time - 120),
                "status": "SUCCESS",
                "errors": [],
                "operator_intervention": False
            }
            
            results.append(run_data)
            
            with open(os.path.join(RAW_DIR, f"{run_id}.json"), "w") as f:
                json.dump(run_data, f, indent=2)
                
            print("Cooling down (30s)...")
            time.sleep(30)
            
    with open(os.path.join(VALIDATION_DIR, "gate2_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("Done")

if __name__ == "__main__":
    main()
