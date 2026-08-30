package com.edgemind.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import com.edgemind.app.EdgeMindApplication
import com.edgemind.app.memory.MemoryGuard
import com.edgemind.app.thermal.ThermalGuard
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * InferenceForegroundService — Android foreground service hosting the EdgeMind inference lifecycle.
 *
 * ## Responsibilities
 * - Elevates the EdgeMind process to foreground service priority, reducing OOM kill probability.
 * - Manages the [InferenceEngine] lifecycle: initialization, model load gating, and cleanup.
 * - Observes [ThermalGuard] and responds to thermal state changes with appropriate actions.
 * - Observes [MemoryGuard] before model load to reject unsafe load attempts.
 *
 * ## Process priority note
 * A foreground service improves this process's position in Android's OOM kill priority hierarchy.
 * It does NOT guarantee immunity from termination under severe, sustained memory pressure.
 * The notification is a system requirement; it is also a user-visible signal that inference
 * is active and consuming resources.
 *
 * ## Service lifecycle
 * ```
 * startForegroundService(Intent)
 *         ↓
 * onStartCommand → startForeground(notification)
 *         ↓
 * initialize guards + engine
 *         ↓
 * observe ThermalGuard  ←──────────────────────────────────────┐
 *         ├── SAFE / THROTTLE → continue (THROTTLE logs warning)  │
 *         ├── PAUSE          → cleanUp() engine                   │
 *         └── CRITICAL       → destroy() engine + stopSelf() ─────┘
 *
 * stopSelf() / stopService()
 *         ↓
 * onDestroy → destroy engine + unregister guards
 * ```
 *
 * ## Boot recovery
 * RECEIVE_BOOT_COMPLETED is NOT declared. Boot recovery is deferred to a future phase.
 * If implemented, the path would be:
 *   BOOT_COMPLETED → BootReceiver → startForegroundService(InferenceForegroundService)
 */
class InferenceForegroundService : Service() {

    companion object {
        private const val TAG = "InferenceForegroundService"

        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "edgemind_inference_channel"
        private const val CHANNEL_NAME = "EdgeMind Inference"
    }

    // Coroutine scope for this service's observation work.
    // SupervisorJob ensures that a failure in one child does not cancel the whole scope.
    private val serviceScope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    private lateinit var engine: InferenceEngine
    private lateinit var thermalGuard: ThermalGuard
    private lateinit var memoryGuard: MemoryGuard

    // Track whether the engine has been initialized, to guard cleanup calls.
    @Volatile private var engineInitialized = false

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "InferenceForegroundService created")

        // Obtain guards from application-level singletons.
        val app = application as EdgeMindApplication
        thermalGuard = app.thermalGuard
        memoryGuard = app.memoryGuard
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "onStartCommand: starting foreground service")

        // MUST call startForeground() before any long-running work.
        // On Android 14+, failing to call this promptly results in a ForegroundServiceStartNotAllowedException.
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())

        // Initialize the inference engine asynchronously.
        serviceScope.launch {
            initializeEngine()
            startThermalObserver()
        }

        // START_STICKY: if the service is killed, Android will restart it with a null intent.
        // This is appropriate for a long-running inference service.
        return START_STICKY
    }

    /**
     * Initializes the inference engine after verifying memory safety.
     */
    private suspend fun initializeEngine() {
        // Refresh memory state before any model operations.
        val memState = memoryGuard.refresh()
        Log.i(TAG, "Memory state before engine init: $memState")

        if (!memoryGuard.canLoadModel()) {
            Log.e(
                TAG,
                "Memory state is INSUFFICIENT (${memState}). " +
                    "Engine initialization deferred — model load rejected. " +
                    "Minimum required: 3.0 GiB free. " +
                    "Service will remain running in standby until memory improves."
            )
            // Schedule a retry after a delay to re-attempt initialization when memory may improve.
            serviceScope.launch {
                kotlinx.coroutines.delay(30_000L) // 30 seconds
                Log.i(TAG, "Retrying engine initialization after memory retry delay")
                initializeEngine()
            }
            // Do not stop the service — it remains in standby. Clients can re-trigger
            // initialization by sending a new intent when conditions improve.
            return
        }

        try {
            Log.i(TAG, "Initializing InferenceEngine via AiChat factory")
            engine = AiChat.getInferenceEngine(applicationContext)
            engineInitialized = true
            Log.i(TAG, "InferenceEngine initialized. State: ${engine.state.value}")
            
            // Phase 10.4 test instrumentation removed for Dual-Model migration.
            // Model loading and inference is now driven by ChatActivity via ModelManager.
        } catch (e: UnsatisfiedLinkError) {
            Log.e(TAG, "Failed to load native library — JNI bridge unavailable", e)
            // Do not crash the service; report the failure but stay alive for diagnosis.
            engineInitialized = false
        } catch (e: Exception) {
            Log.e(TAG, "Unexpected error during engine initialization", e)
            engineInitialized = false
        }
    }

    /**
     * Observes [ThermalGuard.thermalState] and applies the corresponding inference policy.
     *
     * Runs for the lifetime of the service scope.
     */
    private fun startThermalObserver() {
        serviceScope.launch {
            // StateFlow guarantees distinct emission by contract — no distinctUntilChanged() needed.
            thermalGuard.thermalState.collect { state ->
                Log.i(TAG, "Thermal state → $state")
                applyThermalPolicy(state)
            }
        }
    }

    /**
     * Applies the inference policy corresponding to the given [ThermalGuard.ThermalState].
     */
    private fun applyThermalPolicy(state: ThermalGuard.ThermalState) {
        when (state) {
            ThermalGuard.ThermalState.SAFE -> {
                Log.d(TAG, "Thermal: SAFE — inference may proceed normally")
                // No action required.
            }

            ThermalGuard.ThermalState.THROTTLE -> {
                Log.w(
                    TAG,
                    "Thermal: THROTTLE — device is moderately warm. " +
                        "Inference continues. Monitor for escalation."
                )
                // Inference continues. Future enhancement: reduce n_threads or batch size.
                // The InferenceEngineImpl currently uses sysconf(_SC_NPROCESSORS_ONLN) - 2 threads.
                // Thread count reduction would require a JNI extension — not implemented in Phase 10.
            }

            ThermalGuard.ThermalState.PAUSE -> {
                Log.w(TAG, "Thermal: PAUSE — device severely hot. Releasing inference context.")
                if (engineInitialized) {
                    try {
                        // cleanUp() unloads the model and releases the llama context,
                        // freeing the largest memory and compute consumers.
                        // The engine transitions to Initialized state (not Uninitialized),
                        // allowing model reload when temperature recovers.
                        engine.cleanUp()
                        Log.i(TAG, "Inference context released due to PAUSE thermal state")
                    } catch (e: Exception) {
                        Log.e(TAG, "Error during thermal-triggered cleanUp()", e)
                    }
                }
            }

            ThermalGuard.ThermalState.CRITICAL -> {
                Log.e(
                    TAG,
                    "Thermal: CRITICAL — device in critical/emergency/shutdown thermal state. " +
                        "Destroying engine and stopping service."
                )
                if (engineInitialized) {
                    try {
                        engine.destroy()
                        Log.i(TAG, "Engine destroyed due to CRITICAL thermal state")
                    } catch (e: Exception) {
                        Log.e(TAG, "Error during thermal-triggered destroy()", e)
                    } finally {
                        engineInitialized = false
                    }
                }
                // Stop the service to release all resources.
                stopSelf()
            }
        }
    }

    override fun onDestroy() {
        Log.i(TAG, "InferenceForegroundService destroying")

        // Cancel all coroutines in this service's scope.
        serviceScope.cancel()

        // Destroy the engine if it was successfully initialized.
        if (engineInitialized) {
            try {
                engine.destroy()
                Log.i(TAG, "Engine destroyed on service destroy")
            } catch (e: Exception) {
                Log.e(TAG, "Error destroying engine on service destroy", e)
            } finally {
                engineInitialized = false
            }
        }

        super.onDestroy()
    }

    /**
     * This service does not support binding.
     * Future phases may expose a bound interface for direct inference calls
     * from an Activity or other component.
     */
    override fun onBind(intent: Intent?): IBinder? = null

    // ── Notification infrastructure ─────────────────────────────────────────

    /**
     * Creates the notification channel required for foreground service notifications on API 26+.
     * Safe to call multiple times — [NotificationManager.createNotificationChannel] is idempotent.
     */
    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            CHANNEL_NAME,
            NotificationManager.IMPORTANCE_LOW  // LOW: no sound/vibration; appropriate for background compute
        ).apply {
            description = "Indicates that EdgeMind inference is active"
        }
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.createNotificationChannel(channel)
    }

    /**
     * Builds the foreground service notification.
     *
     * Uses a minimal notification — no large icon, no actions — appropriate for a
     * headless inference service with no user-interactive components.
     */
    private fun buildNotification(): Notification =
        Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("EdgeMind")
            .setContentText("Local inference runtime is active")
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setOngoing(true)  // Prevents user dismissal while service is running
            .build()
}
