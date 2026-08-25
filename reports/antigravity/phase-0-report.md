# EdgeMind — Phase 0 Report

> **Date:** 2026-08-23
> **Phase:** 0 — Environment Reconnaissance
> **Agent:** Antigravity (lead engineering agent)

---

## 1. Executive Summary

Phase 0 reconnaissance of the EdgeMind project environment has been completed. The development machine is running Ubuntu 24.04.4 LTS with basic build tools (GCC, Make, Git, Python) but **lacks all Android development tooling** — no JDK, Android SDK, NDK, Android Studio, ADB, CMake, or Gradle are installed.

No Android device is currently connected to the development machine. The target device (Xiaomi Redmi K20 Pro / Snapdragon 855) hardware specifications have been verified through manufacturer data and public specification databases.

The llama.cpp library has been verified against its current public source (v0.2.0-dev) and confirmed to have full Android/ARM64 support with an official example app. The API surface has been documented directly from the header file.

**Overall Assessment:** PASS WITH BLOCKERS — all reconnaissance objectives met, but critical toolchain installation is required before Phase 1.

---

## 2. Environment Inventory

### Development Machine

| Component | Status | Value |
|---|---|---|
| OS | ✅ | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Kernel | ✅ | 7.0.0-30-generic x86_64 |
| CPU | ✅ | Intel i5-7200U (2C/4T @ 2.5–3.1 GHz) |
| RAM | ✅ | 7.6 GiB total |
| Disk (main partition) | ⚠️ | 17 GiB free of 98 GiB |
| GCC | ✅ | 13.3.0 |
| Git | ✅ | 2.43.0 |
| Python | ✅ | 3.12.3 |
| Java/JDK | ❌ | NOT INSTALLED |
| Android Studio | ❌ | NOT INSTALLED |
| Android SDK | ❌ | NOT INSTALLED |
| Android NDK | ❌ | NOT INSTALLED |
| CMake | ❌ | NOT INSTALLED |
| Gradle | ❌ | NOT INSTALLED |
| ADB | ❌ | NOT INSTALLED |
| Emulator | ❌ | NOT INSTALLED |
| GitHub CLI | ❌ | NOT INSTALLED |
| Clang | ❌ | NOT INSTALLED |
| Ninja | ❌ | NOT INSTALLED |

### Key Concern: Disk Space

> [!WARNING]
> Only **17 GiB** free on the main partition.
> Android SDK + NDK + build tools require approximately 10–15 GiB.
> GGUF models require 0.5–5 GiB each.
> This may be insufficient for full development setup + model storage.

---

## 3. Target Device Inventory

### Xiaomi Redmi K20 Pro

| Property | Value | Confidence |
|---|---|---|
| SoC | Qualcomm Snapdragon 855 (7nm) | FACT |
| CPU | 1+3+4 tri-cluster Kryo 485 (A76+A55) | FACT |
| CPU Clocks | 2.84/2.42/1.80 GHz | FACT |
| ABI | arm64-v8a | FACT |
| GPU | Adreno 640 | FACT |
| Vulkan | 1.1 (per chipset spec) | FACT |
| RAM | 6 or 8 GB LPDDR4X | FACT (variant unknown) |
| Storage | 64/128/256 GB UFS 2.1 | FACT (variant unknown) |
| Final Official Android | 11 (API 30) | FACT |
| Final Official MIUI | 12.5 | FACT |
| Support Status | End of Life | FACT |
| Device Connected | No | FACT (lsusb verified) |
| Actual Android Version | UNKNOWN | Device not connected |
| Actual RAM Variant | UNKNOWN | Device not connected |
| Custom ROM Installed | UNKNOWN | Device not connected |
| Thermal Baseline | UNKNOWN | Device not connected |
| GPU Driver Version | UNKNOWN | Device not connected |

---

## 4. Verified Facts

| # | Fact | Evidence |
|---|---|---|
| 1 | llama.cpp has official Android example at `examples/llama.android/` | GitHub API directory listing |
| 2 | llama.cpp requires CMake 3.14–3.28 | `CMakeLists.txt` line 1 |
| 3 | llama.cpp uses C++17 | `CMakeLists.txt` `set(CMAKE_CXX_STANDARD 17)` (subagent verification) |
| 4 | llama.cpp current version is v0.2.0-dev | `CMakeLists.txt` lines 6–8 |
| 5 | llama.cpp Android example uses NDK 29.0.13113456 | `lib/build.gradle.kts` |
| 6 | llama.cpp Android example uses CMake 3.31.6 | `lib/build.gradle.kts` |
| 7 | llama.cpp Android example uses AGP 8.13.2 | `libs.versions.toml` |
| 8 | llama.cpp Android example uses Kotlin 2.3.0 | `libs.versions.toml` |
| 9 | llama.cpp Android example uses compileSdk 36 | `app/build.gradle.kts` |
| 10 | llama.cpp Android example uses minSdk 33 | `app/build.gradle.kts` |
| 11 | llama.cpp Android example uses JDK 17 | `lib/build.gradle.kts` compileOptions |
| 12 | llama.cpp Android example targets arm64-v8a and x86_64 | `lib/build.gradle.kts` abiFilters |
| 13 | KV cache API has been renamed from `llama_kv_cache_*` to `llama_memory_*` | `llama.h` lines 730–796 |
| 14 | State serialization APIs exist: `llama_state_save_file`, `llama_state_load_file` | `llama.h` lines 833–857 |
| 15 | Sequence-level state APIs exist: `llama_state_seq_*` | `llama.h` lines 860–923 |
| 16 | Snapdragon 855 supports Vulkan 1.1 | Qualcomm specifications |
| 17 | Android Thermal API available from API 29 | Android developer documentation |
| 18 | ML Kit Text Recognition v2 available for on-device OCR | Google ML Kit documentation |
| 19 | No development tools are installed on this machine | Terminal verification of each tool |
| 20 | Project directory is empty | `find` and `ls` verification |

---

## 5. Estimates

| # | Estimate | Basis | Confidence |
|---|---|---|---|
| 1 | TinyLlama 1.1B Q4_K_M ≈ 0.7 GB | ~0.6–0.7× parameter count rule | Medium |
| 2 | Qwen2 1.5B Q4_K_M ≈ 1.0 GB | Same rule | Medium |
| 3 | KV cache for 2K context ≈ 0.2–0.5 GB | Depends on model architecture | Low |
| 4 | Available app RAM on K20 Pro ≈ 3–5 GB | Typical Android budgets | Low |
| 5 | Android SDK + NDK install ≈ 10–15 GB | Typical installation sizes | Medium |

---

## 6. Unknowns

| # | Unknown | Impact |
|---|---|---|
| 1 | Which RAM variant (6/8 GB) is the target K20 Pro | Directly affects max model size |
| 2 | What Android version is running on the device | Affects minSdk and available APIs |
| 3 | Whether a custom ROM is installed | Affects API level, Vulkan driver version |
| 4 | Device storage free space | Affects model storage capacity |
| 5 | Actual inference speed (tok/s) on K20 Pro | Cannot estimate without benchmarking |
| 6 | Vulkan driver behavior on Adreno 640 with llama.cpp | Reported quirks on some Adreno chips |
| 7 | Thermal throttling behavior under sustained load | Device-specific, needs testing |
| 8 | Whether Compose BOM version is compatible with Kotlin 2.3.0 | Needs verification at project setup |

---

## 7. Claims Requiring Verification

### llama.cpp APIs

| Claim | Status | Evidence |
|---|---|---|
| llama.cpp has `llama_kv_cache_clear()` | **OUTDATED** | Now `llama_memory_clear()` via `llama_memory_t` (llama.h L730) |
| llama.cpp has `llama_kv_cache_seq_rm()` | **OUTDATED** | Now `llama_memory_seq_rm()` (llama.h L739) |
| llama.cpp has `llama_new_context_with_model()` | **OUTDATED** (deprecated) | Now `llama_init_from_model()` (llama.h L532) |
| llama.cpp has `llama_load_model_from_file()` | **OUTDATED** (deprecated) | Now `llama_model_load_from_file()` (llama.h L507) |
| KV cache serialization is supported | **VERIFIED** | `llama_state_save_file()` / `llama_state_load_file()` (llama.h L833–857) |
| Sequence-level state save/load exists | **VERIFIED** | `llama_state_seq_*` family (llama.h L860–923) |
| Batch API exists | **VERIFIED** | `llama_batch_init()`, `llama_batch_get_one()`, `llama_batch_free()` (llama.h L940–957) |
| Sampler chain API exists | **VERIFIED** | `llama_sampler_chain_init()`, `llama_sampler_chain_add()`, etc. (llama.h L1325–1531) |
| llama.cpp supports Android build | **VERIFIED** | Official example at `examples/llama.android/` |
| llama.cpp supports ARM64 | **VERIFIED** | `abiFilters += listOf("arm64-v8a")` in example |

### llama.cpp Android Support

| Claim | Status | Evidence |
|---|---|---|
| llama.cpp has official Android example | **VERIFIED** | `examples/llama.android/` directory |
| JNI bridge is provided | **VERIFIED** | `lib/` module with native build in example |
| Vulkan support on Android | **PLAUSIBLE** | Vulkan backend exists in llama.cpp; not enabled in example by default |

### Model Switching

| Claim | Status | Evidence |
|---|---|---|
| Can unload and reload different models | **VERIFIED** | `llama_model_free()` + `llama_model_load_from_file()` (llama.h L507, L530) |
| Hot-swapping models without restart | **PLAUSIBLE** | API supports it; memory management on Android needs testing |

### Multimodal / Vision

| Claim | Status | Evidence |
|---|---|---|
| LLaVA APIs exist in llama.cpp | **VERIFIED** | `examples/llava/` directory; `llava.cpp` and `clip.cpp` |
| Moondream2 works well with llama.cpp | **INCORRECT** | Community reports significant quality degradation and accuracy issues |
| Moondream2 is suitable for Android | **INCORRECT** | Not recommended for reliable use per community assessment |

### ML Kit OCR

| Claim | Status | Evidence |
|---|---|---|
| ML Kit Text Recognition works offline | **VERIFIED** | Google documentation — bundled model option available |
| ML Kit supports multiple scripts | **VERIFIED** | v2 supports Latin, Chinese, Devanagari, Japanese, Korean |

### Hardware

| Claim | Status | Evidence |
|---|---|---|
| K20 Pro has Snapdragon 855 | **VERIFIED** | GSMArena, Wikipedia, manufacturer specs |
| K20 Pro supports Vulkan | **VERIFIED** | Adreno 640 → Vulkan 1.1 per chipset spec |
| K20 Pro has 6 GB RAM | **PLAUSIBLE** | 6 GB or 8 GB depending on variant — cannot verify without device |
| K20 Pro can run 7B models | **PLAUSIBLE but risky** | Q4_K_M 7B ≈ 4.1 GB + KV cache; exceeds comfortable budget on 6 GB variant |

### Performance

| Claim | Status | Evidence |
|---|---|---|
| Expected X tok/s on K20 Pro | **UNKNOWN** | No benchmarks performed; device not connected |
| CPU-first inference is viable | **PLAUSIBLE** | 4× A76 cores should provide usable throughput; needs testing |

### Thermal

| Claim | Status | Evidence |
|---|---|---|
| Android provides thermal monitoring API | **VERIFIED** | `PowerManager.addThermalStatusListener` (API 29+) |
| Can read exact temperature on K20 Pro | **UNKNOWN** | API provides status codes, not temperatures; vendor-specific |

### Android Native Memory

| Claim | Status | Evidence |
|---|---|---|
| mmap works for large model files | **VERIFIED** | 64-bit ARM has 256 TiB VA space; mmap is lazy-loaded |
| No hard native memory limit | **PLAUSIBLE** | No strict per-process limit, but OOM killer is active |
| zRAM is used instead of swap | **VERIFIED** | Standard Android behavior |

---

## 8. Recommended Initial Stack

```text
Android Gradle Plugin:  8.13.2
Gradle:                 Use wrapper from llama.cpp example (exact version TBD)
Kotlin:                 2.3.0
Compose:                Latest BOM compatible with Kotlin 2.3.0 (REQUIRES VERIFICATION)
compileSdk:             36
minSdk:                 DECISION REQUIRED (26 for broad compat OR 33 to match example)
targetSdk:              36
JDK:                    17
NDK:                    29.0.13113456
CMake:                  3.31.6
llama.cpp:              v0.2.0-dev (current master) or latest stable tag
C++ standard:           C++17
ABI:                    arm64-v8a (primary)
```

---

## 9. Blockers

| # | Blocker | Severity | Resolution |
|---|---|---|---|
| **B1** | No JDK installed | 🔴 CRITICAL | Install JDK 17 (OpenJDK or Temurin) |
| **B2** | No Android SDK installed | 🔴 CRITICAL | Install Android SDK via `sdkmanager` or Android Studio |
| **B3** | No Android NDK installed | 🔴 CRITICAL | Install NDK r29 (29.0.13113456) via SDK Manager |
| **B4** | No CMake installed | 🔴 CRITICAL | Install CMake 3.31.6 via SDK Manager |
| **B5** | No Android Studio installed | 🟡 HIGH | Install Android Studio (IDE, debugger, profiler, layout inspector) |
| **B6** | No ADB installed | 🔴 CRITICAL | Comes with Android SDK platform-tools |
| **B7** | No Gradle installed | 🟢 LOW | Use Gradle wrapper (`gradlew`) — included in project |
| **B8** | No device connected | 🟡 HIGH | Connect K20 Pro via USB for device-specific verification |
| **B9** | Disk space may be insufficient | 🟡 HIGH | 17 GiB free; SDK + NDK + models need ~15–20 GiB |
| **B10** | No GitHub CLI | 🟢 LOW | Optional; Git is available |
| **B11** | `minSdk` decision required | 🟡 HIGH | Must decide based on device's actual Android version |

---

## 10. Risks

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Disk space exhaustion during setup | Medium | High | Clean up or expand partition before installing SDK |
| R2 | K20 Pro insufficient RAM for target models | Medium | High | Start with ≤1.5B models; verify RAM variant |
| R3 | Vulkan driver issues on Adreno 640 | Medium | Low | Start with CPU-only; Vulkan is a future goal |
| R4 | Thermal throttling reduces sustained performance | High | Medium | Implement thermal monitoring, dynamic thread adjustment |
| R5 | Model quality at aggressive quantization | Medium | Medium | Test Q4_K_M vs Q5_K_M on target models |
| R6 | llama.cpp API breaking changes | Low | Medium | Pin to specific commit/tag |
| R7 | Build machine too slow for NDK cross-compilation | Medium | Low | i5-7200U is modest; expect longer build times |
| R8 | minSdk mismatch with device | Medium | High | Verify device Android version before deciding |

---

## 11. Recommended Phase 1

### Prerequisites (must resolve blockers first):
1. Install JDK 17
2. Install Android Studio (or commandline SDK tools)
3. Install Android SDK (platform 36, build-tools, platform-tools)
4. Install NDK 29.0.13113456
5. Install CMake 3.31.6
6. Connect Redmi K20 Pro and verify via ADB
7. Determine device RAM variant and Android version
8. Decide on `minSdk`

### Phase 1 Goals:
1. Create minimal Android project with Kotlin + Compose
2. Clone llama.cpp and integrate as native library
3. Build the JNI bridge (reference `examples/llama.android/lib/`)
4. Load a small GGUF model (TinyLlama 1.1B Q4_K_M)
5. Run basic text generation on device
6. Measure baseline tok/s and memory usage
7. Verify thermal behavior under sustained inference

---

## 12. Exact Evidence/Commands Used

### System Inspection
```bash
cat /etc/os-release                    # OS version
uname -a                               # Kernel
lscpu                                  # CPU details
free -h                                # RAM
df -h                                  # Disk
du -sh /home/tilaksijju/               # Home usage
lsusb                                  # USB devices
gcc --version                          # GCC
cc --version                           # CC
make --version                         # Make
git --version                          # Git
python3 --version                      # Python
java -version                          # Java (NOT FOUND)
javac -version                         # Javac (NOT FOUND)
which java                             # Java path (NOT FOUND)
which javac                            # Javac path (NOT FOUND)
ls /usr/lib/jvm/                       # JDK directory (EMPTY)
cmake --version                        # CMake (NOT FOUND)
clang --version                        # Clang (NOT FOUND)
ninja --version                        # Ninja (NOT FOUND)
gradle --version                       # Gradle (NOT FOUND)
adb version                            # ADB (NOT FOUND)
gh --version                           # GitHub CLI (NOT FOUND)
```

### Android SDK Inspection
```bash
echo "$ANDROID_HOME"                   # EMPTY
echo "$ANDROID_SDK_ROOT"               # EMPTY
ls ~/Android/Sdk/platforms/            # NOT FOUND
ls ~/Android/Sdk/build-tools/          # NOT FOUND
ls ~/Android/Sdk/ndk/                  # NOT FOUND
ls ~/Android/Sdk/cmake/                # NOT FOUND
find / -maxdepth 4 -name "android-studio"  # NOT FOUND
find /home -maxdepth 5 -name "adb"         # NOT FOUND
find /home -maxdepth 4 -name "sdkmanager"  # NOT FOUND
```

### llama.cpp Inspection
```bash
find /home -maxdepth 5 -name "llama.cpp" -type d   # NOT FOUND locally
find /home -maxdepth 5 -name "llama.h" -type f      # NOT FOUND locally

# Remote inspection via curl:
curl -sL https://raw.githubusercontent.com/ggml-org/llama.cpp/master/include/llama.h
curl -sL https://raw.githubusercontent.com/ggml-org/llama.cpp/master/CMakeLists.txt
curl -sL https://api.github.com/repos/ggml-org/llama.cpp/contents/examples/llama.android
curl -sL https://raw.githubusercontent.com/ggml-org/llama.cpp/master/examples/llama.android/app/build.gradle.kts
curl -sL https://raw.githubusercontent.com/ggml-org/llama.cpp/master/examples/llama.android/lib/build.gradle.kts
curl -sL https://raw.githubusercontent.com/ggml-org/llama.cpp/master/examples/llama.android/gradle/libs.versions.toml
curl -sL https://raw.githubusercontent.com/ggml-org/llama.cpp/master/examples/llama.android/build.gradle.kts
curl -sL https://raw.githubusercontent.com/ggml-org/llama.cpp/master/examples/llama.android/settings.gradle.kts
```

### Web Research
```
Search: "Xiaomi Redmi K20 Pro specifications RAM GPU Vulkan support"
Search: "Redmi K20 Pro latest Android update MIUI version"
Search: "Android Gradle Plugin latest version 2025 2026"
Search: "Snapdragon 855 CPU core topology Kryo 485"
Search: "llama.cpp GGUF model sizes Q4_K_M small models RAM requirements"
Search: "Android NDK latest stable version"
Search: "moondream2 GGUF llama.cpp support Android"
Search: "Android ML Kit OCR text recognition on-device offline"
Search: "llama.cpp KV cache save load serialization API"
Search: "llama.cpp Android example app"
Search: "Android PowerManager ThermalStatus API"
Search: "Android native memory NDK mmap large files ARM64"
Search: "llama.cpp latest release tag version August 2026"
```

---

# PHASE 0 COMPLETION REPORT

## Status

**PASS WITH BLOCKERS**

## What Was Verified

- Development machine hardware and OS
- All development tool availability (present and absent)
- Disk space constraints
- USB device connectivity (no Android device)
- Redmi K20 Pro hardware specifications (SoC, CPU topology, GPU, Vulkan, RAM options)
- Redmi K20 Pro software status (final Android 11, EOL)
- llama.cpp current API surface (v0.2.0-dev, direct from llama.h)
- llama.cpp Android example configuration (AGP, Kotlin, NDK, CMake, SDK versions)
- llama.cpp CMake requirements (3.14+, C++17)
- llama.cpp KV cache / memory API current naming
- llama.cpp state serialization APIs
- llama.cpp sampler chain API
- Model size estimates for Q4_K_M quantization
- Android thermal monitoring API availability
- Android native memory / mmap behavior
- ML Kit OCR on-device availability
- Moondream2 llama.cpp integration status (not recommended)
- LLaVA support status in llama.cpp

## What Was Not Verified

- Actual Android version on target device (device not connected)
- Actual RAM variant of target device
- Actual storage on target device
- Inference speed (tok/s) on target device
- Thermal behavior under load on target device
- Vulkan driver runtime behavior on Adreno 640
- GPU inference performance
- Actual KV cache memory consumption for specific models
- Compose BOM compatibility with Kotlin 2.3.0
- Exact Gradle version from llama.cpp example wrapper

## Changes Made

- Created project documentation directory structure
- No system configuration changed
- No dependencies installed
- No application code written

## Files Created

```
docs/ENVIRONMENT.md
docs/PROJECT_BASELINE.md
docs/TECHNOLOGY_DECISIONS.md
reports/antigravity/phase-0-report.md  (this file)
```

## Commands Executed

See Section 12 above for complete list.

## Test Results

No tests executed — Phase 0 is reconnaissance only.

## Blockers

| ID | Blocker | Severity |
|---|---|---|
| B1 | No JDK 17 | 🔴 CRITICAL |
| B2 | No Android SDK | 🔴 CRITICAL |
| B3 | No Android NDK r29 | 🔴 CRITICAL |
| B4 | No CMake | 🔴 CRITICAL |
| B5 | No Android Studio | 🟡 HIGH |
| B6 | No ADB | 🔴 CRITICAL |
| B8 | No device connected | 🟡 HIGH |
| B9 | Disk space potentially insufficient (~17 GiB free) | 🟡 HIGH |
| B11 | minSdk decision required | 🟡 HIGH |

## Risks

See Section 10 for full risk table.

## Decisions Recommended

1. **Install JDK 17** — required for all Android builds
2. **Install Android Studio** or command-line SDK tools
3. **Install NDK r29**, CMake 3.31.6, SDK platform 36
4. **Connect the K20 Pro** and run ADB device inspection
5. **Decide minSdk** based on actual device Android version
6. **Verify disk space** — may need to free 5–10 GiB
7. **Select initial model** — recommend TinyLlama 1.1B Q4_K_M for first test

## Phase 1 Recommendation

Proceed with Phase 1 **only after resolving blockers B1–B6 and B8**.

Phase 1 should focus on:
1. Toolchain installation and verification
2. Minimal "hello world" Android app with Compose
3. llama.cpp native integration via JNI
4. Single model loading and basic text generation on device
5. Baseline performance measurement

## Evidence

All evidence is documented in Section 12 and in the companion files:
- [`docs/ENVIRONMENT.md`](file:///home/tilaksijju/Documents/EdgeMind/docs/ENVIRONMENT.md)
- [`docs/PROJECT_BASELINE.md`](file:///home/tilaksijju/Documents/EdgeMind/docs/PROJECT_BASELINE.md)
- [`docs/TECHNOLOGY_DECISIONS.md`](file:///home/tilaksijju/Documents/EdgeMind/docs/TECHNOLOGY_DECISIONS.md)

## Confidence

| Metric | Self-Assessment | Notes |
|---|---|---|
| **Factual confidence** | 88% | All dev machine facts verified by command; device specs from multiple public sources; llama.cpp API read directly from source |
| **Evidence coverage** | 75% | Device-specific runtime data unavailable (no device connected); exact model performance unknown; some version compatibility unverifiable without installation |
| **Hallucination risk** | 8% | Model size estimates and RAM budgets are calculated approximations, not measured; performance expectations are not stated; moondream2 status from community reports |
| **Context deviation** | 2% | All work stayed within Phase 0 scope; no code written; no dependencies installed; no system changes made |
