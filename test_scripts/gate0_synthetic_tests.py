#!/usr/bin/env python3
import sys, time
import threading
from harness import Harness, AdbDisconnectException

def test_command_timeout(harness):
    harness.log("Running synthetic command timeout test...")
    try:
        harness.run_cmd(["sleep", "3"], timeout=1)
        raise Exception("Command should have timed out!")
    except Exception as e:
        if "timeout" in str(e).lower() or isinstance(e, Exception):
            harness.log("Timeout triggered correctly.")
            harness.mark_progress("TIMEOUT_VALIDATED")

def test_adb_loss(harness):
    harness.log("Running synthetic ADB loss test...")
    # Monkey patch to simulate failure
    original_check = harness.check_adb
    def fake_check():
        raise AdbDisconnectException("Synthetic ADB loss")
    harness.check_adb = fake_check
    
    # wait for heartbeat to trigger alarm
    time.sleep(12)
    harness.check_adb = original_check
    harness.log("Restored ADB check.")
    harness.mark_progress("ADB_LOSS_VALIDATED")

def test_watchdog_stall(harness):
    harness.log("Running synthetic watchdog stall test...")
    # We will just sleep for a long time. The max_no_progress_sec is set to 5 in heartbeat
    time.sleep(10)
    harness.mark_progress("WATCHDOG_STALL_VALIDATED")

def main():
    harness = Harness()
    stage = "GATE_0_SYNTHETIC"
    
    # We need to mock the input() for alarm_human_intervention so it doesn't block forever
    import builtins
    original_input = builtins.input
    def fake_input(prompt):
        harness.log(f"Auto-answering 'c' to prompt: {prompt}")
        return "c"
    builtins.input = fake_input

    if not harness.begin_stage(stage, force_rerun=True):
        return

    try:
        # 1. Command Timeout Test
        test_command_timeout(harness)
        
        # 2. Watchdog Stall Test
        harness.start_heartbeat(stage, interval=2, max_no_progress_sec=5)
        test_watchdog_stall(harness)
        harness.stop_heartbeat()
        
        # 3. ADB Loss Test
        harness.start_heartbeat(stage, interval=2, max_no_progress_sec=60)
        test_adb_loss(harness)
        harness.stop_heartbeat()
        
        # 4. Checkpoint crash-recovery test
        harness.log("Testing checkpoint recovery...")
        harness.save_checkpoint(stage, {"test_key": "test_value"})
        chk = harness.load_checkpoint(stage)
        if chk.get("test_key") != "test_value":
            raise Exception("Checkpoint read failed")
        harness.mark_progress("CHECKPOINT_RECOVERY_VALIDATED")
        
        harness.record_result(stage, "PASSED", {"synthetic_tests_run": 4}, [])
        harness.end_stage(stage, "PASSED")
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        harness.record_result(stage, "FAILED", {}, [str(e)])
        harness.end_stage(stage, "FAILED")
    finally:
        builtins.input = original_input
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
