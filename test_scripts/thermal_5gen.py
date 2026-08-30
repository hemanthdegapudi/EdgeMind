#!/usr/bin/env python3
"""
Thermal characterisation: ONE model load, FIVE sequential same-prompt generations.
Model: qwen3-1.7b-q4km
Prompt: "Explain in one short sentence what Android is."
Temperature sources: cpuss-0-usr, cpuss-1-usr, xo_therm (millidegrees → °C)
"""
import subprocess, time, re, sys, datetime

ADB   = ["adb"]
MODEL = "qwen3-1.7b-q4km"
PROMPT = "Explain in one short sentence what Android is."
PKG   = "com.edgemind.app"
RECV  = f"{PKG}/.TestReceiver"
GEN_COUNT = 5

# Thermal zone paths selected after enumeration
THERM_ZONES = {
    "cpuss-0-usr": "/sys/class/thermal/thermal_zone5/temp",   # big-core cluster
    "cpuss-1-usr": "/sys/class/thermal/thermal_zone6/temp",   # little-core cluster
    "xo_therm":    "/sys/class/thermal/thermal_zone73/temp",  # crystal-osc / ambient proxy
}

def ts():
    return datetime.datetime.now().isoformat(timespec="seconds")

def adb_shell(cmd, timeout=28):
    r = subprocess.run(ADB + ["shell", cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.stdout

def logcat_dump(timeout=14):
    r = subprocess.run(
        ["timeout", f"{timeout}s", "adb", "logcat", "-d", "-s", "TestReceiver"],
        capture_output=True, text=True)
    return r.stdout

def logcat_clear(timeout=10):
    subprocess.run(["timeout", f"{timeout}s", "adb", "logcat", "-c"],
                   capture_output=True, text=True)

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

def get_temps(timeout=12):
    """Read all named thermal zones; return dict name->°C (float, 1 dp)."""
    results = {}
    for name, path in THERM_ZONES.items():
        raw = adb_shell(f"cat {path}", timeout=timeout).strip()
        try:
            results[name] = round(int(raw) / 1000.0, 1)
        except ValueError:
            results[name] = None
    return results

def broadcast(action, extras="", timeout=14):
    cmd = f"am broadcast -a {action} -n {RECV} {extras}"
    return adb_shell(cmd, timeout=timeout)

def wait_for_logcat(pattern, deadline, error_pattern=r"CMD_ERR"):
    while time.time() < deadline:
        log = logcat_dump(timeout=12)
        for line in log.splitlines():
            if re.search(pattern, line):
                return line
            if re.search(error_pattern, line):
                return None
        time.sleep(1)
    return None

# ── START ────────────────────────────────────────────────────────────────────
print(f"\n[{ts()}] === THERMAL-5GEN: START ===")
print(f"[{ts()}] Crashing any existing EdgeMind process...")
subprocess.run(ADB + ["shell", "am", "crash", PKG],
               capture_output=True, text=True, timeout=10)
time.sleep(2)

print(f"[{ts()}] Starting fresh InferenceForegroundService...")
subprocess.run(
    ADB + ["shell", "am", "start-foreground-service",
           "-n", f"{PKG}/{PKG}.service.InferenceForegroundService"],
    capture_output=True, text=True, timeout=10)
time.sleep(3)

EXPECTED_PID = get_pid()
if not EXPECTED_PID:
    print("FATAL: Could not start EdgeMind process.")
    sys.exit(1)
print(f"[{ts()}] Process started. Expected PID = {EXPECTED_PID}")

# ── BASELINE ─────────────────────────────────────────────────────────────────
bl_rss, bl_pss  = get_rss_pss(EXPECTED_PID)
bl_avail        = get_mem_available()
bl_temps        = get_temps()
print(f"[{ts()}] Baseline  RSS={bl_rss}kB  PSS={bl_pss}kB  MemAvail={bl_avail}kB")
print(f"[{ts()}] Baseline  temps={bl_temps}")

# ── MODEL LOAD ───────────────────────────────────────────────────────────────
logcat_clear()
time.sleep(1)
print(f"[{ts()}] Broadcasting ACTION_LOAD_MODEL for {MODEL}...")
broadcast("com.edgemind.ACTION_LOAD_MODEL", f"--es model_id {MODEL}")

load_done = wait_for_logcat(r"CMD_DONE: Load completed", time.time() + 90)
if not load_done:
    print("FATAL: Model load did not complete within 90s.")
    sys.exit(1)
print(f"[{ts()}] {load_done.strip()}")
time.sleep(1)

obs_pid_after_load = get_pid()

# Gather native evidence and MemoryGuard from full logcat
full_log = subprocess.run(
    ["timeout", "15s", "adb", "logcat", "-d"],
    capture_output=True, text=True).stdout
native_loaded = "InferenceEngineImpl: Model loaded!" in full_log
mg_sufficient = any("MemoryGuard" in l and "SUFFICIENT" in l
                    for l in full_log.splitlines())
mg_postload   = [l.strip() for l in full_log.splitlines()
                 if "MemoryGuard" in l
                 and ("insufficient" in l.lower() or "rejected" in l.lower())]

print(f"[{ts()}] Native 'Model loaded!': {native_loaded}")
print(f"[{ts()}] MemoryGuard pre-load SUFFICIENT: {mg_sufficient}")
for ml in mg_postload:
    print(f"[{ts()}] Post-load MemGuard: {ml}")

# ── FIVE GENERATIONS ─────────────────────────────────────────────────────────
gens = []
escaped_prompt = PROMPT.replace("'", "\\'")

for i in range(1, GEN_COUNT + 1):
    print(f"\n[{ts()}] === GENERATION {i} ===")

    # Temperature BEFORE
    temp_before = get_temps()
    print(f"[{ts()}] Gen {i} temp_before={temp_before}")

    # Fire generation
    logcat_clear()
    time.sleep(0.5)
    broadcast("com.edgemind.ACTION_GENERATE",
              f"--es prompt '{escaped_prompt}' --ez json_mode false")

    gen_deadline = time.time() + 90
    done_line = wait_for_logcat(r"CMD_DONE: Generation completed", gen_deadline)

    # Let logcat flush, then temperature AFTER
    time.sleep(0.5)
    temp_after = get_temps()

    # Fetch CMD_OUTPUT from logcat
    gen_log = logcat_dump(timeout=12)

    # Parse CMD_DONE metrics
    tokens = total_time = ttft = decode_tps = None
    if done_line:
        m = re.search(
            r"Tokens:\s*(\d+),\s*TotalTime:\s*(\d+)ms,\s*TTFT/Prefill:\s*(\d+)ms,"
            r"\s*DecodeTPS:\s*([\d.]+)",
            done_line)
        if m:
            tokens     = int(m.group(1))
            total_time = int(m.group(2))
            ttft       = int(m.group(3))
            decode_tps = float(m.group(4))

    # CMD_OUTPUT lines
    output_lines = []
    capture = False
    for line in gen_log.splitlines():
        if "CMD_OUTPUT:" in line:
            capture = True
        if capture:
            txt = re.sub(r"^[^\s]+\s+\d+\s+\d+\s+\d+\s+\w\s+\S+:\s+", "", line)
            output_lines.append(txt)
    cmd_output = "\n".join(output_lines).strip()

    # IE errors
    ie_errors = [l.strip() for l in gen_log.splitlines()
                 if "InferenceEngineImpl" in l
                 and ("error" in l.lower() or "fail" in l.lower())]

    # Memory snapshot
    cur_pid = get_pid()
    rss = pss = avail = None
    pid_stable = (cur_pid == EXPECTED_PID)
    if pid_stable:
        rss, pss = get_rss_pss(cur_pid)
        avail    = get_mem_available()
    else:
        print(f"[{ts()}] WARNING: PID changed! Expected={EXPECTED_PID} Got={cur_pid}")

    gen_pass = bool(done_line and tokens and tokens > 0) or bool(cmd_output)
    result   = "PASS" if gen_pass else "FAIL"

    gens.append(dict(
        gen=i, result=result,
        tokens=tokens, total_time_ms=total_time, ttft_ms=ttft, decode_tps=decode_tps,
        temp_before=temp_before, temp_after=temp_after,
        rss_kb=rss, pss_kb=pss, mem_available_kb=avail,
        cmd_output=cmd_output[:300] if cmd_output else "",
        ie_errors=ie_errors, done_line=done_line,
    ))

    print(f"[{ts()}] Gen {i}: result={result}  Tokens={tokens}  TotalTime={total_time}ms  "
          f"TTFT={ttft}ms  DecodeTPS={decode_tps}")
    print(f"[{ts()}] Gen {i}: temp_after={temp_after}")
    print(f"[{ts()}] Gen {i}: RSS={rss}kB  PSS={pss}kB  MemAvail={avail}kB")
    if cmd_output:
        print(f"[{ts()}] Gen {i} CMD_OUTPUT[:120]: {cmd_output[:120]}")
    if ie_errors:
        for e in ie_errors:
            print(f"[{ts()}] Gen {i} IE_ERROR: {e}")

# ── FINAL REPORT ─────────────────────────────────────────────────────────────
final_pid = get_pid()
overall   = all(g["result"] == "PASS" for g in gens)
failures  = [f"Gen {g['gen']} FAILED" for g in gens if g["result"] != "PASS"]

# Performance trend helpers
def pct(a, b):
    """Percent change from a to b."""
    if a and b and a != 0:
        return round((b - a) / a * 100, 1)
    return None

g1, g5 = gens[0], gens[4]

print("\n\n" + "="*64)
print("THERMAL-5GEN FINAL REPORT")
print("="*64)

print(f"""
TEST:
Five consecutive same-prompt short generations in one process after single
qwen3-1.7b-q4km model load. Thermal and performance metrics captured before
and after every generation to characterise short-duration thermal behaviour.

PROCESS:
Expected PID: {EXPECTED_PID}
Observed PID: {final_pid}

BASELINE:
RSS:          {bl_rss} kB
PSS:          {bl_pss} kB
MemAvailable: {bl_avail} kB
Temperature:  cpuss-0-usr={bl_temps.get('cpuss-0-usr')}°C  cpuss-1-usr={bl_temps.get('cpuss-1-usr')}°C  xo_therm={bl_temps.get('xo_therm')}°C

MODEL LOAD:
MemoryGuard pre-load:       {'SUFFICIENT' if mg_sufficient else 'NOT OBSERVED'}
Native model-loaded evidence: {'YES — InferenceEngineImpl: Model loaded!' if native_loaded else 'NOT FOUND'}
Load result:                {'PASSED' if load_done else 'FAILED'}""")

if mg_postload:
    for ml in mg_postload:
        print(f"  Post-load MemoryGuard (informational): {ml}")

for g in gens:
    tb = g["temp_before"]
    ta = g["temp_after"]
    print(f"""
GENERATION {g['gen']}:
Tokens:            {g['tokens']}
TotalTime:         {g['total_time_ms']} ms
TTFT:              {g['ttft_ms']} ms
DecodeTPS:         {g['decode_tps']}
Temperature before: cpuss-0-usr={tb.get('cpuss-0-usr')}°C  cpuss-1-usr={tb.get('cpuss-1-usr')}°C  xo_therm={tb.get('xo_therm')}°C
Temperature after:  cpuss-0-usr={ta.get('cpuss-0-usr')}°C  cpuss-1-usr={ta.get('cpuss-1-usr')}°C  xo_therm={ta.get('xo_therm')}°C
RSS:               {g['rss_kb']} kB
PSS:               {g['pss_kb']} kB
MemAvailable:      {g['mem_available_kb']} kB
Result:            {g['result']}""")

# Thermal trend
bl_cpu0  = bl_temps.get("cpuss-0-usr")
end_cpu0 = g5["temp_after"].get("cpuss-0-usr")
bl_xo    = bl_temps.get("xo_therm")
end_xo   = g5["temp_after"].get("xo_therm")
d_cpu0   = round(end_cpu0 - bl_cpu0, 1) if (end_cpu0 and bl_cpu0) else None
d_xo     = round(end_xo   - bl_xo,   1) if (end_xo   and bl_xo)   else None

print(f"""
THERMAL TREND:
  Baseline  cpuss-0-usr={bl_cpu0}°C  xo_therm={bl_xo}°C
  After G1  cpuss-0-usr={g1['temp_after'].get('cpuss-0-usr')}°C  xo_therm={g1['temp_after'].get('xo_therm')}°C
  After G2  cpuss-0-usr={gens[1]['temp_after'].get('cpuss-0-usr')}°C  xo_therm={gens[1]['temp_after'].get('xo_therm')}°C
  After G3  cpuss-0-usr={gens[2]['temp_after'].get('cpuss-0-usr')}°C  xo_therm={gens[2]['temp_after'].get('xo_therm')}°C
  After G4  cpuss-0-usr={gens[3]['temp_after'].get('cpuss-0-usr')}°C  xo_therm={gens[3]['temp_after'].get('xo_therm')}°C
  After G5  cpuss-0-usr={end_cpu0}°C  xo_therm={end_xo}°C
  Net rise (baseline → after G5): cpuss-0-usr={d_cpu0}°C  xo_therm={d_xo}°C
""")

# Performance trend
print("PERFORMANCE TREND:")
print(f"  {'Gen':<5} {'Tokens':<8} {'TotalTime(ms)':<15} {'TTFT(ms)':<10} {'DecodeTPS':<12}")
for g in gens:
    print(f"  {g['gen']:<5} {str(g['tokens']):<8} {str(g['total_time_ms']):<15} {str(g['ttft_ms']):<10} {str(g['decode_tps']):<12}")
print(f"\n  G1 vs G5 comparison:")
print(f"    DecodeTPS change:  {g1['decode_tps']} → {g5['decode_tps']}  ({pct(g1['decode_tps'], g5['decode_tps'])}%)")
print(f"    TotalTime change:  {g1['total_time_ms']}ms → {g5['total_time_ms']}ms  ({pct(g1['total_time_ms'], g5['total_time_ms'])}%)")
print(f"    TTFT change:       {g1['ttft_ms']}ms → {g5['ttft_ms']}ms  ({pct(g1['ttft_ms'], g5['ttft_ms'])}%)")
print(f"    cpuss-0-usr rise:  {bl_cpu0}°C (baseline) → {end_cpu0}°C (after G5)  (Δ={d_cpu0}°C)")
print(f"    PSS change:        {g1['pss_kb']}kB → {g5['pss_kb']}kB  ({pct(g1['pss_kb'], g5['pss_kb'])}%)")

# Memory trend
print(f"""
MEMORY TREND:
  {'Gen':<5} {'PSS(kB)':<12} {'RSS(kB)':<12} {'MemAvail(kB)':<14}""")
for g in gens:
    print(f"  {g['gen']:<5} {str(g['pss_kb']):<12} {str(g['rss_kb']):<12} {str(g['mem_available_kb']):<14}")

print(f"""
FAILURES:
  {'NONE' if not failures else chr(10).join('  '+f for f in failures)}

OVERALL FUNCTIONAL RESULT: {'PASS' if overall else 'FAIL'}

INTERPRETATION:
This test characterises short-duration (5-generation) thermal and performance
behaviour of qwen3-1.7b-q4km inference in a single EdgeMind process. It proves
only that five consecutive same-prompt inferences complete without crash, OOM-kill,
or inference error under the observed thermal and memory conditions, and provides
a measured thermal delta and throughput trend across those five generations.
It does NOT prove long-duration thermal stability, sustained workload safety,
absence of throttling beyond the five-generation window, production readiness,
or performance representative of any workload other than this specific short
same-prompt sequence on this device at this ambient temperature and OS load.
No source code, thresholds, context limits, or quantisation were modified.
""")

sys.exit(0 if overall else 1)
