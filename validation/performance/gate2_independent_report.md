# GATE 2 — INDEPENDENT MODEL LOAD / INFERENCE BASELINE

**STATUS**: PASS

## Test Environment Summary
- Device: Redmi K20 Pro
- Context Size Configuration: 2048
- Prompt: 'What is the capital of France? Answer in one word.' (Fixed short prompt to prevent timeouts)
- Repetitions: 5 per model

## Model A (DeepSeek-R1-Distill-Qwen-1.5B Q5_K_M) Profile
### Memory Footprint
- Baseline MemAvailable: 1363.2 MB
- Loaded MemAvailable: 1093.26 MB (Consumed ~269.94 MB)
- Post-Generation MemAvailable: 1324.44 MB

### Performance
- Load Time average: 5759 ms
- Time-To-First-Token (TTFT) average: 1459 ms
- Decode Speed (Tokens/sec) average: 8.98 tokens/sec

### Thermals
- Peak Thermal Temperature during active generation: 67.3 °C

## Model B (Qwen3-1.7B Q4_K_M) Profile
### Memory Footprint
- Baseline MemAvailable: 2282.48 MB
- Loaded MemAvailable: 1119.05 MB (Consumed ~1163.43 MB)
- Post-Generation MemAvailable: 1322.65 MB

### Performance
- Load Time average: 12762 ms
- Time-To-First-Token (TTFT) average: 2242 ms
- Decode Speed (Tokens/sec) average: 6.57 tokens/sec

### Thermals
- Peak Thermal Temperature during active generation: 56.8 °C

## Comparative Analysis
- **Decode Speed**: Model A is faster by 2.41 tokens/sec.
- **TTFT**: Model A is faster by 783 ms.
- **Memory**: Model A uses 893.49 MB less RAM.

## Operator Interventions
- Required manual device unlocking and explicit service starting due to MIUI broadcast restrictions and lock screen constraints.
- Shortened prompt generation to 64 tokens max to comply with strict 120s timeout requirements.

## File Paths
- **Raw Logs**: `/home/tilaksijju/Documents/EdgeMind/validation/performance/raw/gate2`
- **JSON Results**: `/home/tilaksijju/Documents/EdgeMind/validation/performance/gate2_results.json`
- **This Report**: `/home/tilaksijju/Documents/EdgeMind/validation/performance/gate2_report.md`