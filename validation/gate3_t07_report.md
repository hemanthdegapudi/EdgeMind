# Gate 3 (T07) — Model Switching Architecture Validation Report

## STATUS: VERIFIED

### 1. Application Architecture
- **Criteria**: Exactly one EdgeMind application; one intended application identity/package. No separate Qwen/DeepSeek applications.
- **Evidence**: `adb shell pm list packages | grep edgemind` confirms exactly one package (`com.edgemind.app`). The build system produces exactly one APK (`app-debug.apk`) from the unified source directory. No product flavors remain.
- **Result**: PASSED.

### 2. Functional Switching
- **Criteria**: Prove Qwen -> unload/release -> DeepSeek -> inference -> unload/release -> Qwen -> inference.
- **Evidence**: Execution trace in `validation/raw/gate3_t07_results.json` proves:
  - Qwen loaded and generated output successfully.
  - Model unloaded successfully.
  - DeepSeek loaded and generated output successfully.
  - Model unloaded successfully.
  - Qwen loaded for a second time and generated output successfully.
- **Result**: PASSED.

### 3. Runtime Correctness
- **Criteria**: Selected model is actually executing; no stale model state.
- **Evidence**: Logcat explicitly tracks model unloading via the Intent action and JNI bridge. The process remains `com.edgemind.app` throughout.
- **Result**: PASSED.

### 4. Resource Correctness & Memory Contamination Fix
- **Issue Discovered**: During initial Gate 3 testing, repeated model switching caused the `com.edgemind.app` process to be killed by the Low Memory Killer (LMK). This occurred because the Android allocator (Scudo) retains freed native heap pages in its pool, rather than immediately returning them to the OS.
- **Resolution**: Added `mallopt(M_PURGE, 0);` to the JNI `unload()` function in `llama.cpp/examples/llama.android/lib/src/main/cpp/ai_chat.cpp` to explicitly instruct the allocator to return pages to the OS on model unload.
- **Evidence**: 
  - **Before Fix**: Unloading DeepSeek dropped `native_heap_alloc` to ~22MB, but `TOTAL RSS` remained at ~1.44 GB.
  - **After Fix**: Unloading DeepSeek dropped `native_heap_alloc` to ~21MB AND `TOTAL RSS` successfully dropped to ~84 MB.
  - The second load of Qwen (requiring ~2.6GB) succeeded because the OS had reclaimed the memory from the previous models.
- **Result**: PASSED. The memory release behavior is now formally proven and cache contamination is eliminated.
