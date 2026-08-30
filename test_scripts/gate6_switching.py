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

def test_switching(harness, model_A, model_B, cycle_idx):
    cycle_metrics = {}
    harness.log(f"Cycle {cycle_idx}: Switching {model_A} -> {model_B}")
    
    # Unload A
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver")
    t0 = time.time()
    wait_for_logcat(harness, r"CMD_DONE: Unload completed")
    t1 = time.time()
    harness.mark_progress("UNLOAD_COMPLETED")
    
    cycle_metrics["unload_timing_s"] = t1 - t0
    cycle_metrics["memory_after_unload"] = harness.get_device_metrics()
    
    # Load B
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell(f"am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id {model_B}")
    t0 = time.time()
    wait_for_logcat(harness, r"CMD_DONE: Load completed")
    t1 = time.time()
    harness.mark_progress("LOAD_COMPLETED")
    
    cycle_metrics["load_timing_s"] = t1 - t0
    cycle_metrics["memory_after_load"] = harness.get_device_metrics()
    cycle_metrics["switch_duration_s"] = cycle_metrics["unload_timing_s"] + cycle_metrics["load_timing_s"]
    cycle_metrics["active_model"] = model_B
    
    # Generate B
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt 'Hello'")
    wait_for_logcat(harness, r"CMD_DONE: Generation completed")
    harness.mark_progress("GENERATION_COMPLETED")
    
    return cycle_metrics


def main():
    harness = Harness()
    stage = "GATE_6_SWITCHING"
    
    if not harness.begin_stage(stage):
        return

    checkpoint = harness.load_checkpoint(stage) or {"progress_idx": 0, "results": []}
    start_idx = checkpoint["progress_idx"]
    all_metrics = checkpoint["results"]
    
    model_A = "deepseek-r1-distill-qwen-1.5b-q5km"
    model_B = "qwen3-1.7b-q4km"
    
    total_cycles = 30

    try:
        harness.start_heartbeat(stage, interval=5, max_no_progress_sec=300)
        
        # Initial load model A
        if start_idx == 0:
            harness.run_adb_shell("logcat -c")
            harness.run_adb_shell(f"am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id {model_A}")
            wait_for_logcat(harness, r"CMD_DONE: Load completed")
            harness.mark_progress("LOAD_COMPLETED")
        
        for i in range(start_idx, total_cycles):
            target_model = model_B if i % 2 == 0 else model_A
            current_model = model_A if i % 2 == 0 else model_B
            
            metrics = test_switching(harness, current_model, target_model, i)
            all_metrics.append(metrics)
            
            harness.save_checkpoint(stage, {
                "progress_idx": i + 1,
                "results": all_metrics
            })
            harness.mark_progress("CHECKPOINT_COMMITTED")
            
        harness.record_result(stage, "PASSED", {"cycles_completed": total_cycles}, [])
        harness.end_stage(stage, "PASSED")
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        harness.record_result(stage, "FAILED", {}, [str(e)])
        harness.end_stage(stage, "FAILED")
    finally:
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
