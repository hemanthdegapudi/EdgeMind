package com.edgemind.app.model

data class ModelDefinition(
    val id: String,
    val displayName: String,
    val modelPath: String,
    val quantization: String,
    val architecture: String,
    val parameterCount: String,
    val expectedFileSize: Long,
    val checksum: String,
    val contextLimit: Int,
    val recommendedContext: Int
)

object ModelRegistry {
    val MODELS = listOf(
        ModelDefinition(
            id = "deepseek-r1-distill-qwen-1.5b-q5km",
            displayName = "DeepSeek R1 Distill 1.5B",
            modelPath = "/sdcard/models/DeepSeek-R1-Distill-Qwen-1.5B-Q5_K_M.gguf",
            quantization = "Q5_K_M",
            architecture = "qwen2",
            parameterCount = "1.5B",
            expectedFileSize = 1285494880L,
            checksum = "5190cb74aef330f7d4cf6a6a06553248b0c5bf1054a455184bbe58c03437ba37",
            contextLimit = 4096,
            recommendedContext = 2048
        ),
        ModelDefinition(
            id = "qwen3-1.7b-q4km",
            displayName = "Qwen3 1.7B",
            modelPath = "/sdcard/models/Qwen3-1.7B-Q4_K_M.gguf",
            quantization = "Q4_K_M",
            architecture = "qwen3",
            parameterCount = "1.7B",
            expectedFileSize = 1282439264L,
            checksum = "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5",
            contextLimit = 4096,
            recommendedContext = 2048
        )
    )

    fun getModelById(id: String): ModelDefinition? = MODELS.find { it.id == id }
}
