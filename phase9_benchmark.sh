#!/bin/bash
# ============================================================
# EdgeMind Phase 9 Benchmark Runner
# ============================================================
# Purpose: Deterministic, non-interactive GGUF inference benchmark
# Device:  Xiaomi Redmi K20 Pro (Snapdragon 855)
# Model:   Qwen2.5 3B Instruct Q4_K_M
# Binary:  llama-cli v0.2.0-dev (build 10588)
#
# PRESERVES: phase9_runner.sh, run_experiments.sh (historical)
# ============================================================
set -uo pipefail

# === CONFIGURATION ===
MODEL_PATH="/data/local/tmp/qwen2.5-3b-instruct-q4_k_m.gguf"
LLAMA_CLI="/data/local/tmp/llama-cli"
LD_PATH="/data/local/tmp"

TEST_PROMPT="What is artificial intelligence? Explain briefly."
TARGET_TOKENS=50
CTX_SIZE=512
SEED=42
TEMP=0

RESULTS_DIR="./phase9_results/run_$(date +%Y%m%d_%H%M%S)"
RAW_LOGS_DIR="${RESULTS_DIR}/raw_logs"
THERMAL_LOGS_DIR="${RESULTS_DIR}/thermal_logs"
METRICS_DIR="${RESULTS_DIR}/metrics"

GATE_TEMP=45000        # 45°C CPU gate
HARD_ABORT_TEMP=85000  # 85°C hard abort
BATTERY_GATE_TEMP=40000 # 40°C battery gate
MIN_COOLDOWN_SECS=60

REPS=${1:-3}  # Number of repetitions per experiment (default 3)

# === SETUP ===
mkdir -p "$RAW_LOGS_DIR" "$THERMAL_LOGS_DIR" "$METRICS_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${RESULTS_DIR}/session.log"; }

# === THERMAL FUNCTIONS ===
get_cpu_max_temp() {
    adb shell 'for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case "$type" in cpu*|cpuss*) cat $z/temp 2>/dev/null;; esac; done' 2>/dev/null | awk 'BEGIN {max=0} {if ($1+0>max) max=$1+0} END {print max}'
}

get_battery_temp() {
    local t
    t=$(adb shell cat /sys/class/thermal/thermal_zone80/temp 2>/dev/null | tr -d '\r\n ')
    echo "${t//[^0-9-]/}"
}

millideg_to_c() {
    local val="${1:-0}"
    if [[ -z "$val" || "$val" == "0" ]]; then
        echo "0.0"
    else
        echo "$(( val / 1000 )).$(( (val % 1000) / 100 ))"
    fi
}

# === THERMAL GATE ===
thermal_gate() {
    local run_id="$1"
    log "[$run_id] THERMAL GATE — waiting for CPU < ${GATE_TEMP}mC and Battery < ${BATTERY_GATE_TEMP}mC"
    local waited=0
    while true; do
        local cpu_max
        cpu_max=$(get_cpu_max_temp)
        local batt
        batt=$(get_battery_temp)
        if (( cpu_max < GATE_TEMP && batt < BATTERY_GATE_TEMP )); then
            log "[$run_id] GATE CLEAR ✅ (CPU=${cpu_max}mC, Batt=${batt}mC, waited=${waited}s)"
            return 0
        fi
        log "[$run_id] Gate: CPU=${cpu_max}mC, Batt=${batt}mC — waiting 15s..."
        sleep 15
        waited=$((waited + 15))
    done
}

# === THERMAL MONITOR (background) ===
thermal_monitor() {
    local run_id="$1" csv_file="$2" abort_flag_file="$3" stop_flag_file="$4"
    local start_epoch
    start_epoch=$(date +%s)
    echo "timestamp,elapsed_s,cpu_max_mc,battery_mc,cpu_max_c,battery_c,status" > "$csv_file"

    while true; do
        [[ -f "$stop_flag_file" ]] && break
        local now elapsed cpu_max batt cpu_c batt_c status
        now=$(date +%s)
        elapsed=$(( now - start_epoch ))
        cpu_max=$(get_cpu_max_temp)
        batt=$(get_battery_temp)
        cpu_c=$(millideg_to_c "$cpu_max")
        batt_c=$(millideg_to_c "$batt")
        status="OK"

        if (( cpu_max >= HARD_ABORT_TEMP )); then
            status="HARD_ABORT"
            adb shell "pkill -9 llama-cli" 2>/dev/null || true
            echo "${status}:cpu=${cpu_c}" > "$abort_flag_file"
        elif (( cpu_max > 83000 )); then
            status="WARN_HIGH"
        elif (( cpu_max > 80000 )); then
            status="WARN"
        fi

        echo "$(date '+%Y-%m-%d %H:%M:%S'),${elapsed},${cpu_max},${batt},${cpu_c},${batt_c},${status}" >> "$csv_file"

        [[ "$status" == "HARD_ABORT" ]] && break
        sleep 3
    done
}

# === EFFECTIVE AFFINITY CHECK ===
get_effective_affinity() {
    # Find llama-cli PID and read its actual CPU mask
    local pid
    pid=$(adb shell "pidof llama-cli" 2>/dev/null | tr -d '\r\n ')
    if [[ -n "$pid" && "$pid" =~ ^[0-9]+$ ]]; then
        local mask_hex mask_list
        mask_hex=$(adb shell "cat /proc/${pid}/status" 2>/dev/null | grep 'Cpus_allowed:' | awk '{print $2}' | tr -d '\r\n ')
        mask_list=$(adb shell "cat /proc/${pid}/status" 2>/dev/null | grep 'Cpus_allowed_list:' | awk '{print $2}' | tr -d '\r\n ')
        echo "pid=${pid} mask=${mask_hex} list=${mask_list}"
    else
        echo "pid=UNKNOWN"
    fi
}

# === SINGLE EXPERIMENT RUN ===
run_single() {
    local exp_id="$1" mask="$2" threads="$3" rep="$4"
    local run_id="${exp_id}_rep${rep}"
    local ts
    ts=$(date +%Y%m%d_%H%M%S)

    local raw_log="${RAW_LOGS_DIR}/${run_id}_${ts}.log"
    local thermal_csv="${THERMAL_LOGS_DIR}/${run_id}_${ts}_thermal.csv"
    local metrics_file="${METRICS_DIR}/${run_id}_${ts}_metrics.json"
    local abort_flag="/tmp/edgemind_abort_${run_id}_$$"
    local stop_flag="/tmp/edgemind_stop_${run_id}_$$"
    rm -f "$abort_flag" "$stop_flag"

    log "═══════════════════════════════════════════════════"
    log " ${run_id}: mask=${mask} threads=${threads} [${ts}]"
    log "═══════════════════════════════════════════════════"

    # Thermal gate
    thermal_gate "$run_id"

    # Pre-run measurements
    local pre_mem pre_cpu_temp pre_batt_temp
    pre_mem=$(adb shell cat /proc/meminfo 2>/dev/null | grep MemAvailable | awk '{print $2}' | tr -d '\r')
    pre_cpu_temp=$(get_cpu_max_temp)
    pre_batt_temp=$(get_battery_temp)
    log "[$run_id] PRE: MemAvail=${pre_mem}kB CPU=${pre_cpu_temp}mC Batt=${pre_batt_temp}mC"

    # Start thermal monitor
    thermal_monitor "$run_id" "$thermal_csv" "$abort_flag" "$stop_flag" &
    local monitor_pid=$!

    # Build inference command
    # Key flags:
    #   --single-turn -p "prompt"  → non-interactive single generation
    #   --perf                     → enable llama_print_timings
    #   --no-display-prompt        → don't echo the prompt
    #   --seed 42 --temp 0         → deterministic greedy sampling
    #   --no-warmup                → skip warmup for consistent timing
    #   --cpu-mask M               → built-in CPU affinity (when not "none")
    local cmd
    if [[ "$mask" == "none" ]]; then
        cmd="LD_LIBRARY_PATH=${LD_PATH} ${LLAMA_CLI} \
            -m ${MODEL_PATH} \
            -t ${threads} \
            -p \"${TEST_PROMPT}\" \
            -n ${TARGET_TOKENS} \
            -c ${CTX_SIZE} \
            --seed ${SEED} \
            --temp ${TEMP} \
            --single-turn \
            --perf \
            --no-display-prompt \
            --no-warmup \
            --log-disable \
            2>&1"
    else
        cmd="LD_LIBRARY_PATH=${LD_PATH} taskset ${mask} ${LLAMA_CLI} \
            -m ${MODEL_PATH} \
            -t ${threads} \
            -p \"${TEST_PROMPT}\" \
            -n ${TARGET_TOKENS} \
            -c ${CTX_SIZE} \
            --seed ${SEED} \
            --temp ${TEMP} \
            --single-turn \
            --perf \
            --no-display-prompt \
            --no-warmup \
            --log-disable \
            2>&1"
    fi

    log "[$run_id] CMD: $(echo $cmd | tr -s ' ')"
    log "[$run_id] INFERENCE START"

    local run_start run_end duration
    run_start=$(date +%s)

    # Run inference — capture all output
    local output exit_code
    output=$(adb shell "$cmd" 2>&1) || true
    exit_code=$?
    run_end=$(date +%s)
    duration=$(( run_end - run_start ))

    # Check effective affinity (may still catch a lingering process, best-effort)
    local effective_affinity="UNKNOWN"
    # Since inference just finished, try to capture from the run output instead

    # Stop thermal monitor
    touch "$stop_flag"
    sleep 2
    kill "$monitor_pid" 2>/dev/null || true
    wait "$monitor_pid" 2>/dev/null || true

    # Check abort
    local aborted="false" abort_reason="null"
    if [[ -f "$abort_flag" ]]; then
        aborted="true"
        abort_reason="\"$(cat "$abort_flag")\""
        rm -f "$abort_flag"
    fi
    rm -f "$stop_flag"

    # Save raw log
    echo "$output" > "$raw_log"

    # Post-run measurements
    local post_mem post_cpu_temp post_batt_temp
    post_mem=$(adb shell cat /proc/meminfo 2>/dev/null | grep MemAvailable | awk '{print $2}' | tr -d '\r')
    post_cpu_temp=$(get_cpu_max_temp)
    post_batt_temp=$(get_battery_temp)

    # Extract timing from llama.cpp output
    # Format: [ Prompt: X.X t/s | Generation: Y.Y t/s ]
    local eval_tps prompt_tps eval_tokens prompt_tokens
    eval_tps=$(echo "$output" | grep -oP 'Generation:\s*[\d.]+' | grep -oP '[\d.]+' | tail -1)
    prompt_tps=$(echo "$output" | grep -oP 'Prompt:\s*[\d.]+' | grep -oP '[\d.]+' | tail -1)
    # Token counts not in compact format — use target values
    eval_tokens="${TARGET_TOKENS}"
    prompt_tokens="null"
    # Also try the detailed format (older builds): eval time ... tokens per second
    if [[ -z "$eval_tps" ]]; then
        eval_tps=$(echo "$output" | grep 'eval time' | grep -v 'prompt' | grep -oP '[\d.]+(?=\s*tokens per second)' | tail -1)
        prompt_tps=$(echo "$output" | grep 'prompt eval time' | grep -oP '[\d.]+(?=\s*tokens per second)' | tail -1)
        eval_tokens=$(echo "$output" | grep 'eval time' | grep -v 'prompt' | grep -oP '(\d+)\s*tokens' | grep -oP '^\d+' | tail -1)
        prompt_tokens=$(echo "$output" | grep 'prompt eval time' | grep -oP '(\d+)\s*tokens' | grep -oP '^\d+' | tail -1)
    fi

    [[ -z "$eval_tps" ]] && eval_tps="null"
    [[ -z "$prompt_tps" ]] && prompt_tps="null"
    [[ -z "$eval_tokens" ]] && eval_tokens="null"
    [[ -z "$prompt_tokens" ]] && prompt_tokens="null"

    # Extract peak thermal from CSV
    local peak_cpu_temp="null"
    if [[ -f "$thermal_csv" ]]; then
        peak_cpu_temp=$(tail -n +2 "$thermal_csv" | cut -d',' -f3 | sort -rn | head -1)
        [[ -z "$peak_cpu_temp" || ! "$peak_cpu_temp" =~ ^[0-9]+$ ]] && peak_cpu_temp="null"
    fi

    # Determine validity
    local valid="true"
    local invalid_reason="null"
    if [[ "$eval_tps" == "null" ]]; then
        valid="false"
        invalid_reason="\"no_timing_output\""
    fi
    if [[ "$aborted" == "true" ]]; then
        valid="false"
        invalid_reason="\"thermal_abort\""
    fi

    log "[$run_id] DONE (${duration}s) eval_tps=${eval_tps} prompt_tps=${prompt_tps} valid=${valid}"

    # Write metrics JSON
    cat > "$metrics_file" <<JSON
{
    "run_id": "${run_id}",
    "timestamp": "${ts}",
    "experiment": "${exp_id}",
    "repetition": ${rep},
    "requested_mask": "${mask}",
    "threads": ${threads},
    "model_path": "${MODEL_PATH}",
    "prompt": "${TEST_PROMPT}",
    "target_tokens": ${TARGET_TOKENS},
    "ctx_size": ${CTX_SIZE},
    "seed": ${SEED},
    "temp": ${TEMP},
    "eval_tps": ${eval_tps},
    "prompt_eval_tps": ${prompt_tps},
    "eval_tokens": ${eval_tokens},
    "prompt_tokens": ${prompt_tokens},
    "wall_clock_s": ${duration},
    "pre_mem_avail_kb": ${pre_mem:-0},
    "post_mem_avail_kb": ${post_mem:-0},
    "mem_delta_kb": $(( ${pre_mem:-0} - ${post_mem:-0} )),
    "pre_cpu_temp_mc": ${pre_cpu_temp},
    "post_cpu_temp_mc": ${post_cpu_temp},
    "peak_cpu_temp_mc": ${peak_cpu_temp},
    "pre_batt_temp_mc": ${pre_batt_temp},
    "post_batt_temp_mc": ${post_batt_temp},
    "aborted": ${aborted},
    "abort_reason": ${abort_reason},
    "valid": ${valid},
    "invalid_reason": ${invalid_reason},
    "exit_code": ${exit_code},
    "raw_log": "${raw_log}",
    "thermal_csv": "${thermal_csv}"
}
JSON
}

# === EXPERIMENT RUNNER ===
run_experiment() {
    local exp_id="$1" mask="$2" threads="$3"
    log ""
    log "╔═══════════════════════════════════════════════════════╗"
    log "║  EXPERIMENT: ${exp_id}  |  Mask: ${mask}  |  Threads: ${threads}"
    log "╚═══════════════════════════════════════════════════════╝"

    for rep in $(seq 1 "$REPS"); do
        run_single "$exp_id" "$mask" "$threads" "$rep"
    done
}

# === PRE-FLIGHT CHECKS ===
log "============================================"
log " EdgeMind Phase 9 Benchmark"
log " $(date)"
log "============================================"

# Verify device
device_model=$(adb shell getprop ro.product.model 2>/dev/null | tr -d '\r')
if [[ -z "$device_model" ]]; then
    log "BLOCKED: No device connected"
    exit 1
fi
log "Device: ${device_model}"
log "Android: $(adb shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')"

# Verify model
model_check=$(adb shell "ls -l ${MODEL_PATH}" 2>/dev/null | tr -d '\r')
if [[ -z "$model_check" ]]; then
    log "BLOCKED: Model not found at ${MODEL_PATH}"
    exit 1
fi
log "Model: ${model_check}"

# Verify binary
binary_check=$(adb shell "ls -l ${LLAMA_CLI}" 2>/dev/null | tr -d '\r')
if [[ -z "$binary_check" ]]; then
    log "BLOCKED: llama-cli not found at ${LLAMA_CLI}"
    exit 1
fi
log "Binary: ${binary_check}"

# Record environment
adb shell cat /proc/meminfo > "${RESULTS_DIR}/meminfo_start.txt" 2>/dev/null
adb shell cat /sys/devices/system/cpu/online > "${RESULTS_DIR}/cpu_online.txt" 2>/dev/null
adb shell cat /proc/self/status > "${RESULTS_DIR}/shell_status.txt" 2>/dev/null

log "Results dir: ${RESULTS_DIR}"
log "Repetitions per experiment: ${REPS}"
log ""

# === EXECUTE EXPERIMENTS ===
# run_experiment "EXP-A" "f0" 4
# run_experiment "EXP-B" "70" 3
# run_experiment "EXP-C" "80" 1
run_experiment "EXP-D" "c0" 2
run_experiment "EXP-E" "0f" 4
run_experiment "EXP-F" "none" 6

log ""
log "════════════════════════════════════════════"
log "  ALL EXPERIMENTS COMPLETED at $(date)"
log "════════════════════════════════════════════"
