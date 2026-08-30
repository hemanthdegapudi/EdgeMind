import sys
import json
from harness import Harness

def main():
    print("--- Starting Harness Validation ---")
    h = Harness(manifest_path="validation/test_manifest.json")
    
    # 1. Start fresh process
    print("Initializing fresh process...")
    expected_pid = h.start_fresh_process()
    print(f"Expected PID initialized: {expected_pid}")
    
    # 2. Get device metrics (verifies PID internally now)
    print("Getting device metrics...")
    metrics = h.get_device_metrics()
    
    print("\n--- Validation Output ---")
    print(f"Expected PID: {expected_pid}")
    print(f"Observed PID: {metrics.get('pid')}")
    print(f"PID match result: {metrics.get('pid_match')}")
    print(f"Parsed TOTAL RSS (KB): {metrics.get('rss_kb')}")
    print(f"Parsed TOTAL PSS (KB): {metrics.get('pss_kb')}")
    print(f"MemAvailable (KB) separately: {metrics.get('mem_available_kb')}")
    
    # Validation logic
    passed = True
    if not metrics.get("pid_match"):
        print("FAIL: PID match failed.")
        passed = False
    if not isinstance(metrics.get("rss_kb"), int):
        print("FAIL: TOTAL RSS was not parsed correctly as integer.")
        passed = False
    if not isinstance(metrics.get("pss_kb"), int):
        print("FAIL: TOTAL PSS was not parsed correctly as integer.")
        passed = False
    if not isinstance(metrics.get("mem_available_kb"), int):
        print("FAIL: MemAvailable was not parsed correctly as integer.")
        passed = False
        
    if passed:
        print("\nVALIDATION: PASSED")
    else:
        print("\nVALIDATION: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
