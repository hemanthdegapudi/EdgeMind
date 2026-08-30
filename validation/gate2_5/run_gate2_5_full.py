import os, sys, time, json, re, subprocess
from datetime import datetime

LOG_FILE = "validation/gate2_5/gate2_5_integrity.json"
REPORT_FILE = "validation/gate2_5/gate2_5_integrity_report.md"

MODELS = {
    "deepseek": {"id": "deepseek-r1-distill-qwen-1.5b-q5km", "name": "DeepSeek"},
    "qwen3": {"id": "qwen3-1.7b-q4km", "name": "Qwen3"}
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
    c, procmem, e = adb("shell cat /proc/meminfo", timeout=5)
    for line in procmem.split('\n'):
        if ':' in line:
            parts = line.split(':')
            k = parts[0].strip()
            if k in ["MemAvailable", "MemFree", "Cached", "SwapFree"]:
                try: m[k] = int(parts[1].strip().split()[0])
                except: pass

    if pid:
        c, meminfo, e = adb(f"shell dumpsys meminfo {pid}", timeout=5)
        m["RSS"] = int(re.search(r"TOTAL RSS:\s+(\d+)", meminfo).group(1)) if re.search(r"TOTAL RSS:\s+(\d+)", meminfo) else None
        m["PSS"] = int(re.search(r"TOTAL PSS:\s+(\d+)", meminfo).group(1)) if re.search(r"TOTAL PSS:\s+(\d+)", meminfo) else None
        
        for line in meminfo.split('\n'):
            if line.strip().startswith("Native Heap") and len(line.split()) >= 8:
                parts = line.split()
                try:
                    m["Native_Heap_Size"] = int(parts[7])
                    m["Native_Heap_Alloc"] = int(parts[8])
                    m["Native_Heap_Free"] = int(parts[9])
                except: pass
                break
        
        c, threads, e = adb(f"shell ls /proc/{pid}/task | wc -l", timeout=5)
        m["threads"] = int(threads.strip()) if threads.strip().isdigit() else -1

    c, therm, e = adb('shell "for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case \\"$type\\" in cpu*|cpuss*) cat $z/temp 2>/dev/null;; esac; done"')
    temps = [int(t) for t in therm.split() if t.strip().isdigit()]
    m["cpu_temp"] = max(temps) if temps else -1
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

def run_test_cycle(model_id, prompt="hello"):
    pid = ensure_app_running()
    adb("shell logcat -c")
    broadcast("ACTION_UNLOAD_MODEL")
    time.sleep(3)
    
    baseline = get_metrics(pid)
    if baseline["cpu_temp"] > 45000:
        return {"status": "INVALID", "reason": "Thermal contaminated (HOT)"}
        
    broadcast("ACTION_LOAD_MODEL", f"--es model_id {model_id}")
    t_start = time.time()
    if not wait_for_log("CMD_DONE: Load completed", 120, time.time()):
        return {"status": "TIMEOUT", "phase": "LOAD"}
    load_time = time.time() - t_start
    loaded = get_metrics(pid)
    
    broadcast("ACTION_GENERATE", f"--es prompt '{prompt}' --ei context_budget 64")
    t_start = time.time()
    if not wait_for_log("CMD_DONE: Generation completed", 120, time.time()):
        return {"status": "TIMEOUT", "phase": "GENERATE"}
    
    broadcast("ACTION_UNLOAD_MODEL")
    if not wait_for_log("CMD_DONE: Unload completed", 30, time.time()):
        return {"status": "TIMEOUT", "phase": "UNLOAD"}
    
    time.sleep(3)
    unloaded = get_metrics(pid)
    
    return {
        "status": "VALID",
        "baseline": baseline,
        "loaded": loaded,
        "unloaded": unloaded,
        "load_time_sec": load_time
    }

def main():
    results = {}
    
    print("=== Thermal Isolation & Single Model Run ===")
    results["deepseek_no_reboot"] = []
    for i in range(5):
        print(f"DeepSeek run {i+1}/5")
        res = run_test_cycle(MODELS["deepseek"]["id"])
        results["deepseek_no_reboot"].append(res)
        time.sleep(5)
        
    print("=== Rebooting device for clean run ===")
    adb("reboot")
    adb("wait-for-device", timeout=120)
    time.sleep(30)
    
    results["deepseek_reboot"] = []
    for i in range(5):
        print(f"DeepSeek run {i+1}/5 (post-reboot)")
        res = run_test_cycle(MODELS["deepseek"]["id"])
        results["deepseek_reboot"].append(res)
        time.sleep(5)
        
    print("=== Qwen3 Repeated Run ===")
    adb("reboot")
    adb("wait-for-device", timeout=120)
    time.sleep(30)
    results["qwen3_reboot"] = []
    for i in range(5):
        print(f"Qwen3 run {i+1}/5")
        res = run_test_cycle(MODELS["qwen3"]["id"])
        results["qwen3_reboot"].append(res)
        time.sleep(5)
        
    with open(LOG_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print("Done")

if __name__ == "__main__":
    main()
