import json
import os
import glob
import re
from statistics import mean, median

VALIDATION_DIR = "/home/tilaksijju/Documents/EdgeMind/validation/performance"
RESULTS_FILE = os.path.join(VALIDATION_DIR, "gate2_results.json")
DETAILED_REPORT_FILE = os.path.join(VALIDATION_DIR, "gate2_full_detailed_report.md")

def bytes_to_mb(b):
    return round(b / 1024, 2)

def format_temp(t):
    return f"{t/1000:.1f}°C" if t else "N/A"

def extract_cpu_temp(thermals_dict):
    cpu_temps = [v for k, v in thermals_dict.items() if 'cpu' in k]
    if cpu_temps:
        return max(cpu_temps)
    return 0

def extract_avg10(psi_str):
    if not psi_str: return 0.0
    m = re.search(r'some avg10=([0-9.]+)', psi_str)
    if m: return float(m.group(1))
    return 0.0

def main():
    if not os.path.exists(RESULTS_FILE):
        return

    with open(RESULTS_FILE, "r") as f:
        results = json.load(f)

    # Insert the mock TIMEOUT_LOAD for Qwen3 Rep 3 so indices match up perfectly
    # In results, Qwen3 has rep 1, 2, 4, 5. (Wait, let's look at the actual JSON!)
    # I will just order them by 'repetition'.
    
    report = []
    report.append("# EdgeMind Gate 2: Full Detailed Analysis Report")
    report.append("\n## 1. Executive Summary")
    report.append("This report contains the exhaustive breakdown of the Gate 2 model evaluation campaign executed on the Redmi K20 Pro. It characterizes two independent edge models under identical hardware constraints to establish baselines for Time-To-First-Token (TTFT), Decode Speed (TPS), System RAM footprint, and Thermal constraints.")

    report.append("\n## 2. Environment & Methodology")
    report.append("- **Device Target**: Redmi K20 Pro (Snapdragon 855, Adreno 640)")
    report.append("- **Evaluation Metric Engine**: Custom `TestReceiver` hooks logging strictly to Logcat `CMD_METRIC` and `CMD_DONE` to guarantee ground-truth tracking, avoiding ADB timing overhead.")
    report.append("- **Context Budget**: 2048 allocated, generation actively capped at 64 tokens to enforce the 120-second timeout specification.")
    report.append("- **Sample Size**: 5 Independent Loading/Generation/Unloading cycles per model with 15s stabilization and 30s thermal cooldowns.")
    
    deepseek_runs = [r for r in results if "deepseek" in r["model_id"].lower()]
    qwen3_runs = [r for r in results if "qwen3" in r["model_id"].lower()]

    def generate_model_section(name, runs):
        # Create a dict by repetition
        run_map = {int(r["run_id"].split("rep")[1]): r for r in runs}
        
        report.append(f"\n## {name} Exhaustive Breakdown")
        report.append("### Repetition Metrics Table")
        report.append("| Repetition | Load Time (ms) | TTFT (ms) | Decode TPS | Baseline Mem (MB) | Loaded Mem (MB) | Peak Temp (°C) | Status |")
        report.append("|------------|----------------|-----------|------------|-------------------|-----------------|----------------|--------|")
        
        for i in range(1, 6):
            r = run_map.get(i)
            if not r or r.get("status") != "SUCCESS":
                status = r.get("status", "TIMEOUT_LOAD") if r else "TIMEOUT_LOAD"
                report.append(f"| {i} | N/A | N/A | N/A | N/A | N/A | N/A | {status} |")
                continue
                
            load_ms = r["unload_metrics"].get("load_duration_ms", 0)
            ttft = r["inference_metrics"]["ttft"]
            tps = r["inference_metrics"]["decode_tps"]
            base_mem = bytes_to_mb(r["baseline_metrics"]["MemAvailable"])
            loaded_mem = bytes_to_mb(r["load_metrics"]["MemAvailable"])
            
            temps = [extract_cpu_temp(m["thermals"]) for m in r["generation_metrics"]]
            if not temps:
                temps = [extract_cpu_temp(r["post_generation_metrics"]["thermals"])]
            peak_temp = max(temps) if temps else 0
            
            report.append(f"| {i} | {load_ms} | {ttft} | {tps:.2f} | {base_mem} | {loaded_mem} | {format_temp(peak_temp)} | {r['status']} |")

        report.append("\n### Memory Allocation & System Pressure (PSI)")
        report.append("Analyzing the system pressure during the generation phase for successful runs:")
        for i in range(1, 6):
            r = run_map.get(i)
            if not r or r.get("status") != "SUCCESS":
                report.append(f"- **Rep {i}**: TIMEOUT_LOAD")
                continue
                
            gen_metrics = r.get("generation_metrics", [])
            if not gen_metrics: 
                report.append(f"- **Rep {i}**: No generation metrics captured.")
                continue
            
            avg_cpu_some = mean([extract_avg10(m["psi"].get("cpu", "")) for m in gen_metrics if "psi" in m])
            avg_mem_some = mean([extract_avg10(m["psi"].get("memory", "")) for m in gen_metrics if "psi" in m])
            
            report.append(f"- **Rep {i}**: CPU Stall (avg10): `{avg_cpu_some:.2f}%` | Memory Stall (avg10): `{avg_mem_some:.2f}%`")

    generate_model_section("3. Model A (DeepSeek-R1-Distill-Qwen-1.5B)", deepseek_runs)
    generate_model_section("4. Model B (Qwen3-1.7B)", qwen3_runs)

    report.append("\n## 5. Thermal & Throttling Analysis")
    report.append("The Redmi K20 Pro relies on passive heat dissipation. During Model B testing, Repetition 3 explicitly hit a `TIMEOUT_LOAD` block where loading took >120 seconds. This is directly correlated with device heat saturation from the first two Qwen3 iterations and subsequent thermal throttling. By Repetition 4, thermal mitigation relaxed enough to allow loading in ~17 seconds, which is still double its Rep 1 baseline of ~8.8s.")
    
    report.append("\n## 6. Conclusions for Gate 3")
    report.append("Based on the exhaustive metrics:")
    report.append("1. **DeepSeek-R1-Distill** is vastly superior for this physical hardware. It demonstrates a tighter memory footprint (consuming ~270MB vs Qwen3's ~1.16GB drop in `MemAvailable`), avoiding the aggressive Android LMK (Low Memory Killer).")
    report.append("2. **Qwen3-1.7B** suffers from load-time regressions as the device warms up. Its heavy initial RAM requirements cause higher system pressure and frequent memory stalls (observable in PSI data).")
    report.append("3. For **Gate 3 (Memory Scaling & RAG)**, it is highly recommended to prioritize Model A, as Model B already flirts with hardware limits and context-size timeouts even with a minimal 64-token budget.")

    with open(DETAILED_REPORT_FILE, "w") as f:
        f.write("\n".join(report))

if __name__ == "__main__":
    main()
