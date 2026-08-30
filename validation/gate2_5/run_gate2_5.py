import os, sys, time, json, re, subprocess
from datetime import datetime

os.makedirs("validation/gate2_5", exist_ok=True)
LOG_FILE = "validation/gate2_5/gate2_5_integrity.json"
REPORT_FILE = "validation/gate2_5/gate2_5_integrity_report.md"

MODELS = {
    "deepseek": {"id": "deepseek-r1-distill-qwen-1.5b-q5km", "file": "DeepSeek-R1-Distill-Qwen-1.5B-Q5_K_M.gguf"},
    "qwen3": {"id": "qwen3-1.7b-q4km", "file": "Qwen3-1.7B-Q4_K_M.gguf"}
}

def adb(cmd, timeout=30):
    try:
        r = subprocess.run(f"adb {cmd}", shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"

def get_pid():
    c, o, e = adb("shell pidof com.edgemind.app")
    return o.strip() if c == 0 and o.strip().isdigit() else None

def get_metrics(pid):
    now = datetime.now().isoformat()
    m = {"timestamp": now, "pid": pid}
    
    # proc meminfo
    c, procmem, e = adb("shell cat /proc/meminfo", timeout=10)
    for line in procmem.split('\n'):
        if ':' in line:
            parts = line.split(':')
            k = parts[0].strip()
            v = parts[1].strip().split()[0]
            if k in ["MemAvailable", "MemFree", "Cached", "SwapFree"]:
                try: m[k] = int(v)
                except: pass

    # dumpsys meminfo
    if pid:
        c, meminfo, e = adb(f"shell dumpsys meminfo {pid}", timeout=10)
        # TOTAL PSS and RSS
        rss_m = re.search(r"TOTAL RSS:\s+(\d+)", meminfo)
        pss_m = re.search(r"TOTAL PSS:\s+(\d+)", meminfo)
        if rss_m: m["RSS"] = int(rss_m.group(1))
        if pss_m: m["PSS"] = int(pss_m.group(1))
        
        # Native Heap
        for line in meminfo.split('\n'):
            if line.strip().startswith("Native Heap") and len(line.split()) >= 8:
                parts = line.split()
                try:
                    m["Native_Heap_Size"] = int(parts[7])
                    m["Native_Heap_Alloc"] = int(parts[8])
                    m["Native_Heap_Free"] = int(parts[9])
                except: pass
                break

    # thermal
    c, therm, e = adb('shell "for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case \\"$type\\" in cpu*|cpuss*) cat $z/temp 2>/dev/null;; esac; done"')
    temps = [int(t) for t in therm.split() if t.strip().isdigit()]
    m["cpu_temp"] = max(temps) if temps else -1
    
    # cpu freq
    c, freq, e = adb("shell cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")
    freqs = [int(f) for f in freq.split() if f.strip().isdigit()]
    m["cpu_freq"] = max(freqs) if freqs else -1
    
    # battery
    c, bat, e = adb("shell dumpsys battery")
    bat_m = re.search(r"level:\s+(\d+)", bat)
    m["battery"] = int(bat_m.group(1)) if bat_m else -1
    
    # psi
    m["psi_memory"] = "N/A"
    m["psi_cpu"] = "N/A"
    
    return m

def ensure_app_running():
    pid = get_pid()
    if not pid:
        adb("shell am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService")
        time.sleep(3)
        pid = get_pid()
    return pid

def broadcast(action, extras=""):
    adb(f"shell am broadcast -a com.edgemind.{action} -n com.edgemind.app/.TestReceiver {extras}")

def wait_for_log(pattern, timeout, start_time):
    while time.time() - start_time < timeout:
        c, o, e = adb("shell logcat -d -s TestReceiver MemoryGuard")
        for line in o.split('\n'):
            if pattern in line:
                return line
        time.sleep(1)
    return None

def lifecycle_trace():
    print("=== TEST: Lifecycle Trace ===")
    ensure_app_running()
    adb("shell logcat -c")
    pid = get_pid()
    
    trace = []
    
    print("Capturing baseline...")
    for _ in range(3):
        trace.append({"state": "BASELINE", "metrics": get_metrics(pid)})
        time.sleep(1)
        
    print("Starting load...")
    broadcast("ACTION_LOAD_MODEL", f"--es model_id {MODELS['deepseek']['id']}")
    t_start = time.time()
    
    load_complete = False
    while time.time() - t_start < 60:
        trace.append({"state": "LOADING", "metrics": get_metrics(pid)})
        if wait_for_log("CMD_DONE: Load completed", 1, time.time()):
            load_complete = True
            break
            
    if not load_complete:
        print("TIMEOUT loading")
        return {"error": "Timeout loading"}
        
    for _ in range(3):
        trace.append({"state": "LOADED", "metrics": get_metrics(pid)})
        time.sleep(1)
        
    print("Starting generation...")
    broadcast("ACTION_GENERATE", "--es prompt 'hello' --ei context_budget 64")
    t_start = time.time()
    
    gen_complete = False
    while time.time() - t_start < 60:
        trace.append({"state": "GENERATING", "metrics": get_metrics(pid)})
        if wait_for_log("CMD_DONE: Generation completed", 1, time.time()):
            gen_complete = True
            break
            
    if not gen_complete:
        print("TIMEOUT generation")
        return {"error": "Timeout generation"}
        
    print("Starting unload...")
    broadcast("ACTION_UNLOAD_MODEL")
    t_start = time.time()
    unload_complete = False
    while time.time() - t_start < 30:
        trace.append({"state": "UNLOADING", "metrics": get_metrics(pid)})
        if wait_for_log("CMD_DONE: Unload completed", 1, time.time()):
            unload_complete = True
            break

    for _ in range(5):
        trace.append({"state": "FINAL_IDLE", "metrics": get_metrics(pid)})
        time.sleep(1)
        
    return trace

def main():
    results = {}
    
    # 1. Lifecycle Trace
    results["lifecycle_trace"] = lifecycle_trace()
    
    with open(LOG_FILE, "w") as f:
        json.dump(results, f, indent=2)
        
    print("Done")

if __name__ == "__main__":
    main()
