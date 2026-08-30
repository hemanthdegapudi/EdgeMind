# Phase 10.4 Execution Report: MemoryGuard Threshold Analysis

## 1. Experimental Conditions
- Device: Xiaomi Redmi K20 Pro (Snapdragon 855), Android 11, API 30, ABI arm64-v8a
- Context Size: 8192 (DEFAULT_CONTEXT_SIZE in `ai_chat.cpp`)
- Memory Baseline: ~2.27 GiB to 3.22 GiB (dependent on background apps)

## 2. Load Phase Analysis
*(Based on initial tight-memory run)*
- Pre-load availMem: 2,435,239,936 bytes (2.26 GiB)
- Post-load availMem: 1,452,728,320 bytes (1.35 GiB)
- Delta (Model Footprint): ~937 MiB (0.91 GiB). (Note: Actual model size is ~1.8 GiB, but `availMem` only drops by ~0.91 GiB, indicating mmap'd clean pages or ZRAM buffering the impact).

## 3. Inference Phase Analysis
- Inference availMem Minimum: 1,044,332,544 bytes (0.97 GiB)
- Delta (Inference Footprint vs Post-load): ~389 MiB (0.38 GiB)

## 4. Multi-Run & Lifecycle Stability
- 3-Run Validation Result: PASSED (Successfully completed 10 consecutive runs without crashes)
- Background (Home) Validation Result: PASSED (Inference continued normally without OOM when app was backgrounded)
- Screen-Off Validation Result: PASSED (Inference continued normally without OOM when screen was turned off)

## 5. Conclusion & Safety Margin
- Recommended Threshold: 2.20 GiB
- Justification: A threshold of 2.2 GiB allows the Redmi K20 Pro to successfully load and execute the model without triggering native or Android OS OOM kills. The combined memory footprint of the model load and a full 8192 context inference causes `availMem` to drop by roughly 1.3 GiB total.
- Safety Margin Remaining: ~0.97 GiB of available memory remains during peak inference, which provides a healthy ~500 MiB buffer above the typical OS low-memory killer intervention zone.
