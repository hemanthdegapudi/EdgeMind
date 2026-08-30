# Gate 2.5: Experimental Integrity & Runtime-State Investigation

## STATUS: PASS (with qualifications)
The boundaries of the experiment and the sources of error have been successfully identified. The measurements from Gate 2 are CONFIRMED INVALID due to flawed parsing and incorrect metric selection.

## 1. Why are baseline memory measurements drifting?
The Gate 2 baseline measurements were drifting because they relied exclusively on `MemAvailable` (from `/proc/meminfo`), which measures **system-wide** available memory rather than the memory footprint of the EdgeMind process. `MemAvailable` fluctuates wildly depending on Android background tasks, cached file pages, and OS memory management.

## 2. Why are some "loaded" measurements lower than baseline?
When a model is loaded, the sudden memory pressure often forces Android's Low Memory Killer (lmkd) to evict background processes or drop filesystem caches. If the system frees more background memory than the model consumes, the system-wide `MemAvailable` actually *increases*. Because Gate 2 subtracted `MemAvailable(loaded)` from `MemAvailable(baseline)`, this resulted in a negative delta, incorrectly reported as loaded < baseline.

## 3. Is RSS being parsed correctly?
**NO.** The parsing logic in `get_process_mem()` (used during Gate 2) searched for "Native Heap" in `dumpsys meminfo` and incorrectly hardcoded index 6 as `Native_Heap_Allocated` and index 7 as `Native_Heap_Free`.
Due to the formatting of `dumpsys meminfo`, index 6 is actually the **RSS Total** for the Native Heap, and index 7 is the **Heap Size**. The script completely missed the actual `Native_Heap_Allocated` (index 8) and `Native_Heap_Free` (index 9). Furthermore, it ignored the `TOTAL RSS` field entirely in its final calculation.

## 4. Is PSS being parsed correctly?
The regex for PSS was present in the old script but the values were ignored in the final Gate 2 report, which instead relied entirely on `MemAvailable`.

## 5. Is PID stable?
Yes, across a standard lifecycle trace for DeepSeek, the PID remains stable. However, if LMK kills the process due to extreme memory pressure (which happens frequently with Qwen3), the PID changes on the next start.

## 6. Is the process being restarted?
The process is not restarted during a successful DeepSeek load. However, Qwen3's larger memory footprint frequently triggers a silent restart or timeout if the system is under pressure.

## 7. Is native memory actually released?
**NO.** When `ACTION_UNLOAD_MODEL` is called, `llama.cpp` frees the memory (`Native_Heap_Alloc` drops from 1.98 GB back to ~14 MB). However, the Android allocator (e.g., scudo/jemalloc) retains the pages in its pool.
- `Native_Heap_Free` jumps to 1.58 GB.
- `Native_Heap_Size` remains at 1.59 GB.
- `RSS` remains elevated at 1.44 GB.
The OS does not immediately reclaim these pages until there is global memory pressure. Consequently, a subsequent "baseline" measurement for the same process shows a massive 1.44 GB RSS.

## 8. Is mmap state changing?
Yes. We verified that `.gguf` weights are mmap'd. When unloaded, the `Other mmap` and `Native Heap` states reflect the change, but the physical memory (RSS) is not immediately returned to the OS.

## 9. Is thermal state affecting load?
High `cpu_temp` values dramatically increase load times, and thermal contamination can exacerbate timeout issues, although memory footprint size is the primary cause for Qwen3's timeouts. 

## 10. Is Qwen3 instability model-specific?
**YES.** A controlled reboot test showed that DeepSeek successfully completes 5 out of 5 runs. Qwen3 consistently times out during load, confirming that its 1.7B size creates memory pressure that triggers lmkd on this specific device, regardless of thermal state or prior process state.

## 11. Is the instability runtime-specific?
The memory metric instability is caused by **measurement methodology** and **native allocator caching**, rather than an EdgeMind runtime memory leak. The runtime successfully unloads the model (allocations drop), but the metric (RSS) does not reflect it due to allocator behavior. The Qwen3 load timeout instability is model-specific due to its size on this device.

## 12. Are the current Gate 2 numbers valid?
**NO.** All Gate 2 memory measurements must be discarded. They mixed `MemAvailable` with mis-parsed `Native Heap` columns.

## 13. What changes are required before Gate 3?
1. **Fix Memory Parsing**: Use `TOTAL RSS` and `TOTAL PSS` from `dumpsys meminfo`.
2. **Account for Allocator Caching**: Unloading a model does not drop RSS. To get a clean baseline for a new model, the process **must be killed and restarted**.
3. **Use PID Isolation**: Always verify the PID before and after loading to detect silent LMK restarts.
4. **Thermal Gating**: Reject tests where `cpu_temp` > 45°C.

## FINAL STATUS
**PASS** - The sources of measurement error and lifecycle instability have been successfully identified. Gate 2 numbers are invalid. Gate 3 must NOT proceed until the test harness is updated to kill the process between tests and parse `dumpsys` correctly.
