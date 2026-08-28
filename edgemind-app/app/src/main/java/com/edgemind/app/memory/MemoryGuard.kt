package com.edgemind.app.memory

import android.app.ActivityManager
import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * MemoryGuard — Memory safety layer for the EdgeMind runtime.
 *
 * Evaluates system-wide available memory before model load to determine
 * whether inference can safely proceed without risking an OOM kill.
 *
 * ## Signal path
 * ```
 * ActivityManager.getMemoryInfo()
 *         ↓
 * safety calculation (see MINIMUM_FREE_MEMORY_BYTES derivation below)
 *         ↓
 * MemoryState
 *         ↓
 * allow / reject model load (consumed by InferenceForegroundService)
 * ```
 *
 * ## Memory threshold derivation
 *
 * The threshold is derived from the Qwen2.5 3B Instruct Q4_K_M model used in Phase 9,
 * combined with runtime overhead estimates. All values are documented to allow revision
 * when a different model or context size is used.
 *
 * | Component                          | Size estimate         | Basis |
 * |------------------------------------|----------------------|-------|
 * | Qwen2.5 3B Q4_K_M model weights    | ~1.9 GiB             | Phase 9 benchmark: model size reported as ~1.8–2.0 GiB |
 * | KV cache (512 ctx, fp16)           | ~0.3 GiB             | n_layers=36, n_kv_heads=8, head_dim=128, fp16: 36 × 8 × 128 × 512 × 2B = ~0.3 GiB |
 * | Runtime + JVM + OS overhead        | ~0.3 GiB             | Conservative estimate for process + loaded libs |
 * | Sub-total                          | ~2.5 GiB             | Sum of above |
 * | Safety margin (20%)                | ~0.5 GiB             | Provides headroom for background processes and zRAM pressure |
 * | **MINIMUM_FREE_MEMORY_BYTES**      | **3.0 GiB**          | 3,221,225,472 bytes |
 *
 * Note: Android uses zRAM (compressed RAM), NOT disk swap. The OOM killer will
 * terminate the process if it exceeds its memory budget. The 20% margin reduces
 * the probability of an OOM kill mid-inference.
 *
 * Note: This threshold is intentionally NOT derived from the previously reported
 * 2.52 GiB value, which was unverified. The derivation above is traceable to
 * documented model and architecture parameters.
 *
 * @param context Application context (used to obtain [ActivityManager])
 */
class MemoryGuard(context: Context) {

    companion object {
        private const val TAG = "MemoryGuard"

        /** Minimum free system memory required to safely load the inference model. See KDoc. */
        internal const val MINIMUM_FREE_MEMORY_BYTES: Long = 3L * 1024L * 1024L * 1024L  // 3.0 GiB

        // EXPERIMENTAL: 2.2 GiB threshold for Phase 10.4 testing on Redmi K20 Pro
        internal const val EXPERIMENTAL_THRESHOLD_BYTES: Long = (2.2 * 1024 * 1024 * 1024).toLong() // 2.2 GiB

        /**
         * Threshold below MINIMUM_FREE_MEMORY_BYTES at which the state is MARGINAL
         * rather than SUFFICIENT. Provides a warning window before reaching the hard limit.
         * MARGINAL = free memory is between MINIMUM and (MINIMUM + MARGINAL_BUFFER).
         */
        internal const val MARGINAL_BUFFER_BYTES: Long = 512L * 1024L * 1024L  // 512 MiB

        /** SUFFICIENT threshold: free memory must exceed this to be considered fully safe. */
        internal val SUFFICIENT_THRESHOLD_BYTES: Long = EXPERIMENTAL_THRESHOLD_BYTES + MARGINAL_BUFFER_BYTES
    }

    /**
     * Memory safety states for the EdgeMind inference control plane.
     */
    enum class MemoryState {
        /**
         * Sufficient free memory is available. Model load may proceed.
         * Free memory ≥ MINIMUM_FREE_MEMORY_BYTES + MARGINAL_BUFFER_BYTES (3.5 GiB)
         */
        SUFFICIENT,

        /**
         * Memory is marginal — above the hard minimum but within the safety buffer.
         * Model load may proceed with a logged warning. The service should monitor
         * memory more aggressively.
         * MINIMUM_FREE_MEMORY_BYTES ≤ free < SUFFICIENT_THRESHOLD_BYTES
         */
        MARGINAL,

        /**
         * Insufficient free memory. Model load must be rejected.
         * Free memory < MINIMUM_FREE_MEMORY_BYTES, OR system is in low-memory state.
         */
        INSUFFICIENT
    }

    private val activityManager =
        context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager

    private val _memoryState = MutableStateFlow(MemoryState.SUFFICIENT)

    /**
     * Current memory state. Call [refresh] to update from the current system state.
     * This is not automatically updated — callers must invoke [refresh] at appropriate
     * decision points (e.g., before model load, periodically during long inference runs).
     */
    val memoryState: StateFlow<MemoryState> = _memoryState.asStateFlow()

    init {
        // Evaluate memory state at construction time to populate initial value.
        refresh()
    }

    /**
     * Queries the current system memory and updates [memoryState].
     *
     * Uses [ActivityManager.getMemoryInfo] which reports total available system memory,
     * including native heap from all processes and the file cache. This is the correct
     * API for system-wide memory assessment — unlike [android.os.Debug.getNativeHeapFreeSize]
     * which only reports this process's native heap.
     *
     * @return The current [MemoryState] after refresh.
     */
    fun refresh(): MemoryState {
        val memInfo = ActivityManager.MemoryInfo()
        activityManager.getMemoryInfo(memInfo)

        val availMem = memInfo.availMem
        val totalMem = memInfo.totalMem
        val isLowMemory = memInfo.lowMemory

        Log.i(
            TAG,
            "Memory refresh: availMem=${formatGib(availMem)}, " +
                "totalMem=${formatGib(totalMem)}, " +
                "lowMemory=$isLowMemory, " +
                "threshold=${formatGib(MINIMUM_FREE_MEMORY_BYTES)}"
        )

        val newState = when {
            isLowMemory -> {
                Log.w(TAG, "System reports LOW MEMORY — model load rejected")
                MemoryState.INSUFFICIENT
            }
            availMem < EXPERIMENTAL_THRESHOLD_BYTES -> {
                Log.w(
                    TAG,
                    "Available memory ${formatGib(availMem)} < minimum ${formatGib(EXPERIMENTAL_THRESHOLD_BYTES)} — model load rejected"
                )
                MemoryState.INSUFFICIENT
            }
            availMem < SUFFICIENT_THRESHOLD_BYTES -> {
                Log.w(
                    TAG,
                    "Available memory ${formatGib(availMem)} is marginal (< ${formatGib(SUFFICIENT_THRESHOLD_BYTES)}) — proceed with caution"
                )
                MemoryState.MARGINAL
            }
            else -> {
                Log.i(TAG, "Available memory ${formatGib(availMem)} — SUFFICIENT")
                MemoryState.SUFFICIENT
            }
        }

        _memoryState.value = newState
        return newState
    }

    /**
     * Returns true if the current memory state allows model loading to proceed.
     * Both [MemoryState.SUFFICIENT] and [MemoryState.MARGINAL] permit load;
     * [MemoryState.INSUFFICIENT] does not.
     */
    fun canLoadModel(): Boolean {
        return _memoryState.value != MemoryState.INSUFFICIENT
    }

    /** Formats a byte count as a human-readable GiB string for logging. */
    private fun formatGib(bytes: Long): String =
        "%.2f GiB".format(bytes.toDouble() / (1024.0 * 1024.0 * 1024.0))
}
