# EdgeMind — Project Baseline

> Generated: 2026-08-23T10:16+05:30
> Phase: 0 — Environment Reconnaissance
> Anti-hallucination policy: active

---

## Target Device: Xiaomi Redmi K20 Pro

### Hardware Facts (Verified via manufacturer specs and GSMArena)

| Property | Value | Confidence |
|---|---|---|
| **SoC** | Qualcomm Snapdragon 855 (SM8150), 7nm | FACT |
| **CPU** | Kryo 485 — tri-cluster: 1×2.84GHz (Prime/A76) + 3×2.42GHz (Gold/A76) + 4×1.80GHz (Silver/A55) | FACT |
| **ABI** | arm64-v8a (ARM64) | FACT |
| **GPU** | Adreno 640 | FACT |
| **Vulkan** | Vulkan 1.1 (supported by Adreno 640) | FACT |
| **OpenGL ES** | 3.2 | FACT |
| **OpenCL** | 2.0 | FACT |
| **RAM** | 6 GB or 8 GB LPDDR4X (variant-dependent) | FACT — specific unit UNKNOWN |
| **Storage** | 64/128/256 GB UFS 2.1 (variant-dependent) | FACT — specific unit UNKNOWN |
| **Display** | 6.39" Super AMOLED, 1080×2340, HDR10 | FACT |
| **Battery** | 4000 mAh, 27W fast charging | FACT |

### Software Facts

| Property | Value | Confidence |
|---|---|---|
| **Final Official Android** | Android 11 | FACT |
| **Final Official MIUI** | MIUI 12.5 | FACT |
| **API Level (Official)** | API 30 (Android 11) | FACT |
| **Support Status** | End of Life — no further official updates | FACT |
| **Custom ROM Availability** | Active community (LineageOS, EvolutionX, etc.) supporting Android 14/15 | PLAUSIBLE |

> [!IMPORTANT]
> The actual Android version on the target device is **UNKNOWN** — no device is connected.
> If running a custom ROM, the API level could be 33–35 (Android 13–15).
> This critically impacts `minSdk` and available APIs.

### CPU Core Topology (Snapdragon 855)

```
Cluster 0 (Prime):       1× Kryo 485 Gold (A76) @ 2.84 GHz
Cluster 1 (Performance): 3× Kryo 485 Gold (A76) @ 2.42 GHz
Cluster 2 (Efficiency):  4× Kryo 485 Silver (A55) @ 1.80 GHz
Total: 8 cores
```

### RAM Budget Analysis

| Scenario | Total RAM | OS + Background | Available for App | Confidence |
|---|---|---|---|---|
| 6 GB variant | 6 GiB | ~2–3 GiB | ~3–4 GiB | ESTIMATE |
| 8 GB variant | 8 GiB | ~2–3 GiB | ~5–6 GiB | ESTIMATE |

> [!WARNING]
> Android does not use traditional swap. It uses **zRAM** (compressed RAM).
> Native memory via `mmap` does not consume physical RAM until pages are accessed.
> The OOM killer will terminate processes exceeding memory budgets.
> Exact per-app memory budget depends on OS version, OEM skin, and system configuration.

---

## Model Size Budget

| Model | Params | Q4_K_M Size (est.) | KV Cache (2K ctx) | Total (est.) | Fits 6GB? | Fits 8GB? |
|---|---|---|---|---|---|---|
| TinyLlama 1.1B | 1.1B | ~0.7 GB | ~0.2 GB | ~1.0 GB | ✅ Yes | ✅ Yes |
| Qwen2 1.5B | 1.5B | ~1.0 GB | ~0.3 GB | ~1.5 GB | ✅ Yes | ✅ Yes |
| Phi-2 2.7B | 2.7B | ~1.7 GB | ~0.4 GB | ~2.3 GB | ⚠️ Tight | ✅ Yes |
| Llama 3.2 3B | 3B | ~1.9 GB | ~0.5 GB | ~2.6 GB | ⚠️ Tight | ✅ Yes |
| Mistral 7B | 7B | ~4.1 GB | ~1.0 GB | ~5.3 GB | ❌ No | ⚠️ Tight |

> [!CAUTION]
> All model sizes are **ESTIMATES** based on the ~0.6–0.7× rule of thumb for Q4_K_M.
> KV cache sizes depend on context length, n_embd, n_layer, and n_head_kv.
> Actual values must be verified by loading the specific GGUF files.
> These are **NOT benchmarked on the K20 Pro** — no device is connected.

---

## Device Connection Status

| Check | Result |
|---|---|
| ADB installed | ❌ No |
| Device connected via USB | ❌ No (verified by `lsusb`) |
| Device-specific Android version | UNKNOWN |
| Device-specific RAM variant | UNKNOWN |
| Device-specific storage variant | UNKNOWN |
| Device thermal baseline | UNKNOWN |
| Device GPU driver version | UNKNOWN |
| Device Vulkan capabilities | UNKNOWN (Vulkan 1.1 by spec — runtime verification needed) |
