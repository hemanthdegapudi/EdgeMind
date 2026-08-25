# EdgeMind Phase 9 — Pause State
**Paused at:** 2026-08-24 09:52 IST  
**Completed experiments:** 0/6 (EXP-A was running but killed before completion)

## What We Have (Partial EXP-A Data)
- **Thermal timeline:** 880+ seconds of 3-second interval CPU/battery temperature readings
- **Partial inference output:** Model generated ~150-200 tokens of a response about transformers
- **Pre-run memory:** 2486 MiB available
- **Pre-run temps:** All CPU zones 35-37°C, battery 31.5°C
- **Peak temp observed:** 83.8°C at 20-27s (SOFT_HALT logged, then settled to ~62-67°C sustained)
- **NO timing statistics** — llama-cli was killed before it could print `llama_print_timings`

## Key Findings So Far (Useful for Resume)

### 1. `--single-turn` flag still enters chat mode
The raw log shows the interactive chat UI (`> prompt...`) which means `--single-turn` didn't prevent chat template application. The model is running through Qwen's chat template, adding system prompt overhead.

### 2. Model on `/sdcard/` is MUCH slower
The model was moved from `/data/local/tmp/` to `/sdcard/models/` during Phase 0. FUSE-based `/sdcard/` has dramatically worse mmap performance. Inference is running at ~0.4 t/s instead of ~5 t/s.

### 3. `taskset f0` partially works
The process ran, but earlier testing showed CPU 7 (Prime) gets mask `0x5f` not `0xff` from Android's cpuset. Mask `f0` (CPUs 4-7) gets clamped to `0x60` (CPUs 5-6 only) by the intersection with the shell's allowed mask.

### 4. Thermal behavior
- Rapid heat spike to 83.8°C in first 20-27 seconds
- Settled to 62-67°C sustained (thermal throttling kicked in)
- Battery slowly climbed from 31.5°C to 39°C over ~15 minutes
- No HARD_ABORT triggered

## Action Items for Resume

1. **Move model back to `/data/local/tmp/`:**
   ```bash
   adb shell cp /sdcard/models/qwen2.5-3b-instruct-q4_k_m.gguf /data/local/tmp/
   ```
   Then update `MODEL_PATH` in script to `/data/local/tmp/qwen2.5-3b-instruct-q4_k_m.gguf`

2. **Fix chat mode issue** — use `--no-conversation` or pipe prompt via stdin with `echo "prompt" |`

3. **Verify taskset masks** — check actual affinity granted vs requested for each mask

4. **Re-run all 6 experiments from scratch** (partial EXP-A data has no timing stats)

## Files Saved
```
phase9_results/
├── raw_logs/
│   ├── EXP-A_20260824_093727.log      # Partial inference output (no timings)
│   └── EXP-A_20260824_093727.meta     # Pre-run state, command used
├── thermal_logs/
│   └── EXP-A_thermal_timeline.csv     # 880s of thermal data (USEFUL)
├── master.log                          # Full console output
└── RESUME_STATE.md                     # This file
```
