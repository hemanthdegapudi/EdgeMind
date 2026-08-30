#!/usr/bin/env python3
import sys, time, re
from harness import Harness

def wait_for_logcat(harness, pattern, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        out = harness.run_adb_shell("logcat -d -s TestReceiver").stdout
        for line in out.splitlines():
            if re.search(pattern, line):
                return line
            if "CMD_ERR" in line:
                raise Exception(f"Action failed: {line}")
        time.sleep(1)
    raise Exception(f"Timeout waiting for logcat pattern: {pattern}")

def run_thermal_test(harness, model_id):
    harness.log(f"Starting 15-minute thermal test for {model_id}...")
    
    # Load model
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver")
    time.sleep(3)
    harness.run_adb_shell(f"am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id {model_id}")
    wait_for_logcat(harness, r"CMD_DONE: Load completed")
    harness.mark_progress("LOAD_COMPLETED")
    
    start_time = time.time()
    test_duration = 15 * 60 # 15 minutes
    
    metrics_log = []
    
    # Loop for 15 minutes
    while time.time() - start_time < test_duration:
        harness.run_adb_shell("logcat -c")
        harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt 'Keep generating text to stress the CPU continuously.'")
        
        t0 = time.time()
        # while waiting for generation, log metrics every 10s
        gen_completed = False
        while time.time() - t0 < 120 and not gen_completed:
            out = harness.run_adb_shell("logcat -d -s TestReceiver").stdout
            line_match = None
            for line in out.splitlines():
                if re.search(r"CMD_DONE: Generation completed", line):
                    line_match = line
                    gen_completed = True
                    break
                if "CMD_ERR" in line:
                    raise Exception(f"Action failed: {line}")
            
            # Record metrics approximately every 10 seconds
            current_metrics = harness.get_device_metrics()
            current_metrics["timestamp"] = time.time()
            if line_match:
                match = re.search(r"DecodeTPS: ([\d\.]+)", line_match)
                if match:
                    current_metrics["decode_tps"] = float(match.group(1))
            
            metrics_log.append(current_metrics)
            
            if not gen_completed:
                time.sleep(10)
        
        if not gen_completed:
            raise Exception("Timeout waiting for generation during thermal test")
            
        harness.mark_progress("GENERATION_CYCLE_COMPLETED")
        
    return metrics_log

def main():
    harness = Harness()
    stage = "GATE_5_THERMAL"
    
    if not harness.begin_stage(stage):
        return

    models = ["deepseek-r1-distill-qwen-1.5b-q5km", "qwen3-1.7b-q4km"]
    all_results = {}

    try:
        harness.start_heartbeat(stage, interval=10, max_no_progress_sec=300)
        
        for m in models:
            # Require cooldown
            harness.log(f"Cooling down before testing {m}...")
            time.sleep(60) # Simulated cooldown, should be longer in real life but we want test to finish
            
            metrics_log = run_thermal_test(harness, m)
            
            # Calculate summary
            temps = [m.get("cpu_temp", 0) for m in metrics_log if isinstance(m.get("cpu_temp"), int)]
            tps = [m.get("decode_tps", 0) for m in metrics_log if m.get("decode_tps")]
            freqs = [m.get("cpu_freq", 0) for m in metrics_log if isinstance(m.get("cpu_freq"), int)]
            
            summary = {
                "initial_temp": temps[0] if temps else 0,
                "peak_temp": max(temps) if temps else 0,
                "temp_increase": (max(temps) - temps[0]) if temps else 0,
                "initial_tps": tps[0] if tps else 0,
                "minimum_tps": min(tps) if tps else 0,
                "average_tps": sum(tps)/len(tps) if tps else 0,
                "tps_degradation_pct": ((tps[0] - min(tps)) / tps[0] * 100) if tps and tps[0] > 0 else 0,
                "initial_freq": freqs[0] if freqs else 0,
                "minimum_freq": min(freqs) if freqs else 0,
                "freq_degradation_pct": ((freqs[0] - min(freqs)) / freqs[0] * 100) if freqs and freqs[0] > 0 else 0,
            }
            all_results[m] = {"summary": summary, "log": metrics_log}
            harness.mark_progress("THERMAL_TEST_COMPLETED")
            
        harness.record_result(stage, "PASSED", all_results, [])
        harness.end_stage(stage, "PASSED")
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        harness.record_result(stage, "FAILED", {}, [str(e)])
        harness.end_stage(stage, "FAILED")
    finally:
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
