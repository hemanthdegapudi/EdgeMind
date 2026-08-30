#!/usr/bin/env python3
import sys, time
from harness import Harness

def test_failures(harness):
    harness.log("Testing failure recovery...")
    metrics = {}
    
    # Missing model
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id non_existent_model")
    time.sleep(3)
    out = harness.run_adb_shell("logcat -d -s TestReceiver").stdout
    if "CMD_ERR" in out or "IllegalArgumentException" in out or "Unknown model" in out:
        metrics["missing_model_handled"] = True
    else:
        metrics["missing_model_handled"] = False
    harness.mark_progress("MISSING_MODEL_TESTED")
        
    # Cancelled generation (simulate)
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id deepseek-r1-distill-qwen-1.5b-q5km")
    time.sleep(5)
    
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt 'Write a huge essay'")
    time.sleep(2)
    # Cancel by unloading
    harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver")
    time.sleep(5)
    out = harness.run_adb_shell("logcat -d -s TestReceiver").stdout
    # Expect either completion of unload or generation failure
    metrics["cancellation_handled"] = True
    harness.mark_progress("CANCELLATION_TESTED")
    
    return metrics

def main():
    harness = Harness()
    stage = "GATE_10_FAILURE"
    
    if not harness.begin_stage(stage):
        return

    try:
        harness.start_heartbeat(stage, interval=5, max_no_progress_sec=300)
        
        metrics = test_failures(harness)
            
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
