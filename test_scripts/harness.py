import subprocess
import time
import json
import os
import sys
import datetime
import threading
import re
import shlex
from typing import Optional, Dict, Any, List

class WatchdogException(Exception): pass
class AdbDisconnectException(Exception): pass

class Harness:
    def __init__(self, manifest_path: str = "validation/run_manifest.json"):
        self.manifest_path = manifest_path
        self.manifest = self._load_manifest()
        
        self.cmd_timeout = 30
        self.stage_timeout = 300
        
        self.setup_dirs()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None
        self._last_progress_timestamp = time.time()
        self._last_progress_event = "INITIALIZED"
        self._test_state_lock = threading.Lock()
        self._intervention_event = threading.Event()
        self.current_stage = None

    def setup_dirs(self):
        dirs = ["validation/baseline", "validation/memory", "validation/performance",
                "validation/thermal", "validation/switching", "validation/rag",
                "validation/tools", "validation/failure", "validation/chat",
                "validation/logs", "validation/raw", "validation/checkpoints", "validation/results"]
        for d in dirs: os.makedirs(d, exist_ok=True)

    def _load_manifest(self) -> Dict[str, Any]:
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {
            "campaign_id": datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp": datetime.datetime.now().isoformat(),
            "stages": {},
            "operator_interventions": 0
        }

    def _save_manifest(self):
        with open(self.manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def save_checkpoint(self, stage_name: str, state: Dict[str, Any]):
        chk_path = f"validation/checkpoints/{stage_name}_checkpoint.json"
        state["timestamp"] = datetime.datetime.now().isoformat()
        with open(chk_path, 'w') as f:
            json.dump(state, f, indent=2)
        if stage_name not in self.manifest["stages"]:
            self.manifest["stages"][stage_name] = {"status": "RUNNING"}
        self.manifest["stages"][stage_name]["last_checkpoint"] = chk_path
        self._save_manifest()

    def load_checkpoint(self, stage_name: str) -> Optional[Dict[str, Any]]:
        chk_path = f"validation/checkpoints/{stage_name}_checkpoint.json"
        if os.path.exists(chk_path):
            with open(chk_path, 'r') as f:
                return json.load(f)
        return None

    def log(self, message: str):
        print(f"[{datetime.datetime.now().isoformat()}] {message}", flush=True)

    def mark_progress(self, event: str):
        with self._test_state_lock:
            self._last_progress_timestamp = time.time()
            self._last_progress_event = event
            self.log(f"PROGRESS EVENT: {event}")

    def alarm_human_intervention(self, reason: str, state: Dict[str, Any]):
        self._intervention_event.set()
        self.manifest["operator_interventions"] += 1
        
        if self.current_stage:
            self.manifest["stages"][self.current_stage]["status"] = "PAUSED"
        self._save_manifest()
        
        print("\n" + "="*60)
        print("HUMAN INTERVENTION REQUIRED")
        print("="*60)
        print(f"Reason: {reason}")
        print("Current state:")
        for k, v in state.items(): print(f"  {k}: {v}")
        print("\nAction: Reconnect / unlock device / check logs.")
        print("\a\a\a", end="", flush=True) # ASCII bell
        
        while True:
            resp = input("Type 'c' to continue or 'a' to abort: ").strip().lower()
            if resp == 'c':
                print("Continuing...")
                if self.current_stage:
                    self.manifest["stages"][self.current_stage]["status"] = "RUNNING"
                    self._save_manifest()
                self._intervention_event.clear()
                self.mark_progress("RESUMED_AFTER_INTERVENTION")
                break
            elif resp == 'a':
                print("Aborting campaign.")
                if self.current_stage:
                    self.end_stage(self.current_stage, "ABORTED")
                sys.exit(1)

    def check_adb(self):
        try:
            result = subprocess.run(["adb", "get-state"], capture_output=True, text=True, timeout=5)
            if "device" not in result.stdout:
                raise AdbDisconnectException("ADB device not found or offline.")
        except subprocess.TimeoutExpired:
             raise AdbDisconnectException("ADB get-state timed out.")
        except Exception as e:
             raise AdbDisconnectException(f"ADB check failed: {e}")

    def run_cmd(self, cmd: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        to = timeout if timeout else self.cmd_timeout
        self.check_adb()
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=to)
        except subprocess.TimeoutExpired as e:
            state = self.capture_diagnostic_state()
            state["cmd"] = cmd
            state["timeout"] = to
            self.alarm_human_intervention("Command timeout expired", state)
            raise e
        except Exception as e:
            state = self.capture_diagnostic_state()
            state["cmd"] = cmd
            self.alarm_human_intervention(f"Command execution failed: {e}", state)
            raise e

    def run_adb_shell(self, shell_cmd: str, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        return self.run_cmd(["adb", "shell", shell_cmd], timeout)

    def get_pid(self) -> Optional[int]:
        result = self.run_adb_shell("pidof com.edgemind.app", timeout=5).stdout.strip()
        if result.isdigit():
            return int(result)
        return None

    def start_fresh_process(self) -> int:
        self.log("Crashing existing process to ensure fresh state...")
        self.run_adb_shell("am crash com.edgemind.app", timeout=10)
        time.sleep(2)
        self.log("Starting fresh process...")
        self.run_adb_shell("am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService", timeout=10)
        time.sleep(3)
        pid = self.get_pid()
        if not pid:
            raise Exception("Failed to start fresh EdgeMind process")
        self.current_pid = pid
        self.log(f"Started fresh process with PID: {pid}")
        return pid

    def get_device_metrics(self) -> Dict[str, Any]:
        metrics = {}
        try:
            actual_pid = self.get_pid()
            
            expected_pid = getattr(self, 'current_pid', None)
            if expected_pid is not None:
                if actual_pid != expected_pid:
                    metrics["pid_match"] = False
                    metrics["error"] = f"PID changed or died! Expected {expected_pid}, got {actual_pid}"
                    metrics["measurement_status"] = "FAILED"
                    return metrics
                metrics["pid_match"] = True
            
            metrics["pid"] = actual_pid if actual_pid else "UNAVAILABLE"
            
            if actual_pid:
                meminfo = self.run_adb_shell(f"dumpsys meminfo {actual_pid}", timeout=5).stdout
                rss_match = re.search(r"TOTAL RSS:\s+(\d+)", meminfo)
                metrics["rss_kb"] = int(rss_match.group(1)) if rss_match else "UNAVAILABLE"
                
                pss_match = re.search(r"TOTAL PSS:\s+(\d+)", meminfo)
                metrics["pss_kb"] = int(pss_match.group(1)) if pss_match else "UNAVAILABLE"
            else:
                metrics["rss_kb"] = "UNAVAILABLE"
                metrics["pss_kb"] = "UNAVAILABLE"
            
            procmem = self.run_adb_shell("cat /proc/meminfo", timeout=5).stdout
            avail_match = re.search(r"MemAvailable:\s+(\d+)\s+kB", procmem)
            metrics["mem_available_kb"] = int(avail_match.group(1)) if avail_match else "UNAVAILABLE"
            
            therm = self.run_adb_shell("for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case \"$type\" in cpu*|cpuss*) cat $z/temp 2>/dev/null;; esac; done", timeout=5).stdout
            temps = [int(t) for t in therm.split() if t.isdigit()]
            metrics["cpu_temp"] = max(temps) if temps else "UNAVAILABLE"
            
            freq = self.run_adb_shell("cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq", timeout=5).stdout
            freqs = [int(f) for f in freq.split() if f.isdigit()]
            metrics["cpu_freq"] = max(freqs) if freqs else "UNAVAILABLE"
            
            bat = self.run_adb_shell("dumpsys battery", timeout=5).stdout
            bat_match = re.search(r"level:\s+(\d+)", bat)
            metrics["battery"] = int(bat_match.group(1)) if bat_match else "UNAVAILABLE"
        except Exception as e:
            metrics["error"] = str(e)
            metrics["measurement_status"] = "FAILED"
        return metrics

    def capture_diagnostic_state(self) -> Dict[str, Any]:
        state = {}
        try:
            state["adb_state"] = subprocess.run(["adb", "get-state"], capture_output=True, text=True, timeout=5).stdout.strip()
            state["top"] = self.run_adb_shell("top -n 1 -m 10", timeout=5).stdout
            state["dmesg_tail"] = self.run_adb_shell("dmesg | tail -n 20", timeout=5).stdout
            state.update(self.get_device_metrics())
        except Exception as e:
            state["diagnostic_error"] = str(e)
        return state

    def load_model_with_peak_memory_tracking(self, model_id: str, timeout_sec: int = 60, interval_sec: float = 0.2) -> Dict[str, Any]:
        self.run_cmd(["timeout", "30s", "adb", "logcat", "-c"])

        expected_pid = getattr(self, 'current_pid', None)
        if not expected_pid:
            expected_pid = self.get_pid()
            self.current_pid = expected_pid

        if not expected_pid:
            return {"status": "FAILED", "error": "No running process"}

        baseline_metrics = self.get_device_metrics()
        
        self.log(f"Starting model load for {model_id} with peak memory tracking...")
        start_time = time.time()
        self.run_cmd(["timeout", "30s", "adb", "shell", "am", "broadcast", "-a", "com.edgemind.ACTION_LOAD_MODEL", "-n", "com.edgemind.app/.TestReceiver", "--es", "model_id", model_id])
        
        peak_rss = baseline_metrics.get("rss_kb", 0)
        if not isinstance(peak_rss, int): peak_rss = 0
        peak_pss = baseline_metrics.get("pss_kb", 0)
        if not isinstance(peak_pss, int): peak_pss = 0
        
        status = "TIMEOUT"
        error_msg = ""
        load_time_ms = 0
        
        while time.time() - start_time < timeout_sec:
            loop_start = time.time()
            
            combined_cmd = f"pidof com.edgemind.app && run-as com.edgemind.app cat /proc/{expected_pid}/smaps_rollup"
            try:
                out = self.run_adb_shell(combined_cmd, timeout=3).stdout
            except Exception as e:
                # Ignore transient timeouts during load, just continue sampling
                out = ""
            
            if out and "Rss:" in out:
                rss_match = re.search(r"^Rss:\s+(\d+)\s+kB", out, re.MULTILINE)
                pss_match = re.search(r"^Pss:\s+(\d+)\s+kB", out, re.MULTILINE)
                
                curr_rss = int(rss_match.group(1)) if rss_match else 0
                curr_pss = int(pss_match.group(1)) if pss_match else 0
                
                if curr_rss > peak_rss: peak_rss = curr_rss
                if curr_pss > peak_pss: peak_pss = curr_pss
            elif out and str(expected_pid) not in out.splitlines()[0]:
                status = "FAILED"
                error_msg = f"PID changed or died. Expected {expected_pid}, got: {out.splitlines()[0]}"
                break
                
            try:
                log_out = self.run_cmd(["timeout", "2s", "adb", "logcat", "-d", "-s", "TestReceiver"], timeout=3).stdout
            except Exception as e:
                log_out = ""
            
            done = False
            for line in log_out.splitlines():
                if "CMD_DONE: Load completed" in line:
                    status = "PASSED"
                    match = re.search(r"in (\d+)ms", line)
                    if match:
                        load_time_ms = int(match.group(1))
                    done = True
                    break
                elif "CMD_ERR" in line:
                    status = "FAILED"
                    error_msg = line.strip()
                    done = True
                    break
                    
            if done:
                break
                
            elapsed = time.time() - loop_start
            sleep_time = interval_sec - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
        time.sleep(1) # Let things settle
        final_metrics = self.get_device_metrics()
        
        return {
            "status": status,
            "error": error_msg,
            "expected_pid": expected_pid,
            "observed_pid_final": final_metrics.get("pid", "UNAVAILABLE"),
            "load_time_ms": load_time_ms,
            "duration_sec": time.time() - start_time,
            "baseline": {
                "rss_kb": baseline_metrics.get("rss_kb"),
                "pss_kb": baseline_metrics.get("pss_kb"),
                "mem_available_kb": baseline_metrics.get("mem_available_kb")
            },
            "peak": {
                "rss_kb": peak_rss,
                "pss_kb": peak_pss
            },
            "final": {
                "rss_kb": final_metrics.get("rss_kb"),
                "pss_kb": final_metrics.get("pss_kb"),
                "mem_available_kb": final_metrics.get("mem_available_kb")
            }
        }

    def start_heartbeat(self, test_name: str, interval: int = 10, max_no_progress_sec: int = 120):
        self._heartbeat_stop.clear()
        self.mark_progress("HEARTBEAT_STARTED")
        
        def beat():
            iteration = 0
            while not self._heartbeat_stop.is_set():
                if self._intervention_event.is_set():
                    time.sleep(1)
                    continue
                
                try:
                    self.check_adb()
                    metrics = self.get_device_metrics()
                    
                    with self._test_state_lock:
                        idle_time = time.time() - self._last_progress_timestamp
                    
                    if idle_time > max_no_progress_sec:
                        self.alarm_human_intervention(f"Watchdog: No progress for {int(idle_time)}s", self.capture_diagnostic_state())
                        continue

                    msg = (f"[HEARTBEAT] ts={datetime.datetime.now().isoformat()} "
                           f"test={test_name} iter={iteration} idle={int(idle_time)}s event={self._last_progress_event} "
                           f"PID={metrics.get('pid')} RSS={metrics.get('rss_kb')} PSS={metrics.get('pss_kb')} "
                           f"MemAvail={metrics.get('mem_available_kb')} Temp={metrics.get('cpu_temp')} "
                           f"Freq={metrics.get('cpu_freq')} Bat={metrics.get('battery')}")
                    print(msg, flush=True)
                except AdbDisconnectException as e:
                    self.alarm_human_intervention("Watchdog: ADB Disconnected during test", {"error": str(e)})
                except Exception as e:
                    self.alarm_human_intervention("Watchdog: Unexpected Heartbeat error", {"error": str(e)})
                
                for _ in range(interval):
                    if self._heartbeat_stop.is_set(): break
                    time.sleep(1)
                iteration += 1

        self._heartbeat_thread = threading.Thread(target=beat, daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        if self._heartbeat_thread:
            self._heartbeat_stop.set()
            self._heartbeat_thread.join()
            self._heartbeat_thread = None

    def begin_stage(self, stage_name: str, force_rerun: bool = False) -> bool:
        stage_info = self.manifest["stages"].get(stage_name, {})
        status = stage_info.get("status")
        
        # INCONCLUSIVE MUST NEVER BE AUTOMATICALLY SKIPPED
        if status == "PASSED" and not force_rerun:
            self.log(f"Stage {stage_name} already completed with status {status}. Skipping.")
            return False
            
        if status in ["FAILED", "BLOCKED"] and not force_rerun:
            self.log(f"Stage {stage_name} previously {status}. Not continuing automatically.")
            return False

        self.log(f"Starting stage: {stage_name}")
        self.current_stage = stage_name
        self.manifest["stages"][stage_name] = {"status": "RUNNING"}
        self._save_manifest()
        return True

    def end_stage(self, stage_name: str, status: str):
        valid_statuses = ["NOT_STARTED", "RUNNING", "PAUSED", "PASSED", "FAILED", "BLOCKED", "INCONCLUSIVE", "ABORTED"]
        if status not in valid_statuses:
            status = "INCONCLUSIVE"
        
        self.manifest["stages"][stage_name]["status"] = status
        self._save_manifest()
        if self.current_stage == stage_name:
            self.current_stage = None

    def record_result(self, test_id: str, status: str, metrics: Dict[str, Any], errors: List[str] = None, duration: float = 0.0):
        result = {
            "campaign_id": self.manifest.get("campaign_id", "UNKNOWN"),
            "test_id": test_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "device": "Android",
            "model": metrics.get("model", "UNKNOWN"),
            "iteration": metrics.get("iteration", 1),
            "stage": self.current_stage,
            "status": status,
            "metrics": metrics,
            "errors": errors or [],
            "operator_intervention": self.manifest.get("operator_interventions", 0),
            "duration": duration
        }
        res_file = f"validation/results/{test_id}_{int(time.time())}.json"
        with open(res_file, 'w') as f:
            json.dump(result, f, indent=2)
        self.log(f"Recorded result for {test_id}: {status}")

    def capture_raw_evidence(self, name: str, stdout: str, stderr: str = "", logcat: str = ""):
        timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        evidence = {
            "stdout": stdout,
            "stderr": stderr,
            "logcat": logcat,
            "timestamp": timestamp
        }
        raw_path = f"validation/raw/{name}_{timestamp}_evidence.json"
        with open(raw_path, 'w') as f:
            json.dump(evidence, f, indent=2)

