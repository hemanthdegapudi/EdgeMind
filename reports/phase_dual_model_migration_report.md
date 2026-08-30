# EdgeMind Phase Dual-Model Migration Report

## 1. Existing Architecture Findings
- **Model**: `qwen2.5-3b-instruct-q4_k_m.gguf` (2104932768 bytes, SHA256: 626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d)
- **Deployment**: Single model loaded directly by `InferenceForegroundService.kt`. No UI inside `edgemind-app`.
- **MemoryGuard**: Static threshold of 2.2 GiB (recently calibrated to 2.5 GiB).
- **llama.cpp**: Tag b10588 (commit 70adb1b4cea5ee39f867792c78dc59320921eda7).
- **Issue**: The 3B model footprint (~1.8 GiB) brings `availMem` dangerously close to the 2.4 GiB LMKD threshold on the Snapdragon 855 with 6GB RAM.

## 2. Migration Execution
- **Removed**: Deleted the old 3B model and uninstalled the service to free space.
- **Downloaded**: 
  - `DeepSeek-R1-Distill-Qwen-1.5B-Q5_K_M.gguf` (unsloth)
  - `Qwen3-1.7B-Q4_K_M.gguf` (ggml-org)
- **Added `ModelManager`**: Introduced a centralized model manager supporting load, unload, and switch operations. Validates memory dynamically against `MemoryGuard` by estimating model footprint.
- **Added `ChatActivity`**: Created an Android UI inside `edgemind-app` with a spinner for selecting models. Enforces UI safety by preventing user actions while states are `LOADING`, `UNLOADING`, or `GENERATING`.
- **Chat History (Semantics)**: Retained a bounded chat history using a conservative template `<|im_start|>user/assistant...` for proper generation across switches.
- **True Memory Release**: Verified memory clears via `engine.cleanUp()` combined with JVM `System.gc()` delays when unloading.
- **API Extension**: Added a `jsonMode` parameter to `InferenceEngine` APIs ensuring future compatibility with Qwen3's tool-calling capabilities.

## 3. Admission Logic Rework
- The hardcoded static `MINIMUM_FREE_MEMORY_BYTES` check was reworked to dynamically compute `expectedFootprint + 300MB`.
- A post-load check ensures memory does not dangerously dip below limits *after* the JNI mmap loading sequence completes.

## 4. Test Infrastructure
- Added `phase13_memory_test.sh`, `phase14_thermal_test.sh`, and `phase15_switch_test.sh` for on-device QA regression testing.

## 5. Conclusion
The dual-model migration is structurally complete. The user interface allows seamless model switching while ensuring device safety margins are fully defended through active tracking of LMKD limits.
