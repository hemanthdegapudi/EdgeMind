import re
import subprocess
import json

def run_adb(cmd):
    try:
        r = subprocess.run(f"adb shell {cmd}", shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout
    except Exception as e:
        return str(e)

def test_parsing():
    print("=== OBJECTIVE 7 & 8: Parser Verification ===")
    
    # 1. RSS and PSS
    meminfo = run_adb("dumpsys meminfo com.edgemind.app")
    print("\nRAW dumpsys meminfo output:")
    # print only lines containing TOTAL
    for line in meminfo.split('\n'):
        if "TOTAL" in line:
            print(f"RAW: {line}")
            
    rss_match = re.search(r"TOTAL RSS:\s+(\d+)", meminfo)
    print(f"Parsed TOTAL RSS: {rss_match.group(1) if rss_match else 'None'} KB")
    pss_match = re.search(r"TOTAL PSS:\s+(\d+)", meminfo)
    print(f"Parsed TOTAL PSS: {pss_match.group(1) if pss_match else 'None'} KB")
    
    pid_match = re.search(r"\*\* MEMINFO in pid (\d+)", meminfo)
    print(f"Parsed PID from dumpsys: {pid_match.group(1) if pid_match else 'None'}")
    
    # 2. Native heap
    for line in meminfo.split('\n'):
        if line.strip().startswith("Native Heap"):
            print(f"RAW Native Heap: {line}")
            parts = line.split()
            if len(parts) >= 8:
                print(f"Parsed Native Heap Allocated: {parts[6]} KB")
                print(f"Parsed Native Heap Free: {parts[7]} KB")
                print(f"Parsed Native Heap Size: {parts[5]} KB")
                
    # 3. /proc/meminfo
    procmem = run_adb("cat /proc/meminfo")
    for line in procmem.split('\n'):
        if "MemAvailable" in line or "MemFree" in line or "Cached" in line or "SwapFree" in line or "ZRam" in line:
            print(f"RAW /proc/meminfo: {line}")
    avail_match = re.search(r"MemAvailable:\s+(\d+)\s+kB", procmem)
    print(f"Parsed MemAvailable: {avail_match.group(1) if avail_match else 'None'} KB")

    # 4. Thermal
    therm = run_adb("for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case \"$type\" in cpu*|cpuss*) echo \"RAW THERM $z: $type $(cat $z/temp 2>/dev/null)\";; esac; done")
    print(therm)
    
    # 5. CPU freq
    freq = run_adb("cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")
    print("RAW CPU FREQ:")
    print(freq.strip()[:100])
    
    # 6. Battery
    bat = run_adb("dumpsys battery")
    for line in bat.split('\n'):
        if "level:" in line:
            print(f"RAW Battery: {line}")
            
    # 7. PSI
    print("\nRAW PSI:")
    psi_mem = run_adb("cat /proc/pressure/memory")
    print(f"PSI Memory: {psi_mem.strip()}")

if __name__ == "__main__":
    test_parsing()
