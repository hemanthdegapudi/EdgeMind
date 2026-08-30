import json
with open("validation/raw/inference_run.json") as f:
    d = json.load(f)

print(f"PID: {d['pid']}")
print(f"PRE: RSS={d['pre_mem'].get('rss_kb')} PSS={d['pre_mem'].get('pss_kb')} MemAvail={d['pre_mem'].get('mem_available_kb')}")
print(f"POST: RSS={d['post_mem'].get('rss_kb')} PSS={d['post_mem'].get('pss_kb')} MemAvail={d['post_mem'].get('mem_available_kb')}")

for line in d['full_log'].splitlines():
    if any(k in line for k in ["MemoryGuard", "JNI", "llama", "CMD_DONE", "CMD_OUTPUT", "Model loaded", "Generating for prompt", "CMD: Generating", "TestReceiver", "InferenceEngine"]):
        print(line)
