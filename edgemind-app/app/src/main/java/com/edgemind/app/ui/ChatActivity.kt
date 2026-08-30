package com.edgemind.app.ui

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.edgemind.app.EdgeMindApplication
import com.edgemind.app.R
import com.edgemind.app.model.ModelRegistry
import com.edgemind.app.model.ModelState
import com.edgemind.app.service.InferenceForegroundService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ChatMessage(val role: String, var content: String)

class ChatAdapter(private val messages: List<ChatMessage>) : RecyclerView.Adapter<ChatAdapter.ViewHolder>() {
    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvRole: TextView = view.findViewById(R.id.tvRole)
        val tvContent: TextView = view.findViewById(R.id.tvContent)
    }
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_chat_message, parent, false)
        return ViewHolder(view)
    }
    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val msg = messages[position]
        holder.tvRole.text = msg.role
        holder.tvContent.text = msg.content
    }
    override fun getItemCount() = messages.size
}

class ChatActivity : AppCompatActivity() {

    private lateinit var tvModelStatus: TextView
    private lateinit var spinnerModels: Spinner
    private lateinit var rvChatHistory: RecyclerView
    private lateinit var etMessage: EditText
    private lateinit var btnSend: Button

    private val chatMessages = mutableListOf<ChatMessage>()
    private lateinit var chatAdapter: ChatAdapter

    private var generationJob: Job? = null

    // Single source of truth for chat history semantics
    // Phase 8: Chat history semantics
    private val conversationHistory = mutableListOf<ChatMessage>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)

        tvModelStatus = findViewById(R.id.tvModelStatus)
        spinnerModels = findViewById(R.id.spinnerModels)
        rvChatHistory = findViewById(R.id.rvChatHistory)
        etMessage = findViewById(R.id.etMessage)
        btnSend = findViewById(R.id.btnSend)

        chatAdapter = ChatAdapter(chatMessages)
        rvChatHistory.layoutManager = LinearLayoutManager(this).apply { stackFromEnd = true }
        rvChatHistory.adapter = chatAdapter

        // Start Foreground Service to keep process alive and initialize Thermal/Memory guards properly
        startService(Intent(this, InferenceForegroundService::class.java))

        setupModelSpinner()
        observeModelState()

        btnSend.setOnClickListener {
            val userMsg = etMessage.text.toString()
            if (userMsg.isNotBlank()) {
                sendMessage(userMsg)
                etMessage.text.clear()
            }
        }
    }

    private fun setupModelSpinner() {
        val models = ModelRegistry.MODELS
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, models.map { it.displayName })
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        spinnerModels.adapter = adapter
        
        // Disable initially to avoid rapid clicking
        spinnerModels.isEnabled = false

        spinnerModels.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val selectedModel = models[position]
                val app = application as EdgeMindApplication
                val manager = app.modelManager
                
                if (manager.getActiveModelDef()?.id != selectedModel.id) {
                    lifecycleScope.launch {
                        // Prevent sending while switching
                        withContext(Dispatchers.Main) { btnSend.isEnabled = false; spinnerModels.isEnabled = false }
                        manager.switchModel(selectedModel.id)
                        withContext(Dispatchers.Main) { spinnerModels.isEnabled = true }
                    }
                }
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
    }

    private fun observeModelState() {
        val app = application as EdgeMindApplication
        val manager = app.modelManager

        lifecycleScope.launch {
            manager.status.collect { state ->
                withContext(Dispatchers.Main) {
                    tvModelStatus.text = "Status: ${state.name}"
                    
                    // UI prevents contradictory operations
                    when (state) {
                        ModelState.READY -> {
                            btnSend.isEnabled = true
                            spinnerModels.isEnabled = true
                        }
                        ModelState.GENERATING -> {
                            btnSend.isEnabled = false
                            spinnerModels.isEnabled = false
                        }
                        ModelState.LOADING, ModelState.UNLOADING -> {
                            btnSend.isEnabled = false
                            spinnerModels.isEnabled = false
                        }
                        ModelState.UNLOADED, ModelState.FAILED -> {
                            btnSend.isEnabled = false
                            spinnerModels.isEnabled = true
                        }
                    }
                }
            }
        }
    }

    private fun sendMessage(content: String) {
        val app = application as EdgeMindApplication
        val manager = app.modelManager
        
        chatMessages.add(ChatMessage("User", content))
        conversationHistory.add(ChatMessage("User", content))
        
        val assistantMsg = ChatMessage("Assistant", "")
        chatMessages.add(assistantMsg)
        chatAdapter.notifyItemRangeInserted(chatMessages.size - 2, 2)
        rvChatHistory.scrollToPosition(chatMessages.size - 1)

        generationJob = lifecycleScope.launch(Dispatchers.IO) {
            manager.setGeneratingState(true)
            try {
                // Phase 9 & 10: Context Policy and Chat Templates
                // We construct the prompt based on conversationHistory, bounded to last N messages
                val activeModel = manager.getActiveModelDef()
                val contextBudget = activeModel?.recommendedContext ?: 2048
                
                // Simple formatting for now. Ideally apply model-specific chat templates
                val promptBuilder = StringBuilder()
                val boundedHistory = conversationHistory.takeLast(6)
                
                // Qwen-style chat template used by both DeepSeek-R1-Distill-Qwen and Qwen3
                for (msg in boundedHistory) {
                    val role = if (msg.role == "User") "user" else "assistant"
                    promptBuilder.append("<|im_start|>$role\n${msg.content}<|im_end|>\n")
                }
                promptBuilder.append("<|im_start|>assistant\n")
                
                val engine = manager.getEngine()
                
                engine.sendUserPrompt(promptBuilder.toString(), contextBudget).collect { token ->
                    assistantMsg.content += token
                    withContext(Dispatchers.Main) {
                        chatAdapter.notifyItemChanged(chatMessages.size - 1)
                        rvChatHistory.scrollToPosition(chatMessages.size - 1)
                    }
                }
                
                conversationHistory.add(ChatMessage("Assistant", assistantMsg.content))
            } catch (e: Exception) {
                assistantMsg.content += "\n[Error: ${e.message}]"
                withContext(Dispatchers.Main) {
                    chatAdapter.notifyItemChanged(chatMessages.size - 1)
                }
            } finally {
                manager.setGeneratingState(false)
            }
        }
    }
}
