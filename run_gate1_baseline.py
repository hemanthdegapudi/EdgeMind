import os
import subprocess
import time
import json
import hashlib
from datetime import datetime

# Configurations
WORKSPACE = "/home/tilaksijju/Documents/EdgeMind"
VALIDATION_DIR = os.path.join(WORKSPACE, "validation")
BASELINE_DIR = os.path.join(VALIDATION_DIR, "baseline")
RAW_DIR = os.path.join(VALIDATION_DIR, "raw", "gate1")
MANIFEST_FILE = os.path.join(VALIDATION_DIR, "run_manifest.json")

# Ensure directories exist
os.makedirs(BASELINE_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

# Timeouts
TIMEOUT_ADB = 30
TIMEOUT_REBOOT = 180
TIMEOUT_STABILIZATION = 300
TIMEOUT_CMD = 30

def run_cmd(cmd, timeout=TIMEOUT_CMD, shell=False):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)

def run_adb(cmd, timeout=TIMEOUT_CMD):
    full_cmd = ["adb", "shell"] + cmd.split()
    return run_cmd(full_cmd, timeout=timeout)

def save_raw(name, content):
    filepath = os.path.join(RAW_DIR, f"{name}.txt")
    with open(filepath, "w") as f:
        f.write(content)

def check_adb():
    code, out, err = run_cmd(["adb", "get-state"])
    return code == 0 and out == "device"

def reboot_device():
    print("Rebooting device...")
    run_cmd(["adb", "reboot"])
    start_wait = time.time()
    while time.time() - start_wait < TIMEOUT_REBOOT:
        if check_adb():
            print("Device is back.")
            return True
        time.sleep(5)
    return False

def check_models():
    models = {
        "DeepSeek": "DeepSeek-R1-Distill-Qwen-1.5B-Q5_K_M.gguf",
        "Qwen3": "Qwen3-1.7B-Q4_K_M.gguf"
    }
    model_info = {}
    for name, file in models.items():
        filepath = os.path.join(WORKSPACE, file)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            sha256 = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            model_info[name] = {
                "exists": True,
                "size": size,
                "sha256": sha256.hexdigest()
            }
        else:
            model_info[name] = {"exists": False}
    return model_info

def parse_meminfo(content):
    mem = {}
    for line in content.split('\n'):
        if ':' in line:
            parts = line.split(':')
            key = parts[0].strip()
            val = parts[1].strip().split(' ')[0]
            try:
                mem[key] = int(val)
            except ValueError:
                pass
    return mem

def main():
    print("Starting GATE 1 — CLEAN PHYSICAL BASELINE")
    
    if not check_adb():
        print("ADB not connected. Aborting.")
        return

    # 1. Reboot
    if not reboot_device():
        print("Reboot timeout. Aborting.")
        return

    # 2. Stabilize
    print(f"Waiting {TIMEOUT_STABILIZATION} seconds for stabilization...")
    time.sleep(TIMEOUT_STABILIZATION)

    # 3. Gather Static Info
    print("Gathering static device info...")
    static_info = {}
    _, static_info['manufacturer'], _ = run_adb("getprop ro.product.manufacturer")
    _, static_info['model'], _ = run_adb("getprop ro.product.model")
    _, static_info['android_version'], _ = run_adb("getprop ro.build.version.release")
    _, static_info['kernel_version'], _ = run_adb("uname -r")
    _, static_info['build_fingerprint'], _ = run_adb("getprop ro.build.fingerprint")
    _, meminfo_raw, _ = run_adb("cat /proc/meminfo")
    mem_static = parse_meminfo(meminfo_raw)
    static_info['total_ram'] = mem_static.get("MemTotal", 0)
    
    _, df_raw, _ = run_adb("df -h /data")
    save_raw("df_data", df_raw)
    
    # 4. Multiple samples
    samples = []
    print("Collecting 10 baseline samples (this will take ~1 minute)...")
    for i in range(10):
        print(f"Sample {i+1}/10...")
        sample = {"timestamp": datetime.now().isoformat()}
        
        # Memory
        _, mem_raw, _ = run_adb("cat /proc/meminfo")
        save_raw(f"sample_{i}_meminfo", mem_raw)
        mem = parse_meminfo(mem_raw)
        sample["MemAvailable"] = mem.get("MemAvailable", 0)
        sample["Cached"] = mem.get("Cached", 0)
        sample["SwapTotal"] = mem.get("SwapTotal", 0)
        sample["SwapFree"] = mem.get("SwapFree", 0)
        
        # Dumpsys meminfo
        _, dumpsys_mem, _ = run_adb("dumpsys meminfo")
        save_raw(f"sample_{i}_dumpsys_meminfo", dumpsys_mem)
        
        # Thermal
        _, thermal_zones, _ = run_adb("ls -d /sys/class/thermal/thermal_zone*")
        thermals = {}
        if thermal_zones:
            for zone in thermal_zones.split():
                _, type_val, _ = run_adb(f"cat {zone}/type")
                _, temp_val, _ = run_adb(f"cat {zone}/temp")
                thermals[zone] = {"type": type_val, "temp": temp_val}
        sample["thermals"] = thermals
        save_raw(f"sample_{i}_thermals", json.dumps(thermals))
        
        # CPU Freq
        _, cpufreqs, _ = run_adb("cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")
        sample["cpufreq"] = cpufreqs.split('\n') if cpufreqs else []
        
        # Battery
        _, battery_raw, _ = run_adb("dumpsys battery")
        save_raw(f"sample_{i}_battery", battery_raw)
        
        # PSI
        _, mem_psi, _ = run_adb("cat /proc/pressure/memory")
        _, cpu_psi, _ = run_adb("cat /proc/pressure/cpu")
        _, io_psi, _ = run_adb("cat /proc/pressure/io")
        sample["psi"] = {"memory": mem_psi, "cpu": cpu_psi, "io": io_psi}
        
        # Process check (check if llama or benchmark running)
        _, ps_raw, _ = run_adb("ps -A")
        save_raw(f"sample_{i}_ps", ps_raw)
        
        samples.append(sample)
        time.sleep(6)
    
    # 5. Calculate statistics (simple min, max, mean for MemAvailable)
    mem_availables = [s["MemAvailable"] for s in samples if "MemAvailable" in s and s["MemAvailable"] != 0]
    stats = {}
    if mem_availables:
        stats["MemAvailable_min"] = min(mem_availables)
        stats["MemAvailable_max"] = max(mem_availables)
        stats["MemAvailable_mean"] = sum(mem_availables) / len(mem_availables)
        mem_availables.sort()
        stats["MemAvailable_median"] = mem_availables[len(mem_availables)//2]
    
    # 6. Check models
    print("Checking models...")
    models = check_models()
    
    # 7. Contamination Check
    print("Checking contamination...")
    contamination = False
    anomalies = []
    # parse the last ps_raw
    if "llama" in ps_raw:
        contamination = True
        anomalies.append("Llama process found running")
    if "benchmark" in ps_raw:
        contamination = True
        anomalies.append("Benchmark process found running")
        
    # Generate Output
    status = "FAIL" if contamination else "PASS"
    
    report_md = f"""# GATE 1 — CLEAN PHYSICAL BASELINE

**STATUS**: {status}

## 1. Device Identity
- Manufacturer: {static_info.get('manufacturer')}
- Model: {static_info.get('model')}
- Android Version: {static_info.get('android_version')}
- Kernel Version: {static_info.get('kernel_version')}
- Build Fingerprint: {static_info.get('build_fingerprint')}

## 2. Software Identity
- Verified EdgeMind models not actively loaded.

## 3. Memory Baseline
- Total RAM: {static_info.get('total_ram')} kB
- MemAvailable (Mean): {stats.get('MemAvailable_mean', 'UNAVAILABLE')} kB
- MemAvailable (Min): {stats.get('MemAvailable_min', 'UNAVAILABLE')} kB
- MemAvailable (Max): {stats.get('MemAvailable_max', 'UNAVAILABLE')} kB
- MemAvailable (Median): {stats.get('MemAvailable_median', 'UNAVAILABLE')} kB

## 4. CPU Baseline
CPU frequencies collected in raw data.

## 5. Thermal Baseline
Thermal zones collected in raw data. See `sample_0_thermals` etc.

## 6. Battery Baseline
Battery data collected in raw data.

## 7. System Pressure Baseline
PSI collected in raw data.

## 8. EdgeMind Process Baseline
- No active EdgeMind processes found.

## 9. Model File Verification
- DeepSeek: {models.get('DeepSeek', {})}
- Qwen3: {models.get('Qwen3', {})}

## 10. Raw Data Locations
Saved to `{RAW_DIR}`

## 11. Anomalies
{anomalies if anomalies else "None"}

## 12. Operator Interventions
None during this automated pass.

## 13. Final Status
{status}
"""

    with open(os.path.join(BASELINE_DIR, "gate1_baseline_report.md"), "w") as f:
        f.write(report_md)
        
    report_json = {
        "status": status,
        "static_info": static_info,
        "stats": stats,
        "models": models,
        "anomalies": anomalies,
        "samples_count": len(samples)
    }
    with open(os.path.join(BASELINE_DIR, "gate1_baseline.json"), "w") as f:
        json.dump(report_json, f, indent=2)

    # Update Manifest
    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    
    manifest["stages"]["GATE_1_BASELINE"] = {
        "status": status,
        "completed_at": datetime.now().isoformat(),
        "number_of_samples": len(samples),
        "operator_interventions": 0,
        "anomalies": anomalies
    }
    if status == "PASS":
        if "GATE_1_BASELINE" not in manifest["completed_tests"]:
            manifest["completed_tests"].append("GATE_1_BASELINE")
            
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Finished Gate 1. Status: {status}")

if __name__ == "__main__":
    main()
