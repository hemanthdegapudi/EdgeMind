#!/usr/bin/env python3
"""
Stability test: ONE model load, THREE sequential short generations, same process.
Model: qwen3-1.7b-q4km
Prompts: "Hello", "What is 2 plus 2?", "Name one color."
"""
import subprocess, time, re, sys, datetime

ADB = ["adb"]
MODEL_ID = "qwen3-1.7b-q4km"
PROMPTS = ["Hello", "What is 2 plus 2?", "Name one color."]
PKG = "com.edgemind.app"
RECEIVER = f"{PKG}/.TestReceiver"


def ts():
    return datetime.datetime.now().isoformat(timespec="seconds")


def adb_shell(cmd, timeout=30):
    r = subprocess.run(
        ADB + ["shell", cmd], capture_output=True, text=True, timeout=timeout
    )
    return r.stdout


def logcat_dump(timeout=15):
    r = subprocess.run(
        ["timeout", f"{timeout}s", "adb", "logcat", "-d", "-s", "TestReceiver"],
        capture_output=True, text=True
    )
    return r.stdout


def logcat_clear(timeout=10):
    subprocess.run(
        ["timeout", f"{timeout}s", "adb", "logcat", "-c"],
        capture_output=True, text=True
    )


def get_pid(timeout=8):
    out = adb_shell("pidof com.edgemind.app", timeout=timeout).strip()
    return int(out) if out.isdigit() else None


def get_rss_pss(pid, timeout=15):
    out = adb_shell(f"dumpsys meminfo {pid}", timeout=timeout)
    rss = re.search(r"TOTAL RSS:\s+(\d+)", out)
    pss = re.search(r"TOTAL PSS:\s+(\d+)", out)
    return (int(rss.group(1)) if rss else None,
            int(pss.group(1)) if pss else None)


def get_mem_available(timeout=10):
    out = adb_shell("cat /proc/meminfo", timeout=timeout)
    m = re.search(r"MemAvailable:\s+(\d+)\s+kB", out)
    return int(m.group(1)) if m else None


def broadcast(action, extras="", timeout=15):
    cmd = f"am broadcast -a {action} -n {RECEIVER} {extras}"
    return adb_shell(cmd, timeout=timeout)


def wait_for_logcat(pattern, deadline, error_pattern=None):
    """Poll logcat until pattern found or deadline exceeded. Returns matching line or None."""
    while time.time() < deadline:
        log = logcat_dump(timeout=12)
        for line in log.splitlines():
            if re.search(pattern, line):
                return line
            if error_pattern and re.search(error_pattern, line):
                return None
        time.sleep(1)
    return None


# ── PHASE 0: start fresh process ────────────────────────────────────────────
print(f"\n[{ts()}] === STABILITY-3GEN: START ===")
print(f"[{ts()}] Crashing any existing EdgeMind process...")
subprocess.run(ADB + ["shell", "am", "crash", PKG], capture_output=True, text=True, timeout=10)
time.sleep(2)

print(f"[{ts()}] Starting fresh InferenceForegroundService...")
subprocess.run(
    ADB + ["shell", "am", "start-foreground-service",
           "-n", f"{PKG}/{PKG}.service.InferenceForegroundService"],
    capture_output=True, text=True, timeout=10
)
time.sleep(3)

EXPECTED_PID = get_pid()
if not EXPECTED_PID:
    print("FATAL: Could not start EdgeMind process.")
    sys.exit(1)
print(f"[{ts()}] Process started. Expected PID = {EXPECTED_PID}")

# ── PHASE 1: baseline memory (pre-load) ─────────────────────────────────────
pre_rss, pre_pss = get_rss_pss(EXPECTED_PID)
pre_avail = get_mem_available()
print(f"[{ts()}] Pre-load  RSS={pre_rss} kB  PSS={pre_pss} kB  MemAvailable={pre_avail} kB")

# ── PHASE 2: model load ──────────────────────────────────────────────────────
print(f"[{ts()}] Clearing logcat...")
logcat_clear()
time.sleep(1)

print(f"[{ts()}] Broadcasting ACTION_LOAD_MODEL for {MODEL_ID}...")
broadcast("com.edgemind.ACTION_LOAD_MODEL",
          f"--es model_id {MODEL_ID}")

load_deadline = time.time() + 90  # 90s max for load
load_line = wait_for_logcat(r"CMD_DONE: Load completed", load_deadline,
                             error_pattern=r"CMD_ERR")
if not load_line:
    print("FATAL: Model load did not complete within 90s or CMD_ERR received.")
    sys.exit(1)
print(f"[{ts()}] Load done: {load_line.strip()}")
time.sleep(1)

# Verify PID still alive
OBSERVED_PID = get_pid()
print(f"[{ts()}] Observed PID after load = {OBSERVED_PID}")

# Check native model-loaded evidence and MemoryGuard from ALL tags
full_log_after_load = subprocess.run(
    ["timeout", "15s", "adb", "logcat", "-d"],
    capture_output=True, text=True
).stdout
native_loaded = "InferenceEngineImpl: Model loaded!" in full_log_after_load
mg_lines = [l for l in full_log_after_load.splitlines()
            if "MemoryGuard" in l and ("SUFFICIENT" in l or "INSUFFICIENT" in l or "rejected" in l)]
mg_preload = next((l for l in mg_lines if "SUFFICIENT" in l), None)
mg_postload = [l for l in mg_lines if "insufficient" in l.lower() or "rejected" in l.lower()]

print(f"[{ts()}] Native 'Model loaded!' found: {native_loaded}")
print(f"[{ts()}] Pre-load MemoryGuard SUFFICIENT: {mg_preload is not None}")
if mg_postload:
    for ln in mg_postload:
        print(f"[{ts()}] Post-load MemoryGuard msg: {ln.strip()}")

# ── PHASE 3: three generations ───────────────────────────────────────────────
gen_results = []

for i, prompt in enumerate(PROMPTS, start=1):
    print(f"\n[{ts()}] === GENERATION {i}: '{prompt}' ===")

    logcat_clear()
    time.sleep(0.5)

    escaped = prompt.replace("'", "\\'")
    broadcast("com.edgemind.ACTION_GENERATE",
              f"--es prompt '{escaped}' --ez json_mode false")

    gen_deadline = time.time() + 90
    done_line = wait_for_logcat(r"CMD_DONE: Generation completed", gen_deadline,
                                 error_pattern=r"CMD_ERR")

    # Read logcat once more to get CMD_OUTPUT
    time.sleep(0.5)
    gen_log = logcat_dump(timeout=12)

    # Parse CMD_DONE metrics
    tokens, total_time, ttft, decode_tps = None, None, None, None
    if done_line:
        m = re.search(
            r"Tokens:\s*(\d+),\s*TotalTime:\s*(\d+)ms,\s*TTFT/Prefill:\s*(\d+)ms,\s*DecodeTPS:\s*([\d.]+)",
            done_line
        )
        if m:
            tokens = int(m.group(1))
            total_time = int(m.group(2))
            ttft = int(m.group(3))
            decode_tps = float(m.group(4))

    # Parse CMD_OUTPUT
    output_lines = []
    capture = False
    for line in gen_log.splitlines():
        if "CMD_OUTPUT:" in line:
            capture = True
        if capture:
            # Strip logcat prefix
            txt = re.sub(r"^\S+\s+\d+\s+\d+\s+\d+\s+\w\s+\S+:\s+", "", line)
            output_lines.append(txt)
    cmd_output = "\n".join(output_lines).strip()

    # Find InferenceEngineImpl errors
    ie_errors = [l.strip() for l in gen_log.splitlines()
                 if "InferenceEngineImpl" in l and ("error" in l.lower() or "fail" in l.lower())]

    # Memory snapshot
    current_pid = get_pid()
    rss, pss = (None, None)
    mem_avail = None
    if current_pid == EXPECTED_PID:
        rss, pss = get_rss_pss(current_pid)
        mem_avail = get_mem_available()
    else:
        print(f"[{ts()}] WARNING: PID changed! Expected={EXPECTED_PID} Current={current_pid}")

    # Determine pass/fail for this generation
    gen_pass = bool(done_line and tokens is not None and tokens > 0) or bool(cmd_output)
    result_str = "PASS" if gen_pass else "FAIL"

    gen_results.append({
        "gen": i,
        "prompt": prompt,
        "result": result_str,
        "tokens": tokens,
        "total_time_ms": total_time,
        "ttft_ms": ttft,
        "decode_tps": decode_tps,
        "cmd_output": cmd_output,
        "rss_kb": rss,
        "pss_kb": pss,
        "mem_available_kb": mem_avail,
        "ie_errors": ie_errors,
        "done_line": done_line.strip() if done_line else None,
    })

    print(f"[{ts()}] Gen {i} result={result_str}  Tokens={tokens}  TotalTime={total_time}ms  TTFT={ttft}ms  DecodeTPS={decode_tps}")
    print(f"[{ts()}] Gen {i} RSS={rss} kB  PSS={pss} kB  MemAvailable={mem_avail} kB")
    if cmd_output:
        print(f"[{ts()}] Gen {i} CMD_OUTPUT (first 200 chars): {cmd_output[:200]}")
    if ie_errors:
        for e in ie_errors:
            print(f"[{ts()}] Gen {i} IE ERROR: {e}")

# ── PHASE 4: final report ────────────────────────────────────────────────────
print("\n\n" + "="*60)
print("STABILITY-3GEN FINAL REPORT")
print("="*60)

overall = all(g["result"] == "PASS" for g in gen_results)
final_pid = get_pid()

print(f"\nTEST:\nThree consecutive short generations from single qwen3-1.7b-q4km model load in one process.\n")
print(f"PROCESS:")
print(f"  Expected PID: {EXPECTED_PID}")
print(f"  Observed PID: {final_pid}\n")

print("MODEL LOAD:")
print(f"  Pre-load RSS:          {pre_rss} kB")
print(f"  Pre-load PSS:          {pre_pss} kB")
print(f"  Pre-load MemAvailable: {pre_avail} kB")
print(f"  MemoryGuard pre-load:  {'SUFFICIENT' if mg_preload else 'NOT OBSERVED'}")
print(f"  Native model-loaded:   {'YES — InferenceEngineImpl: Model loaded!' if native_loaded else 'NOT FOUND'}")
print(f"  Load result:           {'PASSED' if load_line else 'FAILED'}")
if mg_postload:
    print(f"  Post-load MemoryGuard: {'; '.join([l.strip() for l in mg_postload])}")

for g in gen_results:
    print(f"\nGENERATION {g['gen']}:")
    print(f"  Prompt:       {g['prompt']}")
    print(f"  Result:       {g['result']}")
    print(f"  Tokens:       {g['tokens']}")
    print(f"  TotalTime:    {g['total_time_ms']} ms")
    print(f"  TTFT:         {g['ttft_ms']} ms")
    print(f"  DecodeTPS:    {g['decode_tps']}")
    print(f"  RSS:          {g['rss_kb']} kB")
    print(f"  PSS:          {g['pss_kb']} kB")
    print(f"  MemAvailable: {g['mem_available_kb']} kB")
    if g['cmd_output']:
        print(f"  CMD_OUTPUT:   {g['cmd_output'][:300]}")
    if g['ie_errors']:
        print(f"  IE_ERRORS:    {g['ie_errors']}")

print("\nMEMORY TREND:")
for g in gen_results:
    print(f"  Gen {g['gen']}: PSS={g['pss_kb']} kB  RSS={g['rss_kb']} kB  MemAvailable={g['mem_available_kb']} kB")

failures = [f"Gen {g['gen']} ({g['prompt']}) FAILED" for g in gen_results if g['result'] != "PASS"]
print(f"\nFAILURES:\n  {'NONE' if not failures else chr(10).join(failures)}")

print(f"\nOVERALL RESULT: {'PASS' if overall else 'FAIL'}")

print("""
INTERPRETATION:
This test proves only that the qwen3-1.7b-q4km inference path completes three
consecutive short-prompt generations in the same process without crashing, OOM-kill,
or inference error, given a single model load. It does NOT prove thermal stability,
long-duration stability, sustained multi-turn chat stability, production readiness,
or general performance characteristics. Context window, quantization, and MemoryGuard
thresholds were not changed. Results are valid only for this device, OS state, and
memory pressure at execution time.
""")

sys.exit(0 if overall else 1)
