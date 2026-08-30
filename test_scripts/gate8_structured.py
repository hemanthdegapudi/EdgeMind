#!/usr/bin/env python3
import sys, time, re, json
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

def test_structured(harness, model_id):
    harness.log(f"Testing {model_id} Structured Output (50 cases)...")
    
    # Load model
    harness.run_adb_shell("logcat -c")
    harness.run_adb_shell(f"am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id {model_id}")
    wait_for_logcat(harness, r"CMD_DONE: Load completed")
    harness.mark_progress("LOAD_COMPLETED")
    
    metrics = {
        "total_cases": 50,
        "valid_json": 0,
        "schema_valid": 0,
        "correct_tool": 0,
        "correct_arguments": 0,
        "unwanted_prose": 0,
        "missing_fields": 0,
        "extra_fields": 0,
        "retry_rate": 0
    }
    
    schemas = [
        {"name": "get_weather", "fields": ["location", "unit"]},
        {"name": "turn_on_light", "fields": ["room_name"]},
    ]
    
    for i in range(50):
        schema = schemas[i % len(schemas)]
        prompt = f"Call the {schema['name']} tool with suitable arguments in JSON format."
        harness.run_adb_shell("logcat -c")
        harness.run_adb_shell(f"am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt '{prompt}' --ez json_mode true")
        wait_for_logcat(harness, r"CMD_DONE: Generation completed")
        harness.mark_progress(f"GENERATION_CASE_{i}_COMPLETED")
        
        # Pull output
        out_logs = harness.run_adb_shell("logcat -d -s TestReceiver").stdout
        output_str = ""
        for line in out_logs.splitlines():
            if "CMD_OUTPUT:" in line:
                output_str = line.split("CMD_OUTPUT:")[1].strip()
        
        try:
            parsed = json.loads(output_str)
            metrics["valid_json"] += 1
            
            # Simple schema validation
            is_valid = True
            missing = 0
            extra = 0
            if "name" not in parsed or parsed["name"] != schema["name"]:
                is_valid = False
            else:
                metrics["correct_tool"] += 1
                
            if "arguments" in parsed:
                args = parsed["arguments"]
                for f in schema["fields"]:
                    if f not in args:
                        missing += 1
                        is_valid = False
                for k in args.keys():
                    if k not in schema["fields"]:
                        extra += 1
                        is_valid = False
                
                if is_valid:
                    metrics["schema_valid"] += 1
                    metrics["correct_arguments"] += 1
            else:
                is_valid = False
                
            metrics["missing_fields"] += missing
            metrics["extra_fields"] += extra
            
        except Exception:
            # Invalid JSON
            metrics["unwanted_prose"] += 1 # simplistic assumption if it failed to parse
            
    metrics["valid_json_pct"] = (metrics["valid_json"] / 50.0) * 100
    metrics["schema_valid_pct"] = (metrics["schema_valid"] / 50.0) * 100
    metrics["correct_tool_pct"] = (metrics["correct_tool"] / 50.0) * 100
    metrics["correct_args_pct"] = (metrics["correct_arguments"] / 50.0) * 100
    
    return metrics


def main():
    harness = Harness()
    stage = "GATE_8_STRUCTURED"
    
    if not harness.begin_stage(stage):
        return

    models = ["deepseek-r1-distill-qwen-1.5b-q5km", "qwen3-1.7b-q4km"]
    all_results = {}

    try:
        harness.start_heartbeat(stage, interval=5, max_no_progress_sec=300)
        
        for m in models:
            metrics = test_structured(harness, m)
            all_results[m] = metrics
            
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
