package com.edgemind.app.model

import android.content.Context
import android.util.Log
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import com.edgemind.app.memory.MemoryGuard
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.delay

enum class ModelState {
    UNLOADED, LOADING, READY, GENERATING, UNLOADING, FAILED
}

class ModelManager(
    private val context: Context,
    private val memoryGuard: MemoryGuard
) {
    companion object {
        private const val TAG = "ModelManager"
    }

    private val _engine: InferenceEngine by lazy {
        AiChat.getInferenceEngine(context)
    }

    private val _status = MutableStateFlow(ModelState.UNLOADED)
    val status: StateFlow<ModelState> = _status.asStateFlow()

    private var _activeModel: ModelDefinition? = null
    val activeModel: ModelDefinition? get() = _activeModel

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val mutex = Mutex()

    fun getModelStatus(): ModelState = status.value
    fun getActiveModelDef(): ModelDefinition? = _activeModel
    fun isModelLoaded(): Boolean = status.value == ModelState.READY || status.value == ModelState.GENERATING

    suspend fun loadModel(modelId: String) {
        val modelDef = ModelRegistry.getModelById(modelId)
            ?: throw IllegalArgumentException("Unknown model: $modelId")
        
        mutex.withLock {
            if (_status.value != ModelState.UNLOADED && _status.value != ModelState.FAILED) {
                Log.w(TAG, "Cannot load model, state is ${_status.value}")
                return
            }

            // Memory Check
            val memState = memoryGuard.refresh()
            // Estimate footprint: model file size + 400 MB for KV cache and overhead
            val estimatedFootprint = modelDef.expectedFileSize + (400L * 1024L * 1024L)
            if (!memoryGuard.canLoadModel(estimatedFootprint)) {
                Log.e(TAG, "Memory state INSUFFICIENT ($memState). Cannot load ${modelDef.displayName}.")
                _status.value = ModelState.FAILED
                return
            }

            _status.value = ModelState.LOADING
            try {
                _engine.loadModel(modelDef.modelPath)
                _activeModel = modelDef
                _status.value = ModelState.READY
                
                // Post-load check - just logging, don't enforce pre-load threshold
                val postMem = memoryGuard.refresh()
                Log.i(TAG, "Post-load memory: $postMem")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to load model", e)
                _status.value = ModelState.FAILED
            }
        }
    }

    suspend fun unloadModel() {
        mutex.withLock {
            if (_status.value == ModelState.UNLOADED) return
            _status.value = ModelState.UNLOADING
            try {
                _engine.cleanUp()
                // True Memory Release (Phase 6): trigger GC/native cleanup
                System.gc()
                delay(500) // Give OS a moment to reclaim pages
                memoryGuard.refresh()
            } catch (e: Exception) {
                Log.e(TAG, "Error unloading model", e)
            } finally {
                _activeModel = null
                _status.value = ModelState.UNLOADED
            }
        }
    }

    suspend fun switchModel(modelId: String) {
        if (_activeModel?.id == modelId && _status.value == ModelState.READY) return
        Log.i(TAG, "Switching to model: $modelId")
        unloadModel()
        loadModel(modelId)
    }
    
    fun getEngine(): InferenceEngine = _engine
    
    fun setGeneratingState(generating: Boolean) {
        if (generating && _status.value == ModelState.READY) {
            _status.value = ModelState.GENERATING
        } else if (!generating && _status.value == ModelState.GENERATING) {
            _status.value = ModelState.READY
        }
    }
}
