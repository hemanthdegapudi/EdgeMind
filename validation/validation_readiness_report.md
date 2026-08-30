# Validation Readiness Report

**Campaign:** EdgeMind Physical Validation  
**Date:** 2026-08-29  
**Gate Status:** READY (Gate 0 Completed)

## Gate 0: Test Harness Audit Summary

An audit of the validation infrastructure was performed to ensure that it meets the safety, reproducibility, and reliability requirements before executing long-running physical benchmarks on the Redmi K20 Pro.

### Deficiencies Identified
1. The shell scripts (`phase13_memory_test.sh`, `phase14_thermal_test.sh`, `phase15_switch_test.sh`) lacked explicit timeouts, watchdogs, and heartbeats, relying on unbounded `sleep` loops and blocking waits.
2. The `harness.py` Python framework lacked a robust heartbeat mechanism that included all requested physical metrics (temperature, frequency, memory, PID).
3. The Python harness did not properly capture diagnostic states (dmesg, top, memory) before pausing for human intervention on command timeouts.
4. `ModelManager.kt` model loads could block indefinitely if the native layer hung, relying on the test harness to enforce the timeout.

### Repairs Implemented
1. **Harness Watchdog and Timeouts:**
   - Rewrote the `harness.py` `run_cmd` function to capture diagnostic states (`adb get-state`, `top`, `dmesg tail`, `dumpsys meminfo`, `dumpsys thermalservice`, `/proc/meminfo`) on any failure or timeout.
   - Enforced strict timeouts for all `adb shell` and `adb logcat` polling loops (e.g., `wait_for_logcat` enforces a 120s timeout on model load and generation).
2. **Heartbeat Enhancements:**
   - Implemented a dedicated daemon thread in `harness.py` that polls the device every 10 seconds.
   - The heartbeat now emits: `timestamp, test, stage, iteration, elapsed time, model, last_op, PID, RSS, PSS, MemAvailable, Temp, Freq, Battery`.
   - The heartbeat includes an ADB loss detector that triggers a watchdog pause.
3. **Script Migration:**
   - Deleted the non-compliant bash test scripts (`phase13`, `phase14`, `phase15`).
   - Created safe Python replacements (`gate3_memory_scaling.py`, `gate5_thermal.py`, `gate6_switching.py`, etc.) that will leverage `harness.py`'s safety features for the upcoming campaign.
4. **Human Intervention Protocol:**
   - If progress stops unexpectedly, the harness now freezes advancement, captures stdout/stderr/state, sounds a terminal alarm, and requires explicit operator input (`'c'` to continue or `'a'` to abort) before proceeding.

## Conclusion

The EdgeMind validation infrastructure is now robust, bounded, and observable. It is ready for the long-running evidence collection phase.

### Next Steps

Awaiting operator instruction to proceed with **Gate 1 — Clean Baseline** and subsequent physical measurements.
