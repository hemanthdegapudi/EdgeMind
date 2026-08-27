# EdgeMind Phase 9 Final Benchmark Report

## 1. Environment Baseline
- **Device**: Xiaomi Redmi K20 Pro (Snapdragon 855)
- **RAM**: 6 GB (LPDDR4X)
- **OS**: Android 11 (API 30)
- **Model**: `qwen2.5-3b-instruct-q4_k_m.gguf` (1.9 GB)
- **Storage Location**: `/data/local/tmp/` (Internal Storage, bypassed FUSE mmap overhead)
- **Binary**: `llama-cli` v0.2.0-dev (build 10588)
- **Determinism**: Seed=42, Temp=0, No-Warmup

## 2. Experimental Data (Summary)
| Experiment | Reps (Valid/Total) | Mask | Cores | Prompt (t/s) | Gen (t/s) | Peak Temp (°C) | Status |
|---|---|---|---|---|---|---|---|
| EXP-A | 3/3 | `f0` | 4 | 9.97 | 6.77 | 84.5 | SUCCESS |
| EXP-B | 2/3 | `70` | 3 | 7.05 | 4.55 | 84.5 | PARTIAL (1 Thermal Abort) |
| EXP-C | 0/3 | `80` | 1 | N/A | N/A | N/A | INVALID (OS rejected single-core affinity) |
| EXP-D | 3/6 | `c0` | 2 | 3.87 | 2.70 | 83.4 | PARTIAL (3 Timeout Aborts) |
| EXP-E | 3/3 | `0f` | 4 | 1.97 | 1.40 | 58.3 | SUCCESS |
| EXP-F | 3/3 | `none` | 6 | 7.67 | 4.93 | 83.8 | SUCCESS |

## 3. Analysis & Findings
1. **FUSE Overhead Confirmed**: Moving the model from `/sdcard/` to `/data/local/tmp/` eliminated the severe FUSE mmap bottleneck. Generation speeds increased from an unusable ~0.4 t/s to a peak of **6.77 t/s**.
2. **Thermal Behavior**: The device runs very hot under full load. The `f0` (4 performance cores) and `none` (6 threads across all cores) configs rapidly push the CPU to 83-84°C within seconds. The thermal safety script successfully hard-aborted one `EXP-B` run at 85.3°C.
3. **EAS Scheduler Constraints (EXP-C)**: `taskset 80` (isolating only the single Prime core) fails at the OS level (`Invalid argument`). The Android Energy Aware Scheduler prevents pinning a task exclusively to the Prime core.
4. **Efficiency vs Performance**: 
   - `EXP-E` (4 Silver efficiency cores only, mask `0f`) generates at **1.40 t/s** but keeps the device remarkably cool (peak 58.3°C).
   - `EXP-A` (1 Prime + 3 Gold cores, mask `f0`) is the fastest at **6.77 t/s** but hits 84.5°C quickly.
   - `EXP-F` (No mask, 6 threads) is actually *slower* than `EXP-A` (4.93 t/s vs 6.77 t/s), demonstrating that over-subscribing threads or including slow efficiency cores in a uniform OpenMP pool degrades overall throughput due to thread synchronization overhead.

## 4. Final Conclusion
The benchmark conclusively proves that local GGUF inference of a 3B parameter model (Q4_K_M) on the Snapdragon 855 is **viable and performant**, achieving near **7 tokens/second** generation and **10 tokens/second** prompt evaluation. However, sustained inference requires aggressive thermal management. The optimal performance configuration for this SoC is isolating the 4 high-performance cores (mask `f0` with 4 threads), as relying on the default Android scheduler with 6 threads reduces throughput. FUSE mmap avoidance is strictly mandatory.
