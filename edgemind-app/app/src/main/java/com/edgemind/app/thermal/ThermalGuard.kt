package com.edgemind.app.thermal

import android.content.Context
import android.os.PowerManager
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * ThermalGuard — Reactive thermal safety layer for the EdgeMind runtime.
 *
 * Converts Android's abstracted thermal status codes into [ThermalState] values
 * and exposes them as a [StateFlow] for consumption by the inference control plane.
 *
 * ## Signal path
 * ```
 * Android thermal signal
 *         ↓
 * PowerManager.OnThermalStatusChangedListener (API 29)
 *         ↓
 * ThermalState
 *         ↓
 * reactive inference policy (consumed by InferenceForegroundService)
 * ```
 *
 * ## API Compatibility
 * Requires API 29 (Android 10). The edgemind-app minSdk is 33, so no runtime
 * version guard is needed here. All PowerManager.THERMAL_STATUS_* constants
 * are available unconditionally.
 *
 * ## Design note
 * This class does NOT read raw temperature values (°C or milli-degrees).
 * Android's thermal framework deliberately abstracts hardware temperatures into
 * semantic status codes. Using the abstracted API is the correct production
 * approach — raw sysfs thermal zone values are device-specific and
 * unavailable to regular apps.
 *
 * @param context Application context (used to obtain [PowerManager])
 */
class ThermalGuard(context: Context) {

    companion object {
        private const val TAG = "ThermalGuard"
    }

    /**
     * Semantic thermal states for the EdgeMind inference control plane.
     *
     * Mapped from [PowerManager.THERMAL_STATUS_*] constants as follows:
     *
     * | PowerManager constant   | ThermalState  |
     * |-------------------------|---------------|
     * | THERMAL_STATUS_NONE     | SAFE          |
     * | THERMAL_STATUS_LIGHT    | SAFE          |
     * | THERMAL_STATUS_MODERATE | THROTTLE      |
     * | THERMAL_STATUS_SEVERE   | PAUSE         |
     * | THERMAL_STATUS_CRITICAL | CRITICAL      |
     * | THERMAL_STATUS_EMERGENCY| CRITICAL      |
     * | THERMAL_STATUS_SHUTDOWN | CRITICAL      |
     */
    enum class ThermalState {
        /** Device is thermally healthy. Inference may proceed normally. */
        SAFE,

        /**
         * Device is moderately warm. Inference may continue but the service
         * should log a warning and may choose to reduce batch size or thread count.
         */
        THROTTLE,

        /**
         * Device is severely hot. Inference must be paused.
         * The service should call [com.arm.aichat.InferenceEngine.cleanUp] to
         * release the context and reduce thermal load.
         */
        PAUSE,

        /**
         * Device is in a critical, emergency, or pre-shutdown thermal state.
         * Inference must stop immediately.
         * The service should call [com.arm.aichat.InferenceEngine.destroy] and
         * then [android.app.Service.stopSelf].
         */
        CRITICAL
    }

    private val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager

    private val _thermalState = MutableStateFlow(ThermalState.SAFE)

    /**
     * Current thermal state. Emits a new value whenever Android reports a
     * thermal status change. Initial value is derived from the current thermal
     * status at construction time.
     */
    val thermalState: StateFlow<ThermalState> = _thermalState.asStateFlow()

    /** Listener registered with [PowerManager]. Retained to allow unregistration. */
    private val thermalListener = PowerManager.OnThermalStatusChangedListener { status ->
        val newState = mapThermalStatus(status)
        Log.i(TAG, "Thermal status changed: raw=$status → state=$newState")
        _thermalState.value = newState
    }

    init {
        // Poll current status immediately so the initial StateFlow value reflects
        // the actual device state at startup, not a default assumption.
        val currentStatus = powerManager.currentThermalStatus
        _thermalState.value = mapThermalStatus(currentStatus)
        Log.i(TAG, "ThermalGuard initialized. Current status: raw=$currentStatus → state=${_thermalState.value}")

        // Register listener for ongoing changes.
        // PowerManager requires this to be called on the main thread executor.
        powerManager.addThermalStatusListener(thermalListener)
    }

    /**
     * Maps a raw [PowerManager.THERMAL_STATUS_*] integer constant to a [ThermalState].
     *
     * @param status One of the PowerManager.THERMAL_STATUS_* constants (API 29+).
     */
    private fun mapThermalStatus(status: Int): ThermalState = when (status) {
        PowerManager.THERMAL_STATUS_NONE,
        PowerManager.THERMAL_STATUS_LIGHT -> ThermalState.SAFE

        PowerManager.THERMAL_STATUS_MODERATE -> ThermalState.THROTTLE

        PowerManager.THERMAL_STATUS_SEVERE -> ThermalState.PAUSE

        PowerManager.THERMAL_STATUS_CRITICAL,
        PowerManager.THERMAL_STATUS_EMERGENCY,
        PowerManager.THERMAL_STATUS_SHUTDOWN -> ThermalState.CRITICAL

        else -> {
            // Unknown status code from a future API level — treat conservatively as THROTTLE
            // to avoid blocking inference unnecessarily while still acknowledging a non-nominal state.
            Log.w(TAG, "Unknown thermal status code: $status — defaulting to THROTTLE")
            ThermalState.THROTTLE
        }
    }

    /**
     * Unregisters the thermal status listener.
     *
     * Must be called when the owning component (e.g., [android.app.Service]) is destroyed
     * to avoid memory leaks and unnecessary callbacks.
     */
    fun destroy() {
        powerManager.removeThermalStatusListener(thermalListener)
        Log.i(TAG, "ThermalGuard destroyed. Listener unregistered.")
    }
}
