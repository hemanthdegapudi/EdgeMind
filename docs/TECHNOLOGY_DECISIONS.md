# EdgeMind — Technology Decisions

> Generated: 2026-08-23
> Phase: 0 — Environment Reconnaissance
> Status: Recommendations pending environment setup

---

## 1. Recommended Initial Stack

Based on verified data from the llama.cpp official Android example (`examples/llama.android/`) and current ecosystem versions.

```text
Android Gradle Plugin:  8.13.2 (from llama.cpp example libs.versions.toml)
Gradle:                 9.x (compatible with AGP 8.13.x — exact version from wrapper)
Kotlin:                 2.3.0 (from llama.cpp example libs.versions.toml)
Compose:                UNKNOWN — llama.cpp example uses XML views, not Compose
                        If Compose is desired, use latest BOM compatible with Kotlin 2.3.0
compileSdk:             36 (from llama.cpp example)
minSdk:                 26 (DECISION REQUIRED — see below)
targetSdk:              36 (from llama.cpp example)
JDK:                    17 (from llama.cpp example compileOptions)
NDK:                    29.0.13113456 (from llama.cpp lib/build.gradle.kts)
CMake:                  3.31.6 (from llama.cpp lib/build.gradle.kts)
llama.cpp version:      v0.2.0-dev (current master) or latest tag
C++ standard:           C++17 (from llama.cpp CMakeLists.txt)
ABI:                    arm64-v8a (primary), x86_64 (emulator)
```

> [!IMPORTANT]
> ### minSdk Decision Required
>
> The llama.cpp example uses `minSdk = 33` (Android 13).
> The Redmi K20 Pro's final official Android is **11 (API 30)**.
>
> **Options:**
> 1. `minSdk = 26` — Broader compatibility, covers stock K20 Pro (Android 9–11)
> 2. `minSdk = 29` — Required for Thermal API (`PowerManager.addThermalStatusListener`)
> 3. `minSdk = 30` — Matches official K20 Pro final Android 11
> 4. `minSdk = 33` — Matches llama.cpp example, requires custom ROM on K20 Pro
>
> **Recommendation:** `minSdk = 26` for broadest device support. Use runtime checks for
> APIs requiring higher levels (thermal API ≥29, etc.). However, if the K20 Pro runs a
> custom ROM (Android 14+), `minSdk = 33` is also viable.

---

## 2. llama.cpp Integration Strategy

### Verified API Surface (from `include/llama.h` on master, v0.2.0-dev)

| Category | API Functions (Verified) | Source |
|---|---|---|
| **Initialization** | `llama_backend_init()`, `llama_backend_free()` | llama.h L472-475 |
| **Model Loading** | `llama_model_load_from_file()`, `llama_model_free()` | llama.h L507, L530 |
| **Context** | `llama_init_from_model()`, `llama_free()` | llama.h L532, L542 |
| **Tokenization** | `llama_tokenize()`, `llama_token_to_piece()`, `llama_detokenize()` | llama.h L1163, L1177, L1191 |
| **Batch** | `llama_batch_init()`, `llama_batch_get_one()`, `llama_batch_free()` | llama.h L940-957 |
| **Decode** | `llama_decode()`, `llama_encode()` | llama.h L965, L981 |
| **Sampler** | `llama_sampler_init()`, `llama_sampler_chain_init()`, `llama_sampler_chain_add()`, `llama_sampler_sample()`, `llama_sampler_accept()`, `llama_sampler_free()` | llama.h L1325-1531 |
| **Sampler Types** | `llama_sampler_init_greedy()`, `llama_sampler_init_temp()`, `llama_sampler_init_top_k()`, `llama_sampler_init_top_p()`, `llama_sampler_init_min_p()` | llama.h L1358-1371 |
| **Memory/KV** | `llama_memory_clear()`, `llama_memory_seq_rm()`, `llama_memory_seq_cp()`, `llama_memory_seq_keep()`, `llama_memory_seq_add()` | llama.h L730-796 |
| **State Save/Load** | `llama_state_get_size()`, `llama_state_get_data()`, `llama_state_set_data()`, `llama_state_save_file()`, `llama_state_load_file()` | llama.h L805-857 |
| **Seq State** | `llama_state_seq_get_size()`, `llama_state_seq_get_data()`, `llama_state_seq_set_data()`, `llama_state_seq_save_file()`, `llama_state_seq_load_file()` | llama.h L860-889 |
| **Threading** | `llama_set_n_threads()` | llama.h L988 |
| **Model Info** | `llama_model_n_ctx_train()`, `llama_model_n_embd()`, `llama_model_n_layer()`, `llama_model_n_params()`, `llama_model_size()` | llama.h L579-638 |
| **Vocab** | `llama_vocab_n_tokens()`, `llama_model_get_vocab()` | llama.h L576, L601 |
| **Chat Templates** | `llama_model_chat_template()`, `llama_chat_apply_template()` | llama.h L635, L1214 |
| **Perf** | `llama_perf_context()`, `llama_perf_context_print()`, `llama_perf_context_reset()` | llama.h L1583-1590 |

### Key Observations

> [!NOTE]
> **API Naming Convention Change**: The API has moved from `llama_kv_cache_*` to `llama_memory_*`.
> The old `llama_kv_cache_clear()` is now `llama_memory_clear()` using `llama_memory_t`.
> Any code or documentation referencing `llama_kv_cache_*` is **OUTDATED**.

> [!NOTE]
> **Deprecated Functions**: `llama_new_context_with_model()` → use `llama_init_from_model()`.
> `llama_load_model_from_file()` → use `llama_model_load_from_file()`.

---

## 3. Android Build Configuration (from llama.cpp example)

Key CMake arguments from the official example:

```cmake
-DCMAKE_BUILD_TYPE=Release
-DBUILD_SHARED_LIBS=ON
-DLLAMA_BUILD_APP=OFF
-DLLAMA_BUILD_COMMON=ON
-DLLAMA_OPENSSL=OFF
-DGGML_NATIVE=OFF          # Critical for cross-compilation
-DGGML_BACKEND_DL=ON       # Dynamic backend loading
-DGGML_CPU_ALL_VARIANTS=ON  # All CPU instruction set variants
-DGGML_LLAMAFILE=OFF
```

---

## 4. Jetpack Compose Decision

The official llama.cpp Android example uses **XML views** (ConstraintLayout, Activity), NOT Jetpack Compose.

If EdgeMind wants Compose:
- Add the `org.jetbrains.kotlin.plugin.compose` Gradle plugin
- Add Compose BOM dependency
- This is a project decision, not a technical blocker

---

## 5. Multimodal / Vision

| Feature | Status | Evidence |
|---|---|---|
| LLaVA support in llama.cpp | ✅ Active — `examples/llava/` | GitHub repo |
| Moondream2 GGUF support | ⚠️ Experimental, quality issues reported | Web research |
| Moondream2 on Android | ⚠️ Not recommended — poor accuracy in llama.cpp | Community reports |
| ML Kit Text Recognition v2 | ✅ Available for on-device OCR | Google documentation |

---

## 6. Thermal Monitoring

| API | Availability | Notes |
|---|---|---|
| `PowerManager.addThermalStatusListener` | API 29+ (Android 10) | Returns status codes, not temperatures |
| `PowerManager.currentThermalStatus` | API 29+ | Polling alternative |
| Native `AThermal_*` APIs | NDK API 30+ | C-level thermal monitoring |

---

## 7. Native Memory Behavior on Android

| Aspect | Details |
|---|---|
| Virtual Address Space (arm64) | ~256 TiB (48-bit) — not a practical limit |
| mmap behavior | Does NOT immediately allocate physical RAM; pages loaded on access |
| Swap | Android uses zRAM (compressed RAM), NOT disk swap |
| OOM Killer | Active — will kill process exceeding memory budget |
| Per-app limits | Vary by OS version and OEM; typically 256MB–512MB for Java heap, no hard limit for native |
| 16KB page size | NDK r28+ default for arm64; older devices use 4KB |
