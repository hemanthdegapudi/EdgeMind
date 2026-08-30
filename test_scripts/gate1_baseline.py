#!/usr/bin/env python3
import sys
import json
import datetime
from harness import Harness

def main():
    harness = Harness()
    stage = "GATE_1_BASELINE"
    
    if not harness.begin_stage(stage):
        return

    try:
        harness.start_heartbeat(stage, interval=5)
        
        # Collect baseline metrics
        metrics = {}
        
        harness.log("Collecting dumpsys meminfo...")
        meminfo = harness.run_cmd(["adb", "shell", "dumpsys", "meminfo"])
        
        harness.log("Collecting dumpsys cpuinfo...")
        cpuinfo = harness.run_cmd(["adb", "shell", "dumpsys", "cpuinfo"])
        
        harness.log("Collecting dumpsys thermalservice...")
        thermals = harness.run_cmd(["adb", "shell", "dumpsys", "thermalservice"])
        
        harness.log("Collecting /proc/meminfo...")
        procmem = harness.run_cmd(["adb", "shell", "cat", "/proc/meminfo"])
        
        metrics["meminfo"] = meminfo.stdout
        metrics["cpuinfo"] = cpuinfo.stdout
        metrics["thermals"] = thermals.stdout
        metrics["procmem"] = procmem.stdout
        
        # Save raw output
        timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        raw_path = f"validation/raw/{timestamp}_baseline.json"
        with open(raw_path, 'w') as f:
            json.dump(metrics, f, indent=2)
            
        harness.log(f"Baseline saved to {raw_path}")
        harness.end_stage(stage, "PASSED")
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        harness.end_stage(stage, "FAILED")
    finally:
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
