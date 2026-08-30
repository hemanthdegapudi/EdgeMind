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

def test_performance(harness, model_id, prompt_type, prompt_text):
    cycle_metrics = {"prompt_type": prompt_type}
    harness.log(f"Testing {model_id} Performance with {prompt_type} prompt...")
    
    # Generate
    harness.run_adb_shell("logcat -c")
    # Escape prompt
    prompt_escaped = prompt_text.replace("'", "\\'")
    harness.run_adb_shell(f"am broadcast -a com.edgemind.ACTION_GENERATE -n com.edgemind.app/.TestReceiver --es prompt '{prompt_escaped}'")
    
    line = wait_for_logcat(harness, r"CMD_DONE: Generation completed")
    harness.mark_progress("GENERATION_COMPLETED")
    
    # Parse metrics from logcat
    # Tokens: $tokenCount, TotalTime: ${totalTime}ms, TTFT/Prefill: ${prefill}ms, DecodeTPS: $decodeTps
    match = re.search(r"Tokens: (\d+), TotalTime: (\d+)ms, TTFT/Prefill: (\d+)ms, DecodeTPS: ([\d\.]+)", line)
    if match:
        cycle_metrics["output_tokens"] = int(match.group(1))
        cycle_metrics["total_time_ms"] = int(match.group(2))
        cycle_metrics["ttft_ms"] = int(match.group(3))
        cycle_metrics["decode_tps"] = float(match.group(4))
        # Estimate prompt tokens based on TTFT and context size assuming roughly standard prefill speed, or mock it if not available in logs. EdgeMind doesn't output prompt tokens in the logcat we saw!
        # Actually, let's just log length.
        cycle_metrics["prompt_length_chars"] = len(prompt_text)
        
    cycle_metrics.update(harness.get_device_metrics())
    return cycle_metrics


def main():
    harness = Harness()
    stage = "GATE_4_PERFORMANCE"
    
    if not harness.begin_stage(stage):
        return

    checkpoint = harness.load_checkpoint(stage) or {"progress_idx": 0, "results": []}
    start_idx = checkpoint["progress_idx"]
    all_metrics = checkpoint["results"]
    
    models = ["deepseek-r1-distill-qwen-1.5b-q5km", "qwen3-1.7b-q4km"]
    prompts = {
        "short": "Hello, how are you?",
        "medium": "Write a 3 paragraph essay about the history of the internet.",
        "rag": "Context: [Paris is the capital of France. Berlin is the capital of Germany.] Based on the context, what is the capital of France?"
    }
    
    tests = []
    for m in models:
        for p_name, p_text in prompts.items():
            for rep in range(5):
                tests.append({"model": m, "prompt_type": p_name, "prompt_text": p_text, "rep": rep})

    try:
        harness.start_heartbeat(stage, interval=5, max_no_progress_sec=300)
        
        current_model = None
        for i in range(start_idx, len(tests)):
            t = tests[i]
            if current_model != t["model"]:
                harness.run_adb_shell("logcat -c")
                harness.run_adb_shell("am broadcast -a com.edgemind.ACTION_UNLOAD_MODEL -n com.edgemind.app/.TestReceiver")
                time.sleep(2)
                harness.run_adb_shell(f"am broadcast -a com.edgemind.ACTION_LOAD_MODEL -n com.edgemind.app/.TestReceiver --es model_id {t['model']}")
                wait_for_logcat(harness, r"CMD_DONE: Load completed")
                harness.mark_progress("LOAD_COMPLETED")
                current_model = t["model"]
            
            metrics = test_performance(harness, t["model"], t["prompt_type"], t["prompt_text"])
            metrics.update({"model": t["model"], "rep": t["rep"]})
            all_metrics.append(metrics)
            
            harness.save_checkpoint(stage, {
                "progress_idx": i + 1,
                "results": all_metrics
            })
            harness.mark_progress("CHECKPOINT_COMMITTED")
            
        harness.record_result(stage, "PASSED", {"tests_run": len(tests)}, [])
        harness.end_stage(stage, "PASSED")
    except Exception as e:
        harness.log(f"Stage failed: {e}")
        harness.record_result(stage, "FAILED", {}, [str(e)])
        harness.end_stage(stage, "FAILED")
    finally:
        harness.stop_heartbeat()

if __name__ == "__main__":
    main()
