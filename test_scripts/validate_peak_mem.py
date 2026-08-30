#!/usr/bin/env python3
import json
import sys
import time
from harness import Harness

def main():
    harness = Harness()
    
    print("Starting fresh process...")
    try:
        pid = harness.start_fresh_process()
    except Exception as e:
        print(f"Failed to start process: {e}")
        sys.exit(1)
        
    print(f"Fresh process started with PID: {pid}")
    
    # Wait a bit to ensure it is fully initialized and memory is stable
    time.sleep(5)
    
    model_to_test = "qwen3-1.7b-q4km"
    
    print(f"\nStarting model load test for {model_to_test} with peak memory tracking...")
    result = harness.load_model_with_peak_memory_tracking(
        model_id=model_to_test,
        timeout_sec=120,
        interval_sec=0.2
    )
    
    print("\nRESULTS:")
    print(json.dumps(result, indent=2))
    
    if result["status"] == "PASSED":
        print("\nSUCCESS: Model loaded and peak memory tracked successfully.")
    else:
        print(f"\nFAILURE: Test failed with status {result['status']}. Error: {result.get('error', 'Unknown')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
