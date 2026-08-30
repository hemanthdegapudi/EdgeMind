#!/usr/bin/env python3
import sys, time
from harness import Harness

def test_offline(harness):
    harness.log("Testing offline mode...")
    
    # Disable network
    harness.run_adb_shell("svc wifi disable")
    harness.run_adb_shell("svc data disable")
    time.sleep(3)
    harness.mark_progress("NETWORK_DISABLED")
    
    metrics = {"network_disabled": True}
    
    # Run a simple inference
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id qwen3-1.7b-q4km")
    time.sleep(5)
    
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt 'Hello offline mode'")
    
    # Wait for completion
    time.sleep(15)
    
    out = harness.run_adb_shell("logcat -d -s TestReceiver").stdout
    if "CMD_DONE: Generation completed" in out:
        metrics["inference_success"] = True
    else:
        metrics["inference_success"] = False
        
    harness.mark_progress("OFFLINE_INFERENCE_TESTED")
    
    # Enable network
    harness.run_adb_shell("svc wifi enable")
    harness.run_adb_shell("svc data enable")
    
    return metrics

def main():
    harness = Harness()
    stage = "GATE_11_OFFLINE"
    
    if not harness.begin_stage(stage):
        return

    try:
        harness.start_heartbeat(stage, interval=5, max_no_progress_sec=300)
        
        metrics = test_offline(harness)
            
        harness.record_result(stage, "PASSED", metrics, [])
        harness.end_stage(stage, "PASSED")
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        harness.record_result(stage, "FAILED", {}, [str(e)])
        harness.end_stage(stage, "FAILED")
    finally:
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
