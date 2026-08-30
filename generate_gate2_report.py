import json
import os
import glob
from collections import defaultdict
from statistics import mean, median

VALIDATION_DIR = "/home/tilaksijju/Documents/EdgeMind/validation/performance"
RESULTS_FILE = os.path.join(VALIDATION_DIR, "gate2_results.json")
REPORT_FILE = os.path.join(VALIDATION_DIR, "gate2_report.md")
RAW_DIR = os.path.join(VALIDATION_DIR, "raw", "gate2")

def main():
    if not os.path.exists(RESULTS_FILE):
        print("Results file not found.")
        return

    with open(RESULTS_FILE, "r") as f:
        results = json.load(f)

    if not results:
        print("No results found.")
        return

    # Group by model
    model_data = defaultdict(list)
    for r in results:
        model_data[r["model_id"]].append(r)

    report_lines = []
    
    # Check overall status
    status = "PASS"
    for r in results:
        if r.get("status") != "SUCCESS":
            status = "FAIL"

    report_lines.append("# GATE 2 — INDEPENDENT MODEL LOAD / INFERENCE BASELINE")
    report_lines.append("")
    report_lines.append(f"**STATUS**: {status}")
    report_lines.append("")

    report_lines.append("## Test Environment Summary")
    report_lines.append("- Device: Redmi K20 Pro")
    report_lines.append("- Context Size Configuration: 2048")
    report_lines.append("- Prompt: 'What is the capital of France? Answer in one word.' (Fixed short prompt to prevent timeouts)")
    report_lines.append("- Repetitions: 5 per model")
    report_lines.append("")

    def bytes_to_mb(b): return round(b / 1024, 2)

    model_names = {
        "deepseek-r1-distill-qwen-1.5b-q5km": "Model A (DeepSeek-R1-Distill-Qwen-1.5B Q5_K_M)",
        "qwen3-1.7b-q4km": "Model B (Qwen3-1.7B Q4_K_M)"
    }

    comparative = {}

    for model_id, runs in model_data.items():
        name = model_names.get(model_id, model_id)
        report_lines.append(f"## {name} Profile")
        
        # Averages
        mem_baselines = []
        mem_loaded = []
        mem_post_gen = []
        ttfts = []
        tps = []
        peak_temps = []
        load_times = []
        
        for r in runs:
            if r.get("status") != "SUCCESS": continue
            # Memory Available in kB
            mb = r["baseline_metrics"]["MemAvailable"]
            ml = r["load_metrics"]["MemAvailable"]
            mpg = r["post_generation_metrics"]["MemAvailable"]
            mem_baselines.append(mb)
            mem_loaded.append(ml)
            mem_post_gen.append(mpg)
            
            inf = r["inference_metrics"]
            if inf:
                ttfts.append(inf["ttft"])
                tps.append(inf["decode_tps"])
                
            # Temps
            temps = [m["thermals"].get("cpu-1-0-usr", 0) for m in r["generation_metrics"]]
            if not temps:
                temps = [r["post_generation_metrics"]["thermals"].get("cpu-1-0-usr", 0)]
            peak_temps.append(max(temps) if temps else 0)
            
            load_times.append(r["unload_metrics"].get("load_duration_ms", 0))

        avg_mb = bytes_to_mb(mean(mem_baselines)) if mem_baselines else 0
        avg_ml = bytes_to_mb(mean(mem_loaded)) if mem_loaded else 0
        avg_mpg = bytes_to_mb(mean(mem_post_gen)) if mem_post_gen else 0
        
        avg_ttft = mean(ttfts) if ttfts else 0
        avg_tps = mean(tps) if tps else 0
        avg_peak_temp = mean(peak_temps) / 1000.0 if peak_temps else 0
        avg_load_time = mean(load_times) if load_times else 0

        comparative[model_id] = {
            "tps": avg_tps,
            "ttft": avg_ttft,
            "mem_used": avg_mb - avg_ml,
            "load_time": avg_load_time
        }

        report_lines.append("### Memory Footprint")
        report_lines.append(f"- Baseline MemAvailable: {avg_mb} MB")
        report_lines.append(f"- Loaded MemAvailable: {avg_ml} MB (Consumed ~{round(avg_mb - avg_ml, 2)} MB)")
        report_lines.append(f"- Post-Generation MemAvailable: {avg_mpg} MB")
        report_lines.append("")
        
        report_lines.append("### Performance")
        report_lines.append(f"- Load Time average: {avg_load_time:.0f} ms")
        report_lines.append(f"- Time-To-First-Token (TTFT) average: {avg_ttft:.0f} ms")
        report_lines.append(f"- Decode Speed (Tokens/sec) average: {avg_tps:.2f} tokens/sec")
        report_lines.append("")
        
        report_lines.append("### Thermals")
        report_lines.append(f"- Peak Thermal Temperature during active generation: {avg_peak_temp:.1f} °C")
        report_lines.append("")

    report_lines.append("## Comparative Analysis")
    m_a = comparative.get("deepseek-r1-distill-qwen-1.5b-q5km", {})
    m_b = comparative.get("qwen3-1.7b-q4km", {})
    
    if m_a and m_b:
        tps_diff = m_a['tps'] - m_b['tps']
        tps_winner = "Model A" if tps_diff > 0 else "Model B"
        ttft_diff = m_b['ttft'] - m_a['ttft']
        ttft_winner = "Model A" if ttft_diff > 0 else "Model B"
        mem_diff = m_b['mem_used'] - m_a['mem_used']
        mem_winner = "Model A" if mem_diff > 0 else "Model B"
        
        report_lines.append(f"- **Decode Speed**: {tps_winner} is faster by {abs(tps_diff):.2f} tokens/sec.")
        report_lines.append(f"- **TTFT**: {ttft_winner} is faster by {abs(ttft_diff):.0f} ms.")
        report_lines.append(f"- **Memory**: {mem_winner} uses {abs(mem_diff):.2f} MB less RAM.")
    else:
        report_lines.append("Insufficient data for comparison.")
    report_lines.append("")

    report_lines.append("## Operator Interventions")
    report_lines.append("- Required manual device unlocking and explicit service starting due to MIUI broadcast restrictions and lock screen constraints.")
    report_lines.append("- Shortened prompt generation to 64 tokens max to comply with strict 120s timeout requirements.")
    report_lines.append("")

    report_lines.append("## File Paths")
    report_lines.append(f"- **Raw Logs**: `{RAW_DIR}`")
    report_lines.append(f"- **JSON Results**: `{RESULTS_FILE}`")
    report_lines.append(f"- **This Report**: `{REPORT_FILE}`")

    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(report_lines))

    print(f"Report generated at {REPORT_FILE}")

if __name__ == "__main__":
    main()
