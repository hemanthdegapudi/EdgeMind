package com.edgemind.app

import android.app.Application
import android.util.Log
import com.edgemind.app.memory.MemoryGuard
import com.edgemind.app.model.ModelManager
import com.edgemind.app.thermal.ThermalGuard

/**
 * EdgeMindApplication — Application-level lifecycle host for the EdgeMind runtime.
 *
 * ## Responsibilities
 * - Initializes application-level singletons: [ThermalGuard] and [MemoryGuard].
 * - Provides a well-defined access point for guards, consumed by [com.edgemind.app.service.InferenceForegroundService].
 *
 * ## What this class does NOT do
 * - Does NOT auto-start [com.edgemind.app.service.InferenceForegroundService].
 *   The service is started on demand (e.g., by an intent from an external controller,
 *   or by the user's interaction in future phases).
 * - Does NOT initialize the [com.arm.aichat.InferenceEngine] (that is the service's responsibility,
 *   after guard state verification).
 * - Does NOT perform network operations, database access, or any other unrelated initialization.
 *
 * ## Guard initialization order
 * 1. [ThermalGuard]: registers a thermal listener with [android.os.PowerManager].
 *    Must be initialized before the service starts, so the initial thermal state is
 *    known from the moment inference is requested.
 * 2. [MemoryGuard]: performs a one-time memory snapshot at init. The service calls
 *    [MemoryGuard.refresh] again immediately before model load for the freshest reading.
 *
 * ## Duplicate initialization prevention
 * Guards are initialized as `lateinit` properties set exactly once in [onCreate].
 * Android guarantees [onCreate] is called exactly once per process lifetime.
 */
class EdgeMindApplication : Application() {

    companion object {
        private const val TAG = "EdgeMindApplication"
    }

    /** Thermal safety monitor. Initialized once; consumed by [com.edgemind.app.service.InferenceForegroundService]. */
    lateinit var thermalGuard: ThermalGuard
        private set

    /** Memory safety evaluator. Initialized once; consumed by [com.edgemind.app.service.InferenceForegroundService]. */
    lateinit var memoryGuard: MemoryGuard
        private set

    /** Model manager. Initialized once; consumed by [com.edgemind.app.service.InferenceForegroundService]. */
    lateinit var modelManager: ModelManager
        private set

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "EdgeMindApplication starting")

        // Initialize ThermalGuard first — registers the PowerManager listener immediately,
        // ensuring no thermal events are missed during startup.
        thermalGuard = ThermalGuard(applicationContext)
        Log.i(TAG, "ThermalGuard initialized. Initial state: ${thermalGuard.thermalState.value}")

        // Initialize MemoryGuard — performs initial memory snapshot.
        memoryGuard = MemoryGuard(applicationContext)
        Log.i(TAG, "MemoryGuard initialized. Initial state: ${memoryGuard.memoryState.value}")

        modelManager = com.edgemind.app.model.ModelManager(applicationContext, memoryGuard)
        Log.i(TAG, "ModelManager initialized.")

        Log.i(TAG, "EdgeMindApplication initialization complete")
    }

    override fun onTerminate() {
        // onTerminate() is NOT called on real devices — it is only called in the emulator.
        // Resource cleanup must happen in the service's onDestroy() and guard.destroy() calls.
        // ThermalGuard.destroy() is not called here for that reason.
        // Included for completeness in emulator/test scenarios.
        Log.i(TAG, "EdgeMindApplication terminating (emulator only)")
        thermalGuard.destroy()
        super.onTerminate()
    }
}
