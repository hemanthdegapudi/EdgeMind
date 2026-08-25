# EDGEMIND — PHASE 2B: ADB Recovery + Physical Device Runtime Proof

## 1. USB Detection
- `lsusb` indicated the physical device was attached: `Bus 001 Device 008: ID 0a9d:ff40 Xiaomi Redmi K20 Pro`

## 2. ADB Diagnostics
- ADB server was restarted. Initial `adb devices -l` result was empty.
- Checking USB descriptors confirmed only the MTP interface was active, missing the ADB interface.

## 3. Authorization
- **ADB_STATE**: Empty list initially.
- **USB_STATE**: Detected, MTP only.
- **AUTHORIZATION_STATE**: Unauthorized/Missing.
- **DEVICE_STATE**: Offline / Not attached via ADB.
- **REMEDIATION**: User manually enabled USB debugging in Developer Options and accepted the RSA key prompt on the device.
- Result: `adb devices -l` successfully listed the device as `device usb:1-2 product:raphaelin model:Redmi_K20_Pro device:raphaelin transport_id:1`.

## 4. Device Profile
- **Manufacturer**: Xiaomi
- **Model**: Redmi K20 Pro
- **Android Version (Release)**: 11
- **Android API SDK Level**: 30
- **Primary CPU ABI**: arm64-v8a
- **Supported CPU ABIs**: arm64-v8a, armeabi-v7a, armeabi
- **RAM**: 5633892 kB Total (~5.6 GB), 2417248 kB Available (~2.4 GB)
- **User Storage Space (`/data`)**: 109G Total, 88G Available

## 5. Transfer Test
- Transferred a test text file `test_transfer.txt` using `adb push`.
- Reading file using `adb shell cat` succeeded.
- Cleaned up the test file using `adb shell rm`.

## 6. Native Binary Transfer
- Pushed `llama-cli` (built for arm64-v8a) to `/data/local/tmp/`.
- The following required shared libraries were also transferred:
  - `libllama-common.so`
  - `libggml-cpu.so`
  - `libllama-server-impl.so`
  - `libggml.so`
  - `libllama.so`
  - `libmtmd.so`
  - `libllama-cli-impl.so`
  - `libggml-base.so`
  - `libomp.so` (from NDK toolchain for OpenMP support)

## 7. Native Execution Result
- Executed `llama-cli --help` via `adb shell` with `LD_LIBRARY_PATH=/data/local/tmp`.
- Result: **BINARY_EXECUTION_VERIFIED**

## 8. Errors
- **ERROR_MESSAGE**: `CANNOT LINK EXECUTABLE "/data/local/tmp/llama-cli": library "libomp.so" not found: needed by /data/local/tmp/libggml-cpu.so in namespace (default)`

## 9. Root Cause
- **ROOT_CAUSE**: The built binary depends on OpenMP (`libomp.so`), which isn't present in Android system libraries.
- **REMEDIATION**: Extracted `libomp.so` from the NDK toolchain (aarch64) and pushed it to `/data/local/tmp/`.

## 10. Remaining Blockers
- None.
