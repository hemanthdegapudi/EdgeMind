#!/bin/bash
set -uo pipefail

RESULTS_DIR="./phase9_results"
RAW_LOGS_DIR="${RESULTS_DIR}/raw_logs"
THERMAL_LOGS_DIR="${RESULTS_DIR}/thermal_logs"
mkdir -p "$RAW_LOGS_DIR" "$THERMAL_LOGS_DIR"

GATE_TEMP=40000
HARD_ABORT_TEMP=85000
BATTERY_GATE_TEMP=45000
MIN_COOLDOWN_SECS=30

TEST_PROMPT='What is AI?'
TARGET_TOKENS=20

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
get_cpu_max_temp() {
  local max_temp=0 temps
  temps=$(adb shell "cat /sys/class/thermal/thermal_zone[1-9]/temp /sys/class/thermal/thermal_zone1[0-4]/temp" 2>/dev/null | tr -d '\r')
  while IFS= read -r t; do
    t="${t//[^0-9]/}"; [[ -z "$t" ]] && continue
    (( t > max_temp )) && max_temp=$t
  done <<< "$temps"
  echo "$max_temp"
}
get_battery_temp() {
  local t=$(adb shell cat /sys/class/thermal/thermal_zone80/temp 2>/dev/null | tr -d '\r\n ')
  echo "${t//[^0-9]/}"
}
millideg_to_c() { echo "$(( $1 / 1000 )).$(( ($1 % 1000) / 100 ))"; }

thermal_gate() {
  local run_id="$1" waited=0
  log "[$run_id] THERMAL GATE — polling..."
  while true; do
    local cpu_max=$(get_cpu_max_temp)
    local batt=$(get_battery_temp)
    if (( cpu_max < GATE_TEMP && batt < BATTERY_GATE_TEMP )); then
      log "[$run_id] GATE CLEAR ✅"; return 0
    fi
    sleep 10; waited=$((waited + 10))
  done
}

thermal_monitor() {
  local run_id="$1" csv_file="$2" abort_flag_file="$3" stop_flag_file="$4" start_epoch=$(date +%s)
  echo "timestamp,elapsed_s,cpu_max_millideg,battery_millideg,cpu_max_c,battery_c,status" > "$csv_file"
  while true; do
    [[ -f "$stop_flag_file" ]] && break
    local now=$(date +%s)
    local elapsed=$(( now - start_epoch ))
    local cpu_max=$(get_cpu_max_temp)
    local batt=$(get_battery_temp)
    local cpu_c=$(millideg_to_c "$cpu_max")
    local batt_c=$(millideg_to_c "$batt")
    local status="OK"
    if (( cpu_max >= HARD_ABORT_TEMP )); then
      status="HARD_ABORT"
      adb shell killall llama-cli 2>/dev/null
      echo "CPU_HARD_ABORT:${cpu_c}" > "$abort_flag_file"; break
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S'),${elapsed},${cpu_max},${batt},${cpu_c},${batt_c},${status}" >> "$csv_file"
    sleep 3
  done
}

run_experiment() {
  local run_id="$1" mask="$2" threads="$3" desc="$4"
  local ts=$(date +%Y%m%d_%H%M%S)
  local raw_log="${RAW_LOGS_DIR}/${run_id}_${ts}.log"
  local thermal_csv="${THERMAL_LOGS_DIR}/${run_id}_thermal_timeline.csv"
  local abort_flag="/tmp/edgemind_abort_${run_id}_$$"
  local stop_flag="/tmp/edgemind_stop_${run_id}_$$"
  rm -f "$abort_flag" "$stop_flag"

  log "═══════════════════════════════════════════════════════════"
  log " ${run_id}: mask=${mask}  threads=${threads}  (${desc})"
  
  thermal_gate "$run_id"
  local pre_mem=$(adb shell "cat /proc/meminfo" 2>/dev/null | grep MemAvailable | awk '{print $2}')
  local pre_cpu_max=$(get_cpu_max_temp)
  
  thermal_monitor "$run_id" "$thermal_csv" "$abort_flag" "$stop_flag" &
  local monitor_pid=$!
  
  local cmd
  if [[ "$mask" == "none" ]]; then
    cmd="LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/llama-cli -m /sdcard/models/qwen2.5-3b-instruct-q4_k_m.gguf -t ${threads} -p '${TEST_PROMPT}' -n ${TARGET_TOKENS} -c 128 --log-disable 2>&1"
  else
    cmd="LD_LIBRARY_PATH=/data/local/tmp taskset ${mask} /data/local/tmp/llama-cli -m /sdcard/models/qwen2.5-3b-instruct-q4_k_m.gguf -t ${threads} -p '${TEST_PROMPT}' -n ${TARGET_TOKENS} -c 128 --log-disable 2>&1"
  fi

  log "[$run_id] INFERENCE START"
  local run_start=$(date +%s)
  local output
  output=$(adb shell "$cmd" 2>&1) || true
  local run_end=$(date +%s)
  local duration=$(( run_end - run_start ))
  
  touch "$stop_flag"; sleep 2; kill "$monitor_pid" 2>/dev/null || true
  
  local aborted="false" abort_reason="null"
  if [[ -f "$abort_flag" ]]; then
    aborted="true"; abort_reason="\"$(cat "$abort_flag")\""
  fi

  echo "$output" > "$raw_log"
  local post_mem=$(adb shell "cat /proc/meminfo" 2>/dev/null | grep MemAvailable | awk '{print $2}')
  
  local eval_tps=$(echo "$output" | grep "eval time" | grep -oP '[\d.]+(?=\s*tokens per second)' | tail -1)
  [[ -z "$eval_tps" ]] && eval_tps="null"
  local prompt_eval_tps=$(echo "$output" | grep "prompt eval time" | grep -oP '[\d.]+(?=\s*tokens per second)' | tail -1)
  [[ -z "$prompt_eval_tps" ]] && prompt_eval_tps="null"
  
  local peak_temp="null" peak_c="null"
  if [[ -f "$thermal_csv" ]]; then
    peak_temp=$(tail -n +2 "$thermal_csv" | cut -d',' -f3 | sort -rn | head -1)
    [[ -n "$peak_temp" && "$peak_temp" =~ ^[0-9]+$ ]] && peak_c=$(millideg_to_c "$peak_temp") || peak_temp="null"
  fi

  log "[$run_id] DONE (${duration}s). eval_tps=${eval_tps}, prompt_tps=${prompt_eval_tps}"

  cat > "${RESULTS_DIR}/${run_id}_metrics.json" << JSON
{
  "run_id": "${run_id}",
  "mask": "${mask}",
  "threads": ${threads},
  "eval_tps": ${eval_tps},
  "prompt_eval_tps": ${prompt_eval_tps},
  "peak_temp_c": ${peak_c},
  "run_duration_s": ${duration},
  "mem_before_kb": ${pre_mem},
  "mem_after_kb": ${post_mem},
  "aborted": ${aborted}
}
JSON
}

run_experiment "EXP-A" "f0" "4" "Gold3+Prime"
sleep $MIN_COOLDOWN_SECS
run_experiment "EXP-B" "70" "3" "Gold3_only"
sleep $MIN_COOLDOWN_SECS
run_experiment "EXP-C" "80" "1" "Prime_only"
sleep $MIN_COOLDOWN_SECS
run_experiment "EXP-D" "c0" "2" "1Gold+Prime"
sleep $MIN_COOLDOWN_SECS
run_experiment "EXP-E" "0f" "4" "Silver4_control"
sleep $MIN_COOLDOWN_SECS
run_experiment "EXP-F" "none" "6" "Scheduler_6t"

echo "🏁 Phase 9 runner finished."
