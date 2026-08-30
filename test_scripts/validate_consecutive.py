import sys
import json
import time
from harness import Harness

def main():
    print("--- Starting Consecutive Cycles Validation ---")
    h = Harness(manifest_path="validation/test_manifest.json")
    
    model_id = "qwen3-1.7b-q4km"
    num_cycles = 3
    results = []
    
    for i in range(num_cycles):
        print(f"\n--- Cycle {i+1} ---")
        try:
            pid_expected = h.start_fresh_process()
            print(f"Started fresh process with PID: {pid_expected}")
            
            # Wait for stabilization
            time.sleep(3)
            
            res = h.load_model_with_peak_memory_tracking(model_id=model_id, timeout_sec=60, interval_sec=0.2)
            results.append(res)
            
        except Exception as e:
            print(f"Error in cycle {i+1}: {e}")
            sys.exit(1)
            
    print("\n--- Final Validation Output ---")
    print(json.dumps(results, indent=2))
    
    passed = True
    for i, res in enumerate(results):
        if res.get("status") != "PASSED":
            print(f"FAIL: Cycle {i+1} status is {res.get('status')} - Error: {res.get('error')}")
            passed = False
            
    if passed:
        print("PASS")
    else:
        print("FAIL")
        sys.exit(1)

if __name__ == "__main__":
    main()
