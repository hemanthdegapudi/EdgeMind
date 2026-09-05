# EdgeMind

EdgeMind is an offline-first, on-device AI system designed for constrained Android hardware. It leverages the `llama.cpp` inference engine via NDK to run sophisticated language models (like Qwen and DeepSeek) entirely locally, ensuring privacy and minimizing cloud dependency.

## Features

- **Offline-First Architecture**: Run powerful LLMs locally without requiring an internet connection.
- **Hardware Optimized**: Built specifically for constrained Android hardware (tested on Snapdragon 855 / Android 11).
- **Resource Safety**: Implements MemoryGuard and ThermalGuard architectures to manage memory consumption and thermal throttling.
- **Multi-Model Support**: Extensible architecture supporting multiple models, currently focusing on Qwen and DeepSeek.
- **JNI Bridging**: Zero-copy memory transfers between the Android Java layer and native C++ backend for optimal performance.
- **Modern UI**: Clean, responsive chat interface designed for seamless user experience.

## Technical Details

- **Core Engine**: `llama.cpp` compiled via Android NDK.
- **Language Models**: Qwen3 (1.7B) and DeepSeek R1 Distill Qwen (1.5B).
- **Target Platform**: Android API 30+ (ARM64).

## Current Development Status

- ✅ Base inference engine and Native C++ integration functioning on Android.
- ✅ Two-application model architecture supporting both Qwen and DeepSeek.
- 🚧 Robustness under aggressive thermal throttling and memory consumption curves are under active investigation.
- 🚧 Future support planned for local knowledge/RAG and domain adaptation (LoRA).

## Building and Deployment

The native backend is compiled using standard Android NDK CMake toolchain arguments:

```bash
-DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
-DANDROID_ABI=arm64-v8a \
-DANDROID_PLATFORM=android-28 \
-DCMAKE_C_FLAGS="-march=armv8.4a+dotprod" \
-DCMAKE_CXX_FLAGS="-march=armv8.4a+dotprod"
```

Deployment to device for testing:
```bash
adb push <binary> /data/local/tmp/
adb shell "cd /data/local/tmp && ./main -m /data/local/tmp/model.gguf -p 'prompt' -n 128"
```
