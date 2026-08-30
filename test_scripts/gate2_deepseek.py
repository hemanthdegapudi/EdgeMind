import subprocess, time, re, sys, threading, json

def ts():
    return time.strftime("%H:%M:%S")

def run_cmd(cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["timeout", "5s", "sh", "-c", "echo -e '\\a'"])
        print(f"TIMEOUT on cmd: {' '.join(cmd)}")
        return None
    except Exception as e:
        print(f"ERROR on cmd {' '.join(cmd)}: {e}")
        return None

def run_shell(cmd_str, timeout=30):
    return run_cmd(["timeout", f"{timeout}s", "adb", "shell", cmd_str], timeout=timeout+2)

def get_pid():
    res = run_shell("pidof com.edgemind.app", timeout=10)
    if res and res.stdout.strip().isdigit():
        return int(res.stdout.strip())
    return None

def start_fresh_process():
    run_shell("am crash com.edgemind.app", timeout=10)
    time.sleep(2)
    run_shell("am force-stop com.edgemind.app", timeout=10)
    time.sleep(2)
    run_shell("am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService", timeout=10)
    time.sleep(3)
    return get_pid()

def get_mem_available():
    res = run_shell("cat /proc/meminfo", timeout=5)
    if res:
        m = re.search(r"MemAvailable:\s+(\d+)\s+kB", res.stdout)
        if m: return int(m.group(1))
    return None

def get_smaps(pid):
    cmd = f"run-as com.edgemind.app cat /proc/{pid}/smaps_rollup || cat /proc/{pid}/smaps_rollup"
    res = run_shell(cmd, timeout=5)
    rss, pss = None, None
    if res and res.stdout:
        r_match = re.search(r"^Rss:\s+(\d+)\s+kB", res.stdout, re.MULTILINE)
        p_match = re.search(r"^Pss:\s+(\d+)\s+kB", res.stdout, re.MULTILINE)
        if r_match: rss = int(r_match.group(1))
        if p_match: pss = int(p_match.group(1))
    return rss, pss

class PeakSampler:
    def __init__(self, pid):
        self.pid = pid
        self.running = True
        self.peak_rss = 0
        self.peak_pss = 0
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._loop)
        self.thread.daemon = True
        
    def start(self):
        self.thread.start()
        
    def stop(self):
        self.running = False
        self.thread.join(timeout=5)
        
    def _loop(self):
        while self.running:
            rss, pss = get_smaps(self.pid)
            with self.lock:
                if rss and rss > self.peak_rss: self.peak_rss = rss
                if pss and pss > self.peak_pss: self.peak_pss = pss
            time.sleep(0.5)
            
    def get_peaks(self):
        with self.lock:
            return self.peak_rss, self.peak_pss

def broadcast(action, extras):
    run_shell(f"am broadcast -a {action} -n com.edgemind.app/.TestReceiver {extras}", timeout=10)

def main():
    MODEL_ID = "deepseek-r1-distill-qwen-1.5b-q5km"
    PROMPT = "Hello"
    cycles_data = []
    
    for cycle in range(1, 6):
        print(f"\n[{ts()}] === CYCLE {cycle} ===")
        pid = start_fresh_process()
        if not pid:
            print(f"[{ts()}] Cycle {cycle} failed to get fresh PID.")
            cycles_data.append({"cycle": cycle, "error": "Failed to get fresh PID"})
            continue
            
        print(f"[{ts()}] Fresh PID: {pid}")
        
        run_cmd(["timeout", "10s", "adb", "logcat", "-c"], timeout=15)
        time.sleep(1)
        
        base_rss, base_pss = get_smaps(pid)
        base_avail = get_mem_available()
        
        print(f"[{ts()}] Baseline RSS={base_rss} PSS={base_pss} MemAvailable={base_avail}")
        
        sampler = PeakSampler(pid)
        if base_rss: sampler.peak_rss = base_rss
        if base_pss: sampler.peak_pss = base_pss
        sampler.start()
        
        # Load
        broadcast("com.edgemind.ACTION_LOAD_MODEL", f"--es model_id {MODEL_ID}")
        load_start = time.time()
        
        loaded = False
        load_time_ms = 0
        while time.time() - load_start < 120:
            logs = run_cmd(["timeout", "5s", "adb", "logcat", "-d"], timeout=10)
            if logs and "InferenceEngineImpl: Model loaded!" in logs.stdout:
                loaded = True
                
            if logs and "CMD_DONE: Load completed" in logs.stdout:
                m = re.search(r"in (\d+)ms", logs.stdout)
                if m: load_time_ms = int(m.group(1))
                loaded = True
                break
            time.sleep(1)
            
        if not loaded:
            sampler.stop()
            print(f"[{ts()}] Cycle {cycle} failed: Model load timeout/error")
            cycles_data.append({"cycle": cycle, "error": "Model load timeout/error"})
            continue
            
        print(f"[{ts()}] Model loaded! Time={load_time_ms}ms")
        
        # Logcat clear
        run_cmd(["timeout", "10s", "adb", "logcat", "-c"], timeout=15)
        time.sleep(1)
        
        # Generate
        broadcast("com.edgemind.ACTION_GENERATE", f"--es prompt '{PROMPT}' --ez json_mode false --ei context_budget 512")
        gen_start = time.time()
        
        gen_done = False
        done_line = None
        full_log = ""
        while time.time() - gen_start < 120:
            logs = run_cmd(["timeout", "5s", "adb", "logcat", "-d"], timeout=10)
            if logs and "CMD_DONE:" in logs.stdout:
                full_log = logs.stdout
                lines = full_log.splitlines()
                for l in lines:
                    if "CMD_DONE:" in l:
                        done_line = l
                gen_done = True
                break
            time.sleep(1)
            
        time.sleep(2) # Settle for output
        if gen_done:
            logs = run_cmd(["timeout", "5s", "adb", "logcat", "-d"], timeout=10)
            if logs: full_log = logs.stdout
            
        sampler.stop()
        
        fin_rss, fin_pss = get_smaps(pid)
        fin_avail = get_mem_available()
        peak_rss, peak_pss = sampler.get_peaks()
        if fin_rss and fin_rss > peak_rss: peak_rss = fin_rss
        if fin_pss and fin_pss > peak_pss: peak_pss = fin_pss
        
        print(f"[{ts()}] Final RSS={fin_rss} PSS={fin_pss} MemAvailable={fin_avail}")
        
        if not gen_done:
            print(f"[{ts()}] Cycle {cycle} failed: Generation timeout/error")
            cycles_data.append({"cycle": cycle, "error": "Generation timeout/error"})
            continue
            
        # Parse metrics
        tokens, total_time, ttft, tps = 0, 0, 0, 0.0
        if done_line:
            m = re.search(r"Tokens:\s*(\d+),\s*TotalTime:\s*(\d+)ms,\s*TTFT/Prefill:\s*(\d+)ms,\s*DecodeTPS:\s*([\d.]+)", done_line)
            if m:
                tokens = int(m.group(1))
                total_time = int(m.group(2))
                ttft = int(m.group(3))
                tps = float(m.group(4))
                
        # CMD_OUTPUT
        cmd_output = ""
        capture = False
        out_lines = []
        for l in full_log.splitlines():
            if "CMD_OUTPUT:" in l:
                capture = True
            if capture:
                txt = re.sub(r"^\S+\s+\d+\s+\d+\s+\d+\s+\w\s+\S+:\s+", "", l)
                out_lines.append(txt)
        cmd_output = "\n".join(out_lines).strip()
        
        # Verify success
        res = "FAIL"
        if tokens > 0 or cmd_output:
            res = "PASS"
            
        cycles_data.append({
            "cycle": cycle,
            "pid": pid,
            "base_rss": base_rss,
            "base_pss": base_pss,
            "base_avail": base_avail,
            "peak_rss": peak_rss,
            "peak_pss": peak_pss,
            "fin_rss": fin_rss,
            "fin_pss": fin_pss,
            "fin_avail": fin_avail,
            "load_time": load_time_ms,
            "tokens": tokens,
            "ttft": ttft,
            "tps": tps,
            "output": cmd_output,
            "result": res
        })
        
        print(f"[{ts()}] Cycle {cycle} RESULT={res} Tokens={tokens} TPS={tps}")

    with open("validation/results/gate2_deepseek.json", "w") as f:
        json.dump(cycles_data, f, indent=2)
        
    print(f"\n[{ts()}] DONE.")

if __name__ == "__main__":
    main()
