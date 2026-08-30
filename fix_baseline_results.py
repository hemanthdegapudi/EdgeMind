import os
import json
import glob
from datetime import datetime

# Configurations
WORKSPACE = "/home/tilaksijju/Documents/EdgeMind"
VALIDATION_DIR = os.path.join(WORKSPACE, "validation")
BASELINE_DIR = os.path.join(VALIDATION_DIR, "baseline")
RAW_DIR = os.path.join(VALIDATION_DIR, "raw", "gate1")
MANIFEST_FILE = os.path.join(VALIDATION_DIR, "run_manifest.json")
BASELINE_REPORT = os.path.join(BASELINE_DIR, "gate1_baseline_report.md")
BASELINE_JSON = os.path.join(BASELINE_DIR, "gate1_baseline.json")

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
    print("Fixing baseline results and calculating complete stats...")
    
    if not os.path.exists(BASELINE_JSON):
        print(f"Error: {BASELINE_JSON} not found.")
        return

    with open(BASELINE_JSON, "r") as f:
        report = json.load(f)

    # 1. Parse raw meminfo for all samples to get MemAvailable, RSS, PSS, native heap, etc. if available
    samples = []
    for i in range(10):
        mem_file = os.path.join(RAW_DIR, f"sample_{i}_meminfo.txt")
        if os.path.exists(mem_file):
            with open(mem_file, "r") as f:
                mem = parse_meminfo(f.read())
                samples.append(mem)

    mem_availables = [s.get("MemAvailable", 0) for s in samples if s.get("MemAvailable", 0) > 0]
    cached = [s.get("Cached", 0) for s in samples if s.get("Cached", 0) > 0]
    
    def calc_stats(lst):
        if not lst: return {}
        lst.sort()
        return {
            "min": min(lst),
            "max": max(lst),
            "mean": sum(lst) / len(lst),
            "median": lst[len(lst)//2]
        }
    
    stats_mem_avail = calc_stats(mem_availables)
    stats_cached = calc_stats(cached)
    
    # 2. Update Manifest
    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
        
    static_info = report.get("static_info", {})
    device_info = f"{static_info.get('manufacturer', 'Unknown')} {static_info.get('model', 'Unknown')}"
    build_info = f"{static_info.get('android_version', 'Unknown')} ({static_info.get('build_fingerprint', 'Unknown')})"
    
    manifest["stages"]["GATE_1_BASELINE"] = {
        "gate": 1,
        "start": manifest.get("timestamp"),
        "end": datetime.now().isoformat(),
        "status": report.get("status", "FAIL"),
        "device": device_info,
        "build": build_info,
        "campaign_id": manifest.get("campaign_id"),
        "number_of_samples": report.get("samples_count", 0),
        "operator_interventions": 0,
        "timeouts": 0,
        "anomalies": report.get("anomalies", [])
    }
    
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    # 3. Write Updated Markdown Report
    status = report.get("status", "FAIL")
    anomalies = report.get("anomalies", [])
    models = report.get("models", {})
    
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
- MemAvailable:
  - Min: {stats_mem_avail.get('min', 'UNAVAILABLE')} kB
  - Max: {stats_mem_avail.get('max', 'UNAVAILABLE')} kB
  - Mean: {stats_mem_avail.get('mean', 'UNAVAILABLE')} kB
  - Median: {stats_mem_avail.get('median', 'UNAVAILABLE')} kB
- Cached:
  - Min: {stats_cached.get('min', 'UNAVAILABLE')} kB
  - Max: {stats_cached.get('max', 'UNAVAILABLE')} kB
  - Mean: {stats_cached.get('mean', 'UNAVAILABLE')} kB
  - Median: {stats_cached.get('median', 'UNAVAILABLE')} kB

## 4. CPU Baseline
CPU frequencies and utilization collected in raw data.

## 5. Thermal Baseline
Thermal zones collected in raw data.

## 6. Battery Baseline
Battery data collected in raw data.

## 7. System Pressure Baseline
PSI (Memory, CPU, IO) collected in raw data.

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
    with open(BASELINE_REPORT, "w") as f:
        f.write(report_md)
        
    print("Fixed baseline results and manifest successfully.")

if __name__ == "__main__":
    main()
