import sys
import re

with open("test_scripts/harness.py", "r") as f:
    content = f.read()

# Replace run_cmd
new_run_cmd = """
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=to)
            # Do not throw on non-zero exit code here, let the caller validate exit-code
            return result
        except subprocess.TimeoutExpired as e:
            # Capture state before pausing
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

    def get_device_metrics(self):
        metrics = {}
        try:
            meminfo = subprocess.run(["adb", "shell", "dumpsys", "meminfo", "com.edgemind.app"], capture_output=True, text=True, timeout=5).stdout
            rss_match = re.search(r"TOTAL RSS:\\s+(\\d+)", meminfo)
            pss_match = re.search(r"TOTAL PSS:\\s+(\\d+)", meminfo)
            metrics["rss_kb"] = int(rss_match.group(1)) if rss_match else 0
            metrics["pss_kb"] = int(pss_match.group(1)) if pss_match else 0
            
            procmem = subprocess.run(["adb", "shell", "cat", "/proc/meminfo"], capture_output=True, text=True, timeout=5).stdout
            avail_match = re.search(r"MemAvailable:\\s+(\\d+)\\s+kB", procmem)
            metrics["mem_available_kb"] = int(avail_match.group(1)) if avail_match else 0
            
            pid_match = re.search(r"pid\\s+(\\d+)", meminfo)
            metrics["pid"] = int(pid_match.group(1)) if pid_match else -1
            
            therm = subprocess.run(["adb", "shell", "'for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case \"$type\" in cpu*|cpuss*) cat $z/temp 2>/dev/null;; esac; done'"], capture_output=True, text=True, timeout=5).stdout
            temps = [int(t) for t in therm.split() if t.isdigit()]
            metrics["cpu_temp"] = max(temps) if temps else 0
            
            freq = subprocess.run(["adb", "shell", "cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq"], capture_output=True, text=True, timeout=5).stdout
            freqs = [int(f) for f in freq.split() if f.isdigit()]
            metrics["cpu_freq"] = max(freqs) if freqs else 0
            
            bat = subprocess.run(["adb", "shell", "dumpsys", "battery"], capture_output=True, text=True, timeout=5).stdout
            bat_match = re.search(r"level:\\s+(\\d+)", bat)
            metrics["battery"] = int(bat_match.group(1)) if bat_match else 0
        except:
            pass
        return metrics

    def capture_diagnostic_state(self):
        state = {}
        try:
            state["adb_state"] = subprocess.run(["adb", "get-state"], capture_output=True, text=True, timeout=5).stdout.strip()
            state["top"] = subprocess.run(["adb", "shell", "top", "-n", "1", "-m", "10"], capture_output=True, text=True, timeout=5).stdout
            state["dmesg_tail"] = subprocess.run(["adb", "shell", "dmesg", "|", "tail", "-n", "20"], capture_output=True, text=True, timeout=5).stdout
            state.update(self.get_device_metrics())
        except:
            pass
        return state
"""

content = re.sub(r"    def check_adb\(self\):.*?        except Exception as e:.*?             raise AdbDisconnectException\(f\"ADB check failed: \{e\}\"\)\n\n    def run_cmd\(self, cmd: List\[str\], timeout: Optional\[int\] = None\) -> subprocess\.CompletedProcess:.*?            raise", new_run_cmd, content, flags=re.DOTALL)

# Replace start_heartbeat
new_heartbeat = """
    def start_heartbeat(self, test_name: str, interval: int = 10, current_model: str = "unknown"):
        self._heartbeat_stop.clear()
        self.current_model = current_model
        self.last_op = "started"
        
        def beat():
            iteration = 0
            start_time = time.time()
            while not self._heartbeat_stop.is_set():
                try:
                    self.check_adb()
                    metrics = self.get_device_metrics()
                    elapsed = int(time.time() - start_time)
                    msg = (f"[HEARTBEAT] ts={datetime.datetime.now().isoformat()} "
                           f"test={test_name} iter={iteration} elapsed={elapsed}s "
                           f"model={self.current_model} last_op={self.last_op} "
                           f"PID={metrics.get('pid', 'N/A')} "
                           f"RSS={metrics.get('rss_kb', 0)}kB PSS={metrics.get('pss_kb', 0)}kB "
                           f"MemAvail={metrics.get('mem_available_kb', 0)}kB "
                           f"Temp={metrics.get('cpu_temp', 0)} Freq={metrics.get('cpu_freq', 0)} "
                           f"Bat={metrics.get('battery', 0)}%")
                    print(msg, flush=True)
                except AdbDisconnectException as e:
                    print(f"\\n[WATCHDOG] ADB Disconnected during {test_name}! Pause required.", flush=True)
                    # Trigger watchdog by simulating timeout? 
                    # For a thread, it's safer to just log and let main thread fail on next command.
                except Exception as e:
                    print(f"\\n[WATCHDOG] Heartbeat error: {e}", flush=True)
                
                # Check for stop every second to respond quickly
                for _ in range(interval):
                    if self._heartbeat_stop.is_set():
                        break
                    time.sleep(1)
                iteration += 1

        self._heartbeat_thread = threading.Thread(target=beat, daemon=True)
        self._heartbeat_thread.start()
"""

content = re.sub(r"    def start_heartbeat\(self, test_name: str, interval: int = 10\):.*?        self._heartbeat_thread\.start\(\)", new_heartbeat, content, flags=re.DOTALL)

with open("test_scripts/harness.py", "w") as f:
    f.write(content)
