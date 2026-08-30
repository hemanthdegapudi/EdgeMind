package com.edgemind.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.edgemind.app.model.ModelManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class TestReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val app = context.applicationContext as EdgeMindApplication
        val manager = app.modelManager
        val action = intent.action

        CoroutineScope(Dispatchers.IO).launch {
            try {
                when (action) {
                    "com.edgemind.ACTION_LOAD_MODEL" -> {
                        val modelId = intent.getStringExtra("model_id") ?: return@launch
                        val contextSize = intent.getIntExtra("context_size", 0)
                        Log.i("TestReceiver", "CMD: Loading $modelId with context_size=$contextSize")
                        val start = System.currentTimeMillis()
                        // Assume model manager accepts context size, we need to check this!
                        manager.loadModel(modelId)
                        val elapsed = System.currentTimeMillis() - start
                        Log.i("TestReceiver", "CMD_DONE: Load completed in ${elapsed}ms")
                    }
                    "com.edgemind.ACTION_UNLOAD_MODEL" -> {
                        Log.i("TestReceiver", "CMD: Unloading model")
                        manager.unloadModel()
                        Log.i("TestReceiver", "CMD_DONE: Unload completed")
                    }
                    "com.edgemind.ACTION_GENERATE" -> {
                        val prompt = intent.getStringExtra("prompt") ?: "Hello"
                        val jsonMode = intent.getBooleanExtra("json_mode", false)
                        val budgetExtra = intent.getIntExtra("context_budget", -1)
                        Log.i("TestReceiver", "CMD: Generating for prompt: $prompt (jsonMode: $jsonMode)")
                        manager.setGeneratingState(true)
                        val engine = manager.getEngine()
                        val activeModel = manager.getActiveModelDef()
                        val budget = if (budgetExtra != -1) budgetExtra else (activeModel?.recommendedContext ?: 512)
                        
                        val start = System.currentTimeMillis()
                        var firstTokenTime = -1L
                        var tokenCount = 0
                        val outputBuilder = java.lang.StringBuilder()
                        
                        try {
                            engine.sendUserPrompt(prompt, budget, jsonMode).collect { token ->
                                if (firstTokenTime == -1L) {
                                    firstTokenTime = System.currentTimeMillis()
                                    val ttft = firstTokenTime - start
                                    Log.i("TestReceiver", "CMD_METRIC: TTFT ${ttft}ms")
                                }
                                tokenCount++
                                outputBuilder.append(token)
                            }
                            val end = System.currentTimeMillis()
                            val totalTime = end - start
                            val decodeTime = end - firstTokenTime
                            val prefill = firstTokenTime - start
                            val decodeTps = if (decodeTime > 0) (tokenCount * 1000.0) / decodeTime else 0.0
                            val outputStr = outputBuilder.toString()
                            Log.i("TestReceiver", "CMD_DONE: Generation completed. Tokens: $tokenCount, TotalTime: ${totalTime}ms, TTFT/Prefill: ${prefill}ms, DecodeTPS: $decodeTps")
                            Log.i("TestReceiver", "CMD_OUTPUT: $outputStr")
                        } catch(e: Exception) {
                            Log.e("TestReceiver", "CMD_ERR: Generation failed", e)
                        } finally {
                            manager.setGeneratingState(false)
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e("TestReceiver", "CMD_ERR: Exception in receiver", e)
            }
        }
    }
}
