#!/bin/bash
set -e

# Configuration
PROMPT="Explain in comprehensive detail how transformer attention mechanisms work: the mathematical formulation of queries, keys, and values, scaled dot-product attention, softmax normalization, multi-head attention, positional encodings, feed-forward layers, residual connections, and layer normalization. Then compare encoder-only, decoder-only, and encoder-decoder architectures with real-world model examples for each. Finally, explain how modern optimizations like Flash Attention and grouped-query attention improve memory efficiency."
TARGET_TOKENS=300
MODEL_PATH="/sdcard/models/qwen2.5-3b-instruct-q4_k_m.gguf"
LOG_DIR_HOST="./phase9_results"

mkdir -p "$LOG_DIR_HOST/raw_logs"
mkdir -p "$LOG_DIR_HOST/thermal_logs"

# Helpers
get_max_cpu_temp() {
    adb shell 'for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case "$type" in cpu*|cpuss*) cat $z/temp 2>/dev/null;; esac; done' | awk 'BEGIN {max=0} {if ($1+0>max) max=$1+0} END {print max}'
}

get_battery_temp() {
    adb shell 'for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case "$type" in battery|bms) cat $z/temp 2>/dev/null;; esac; done' | awk 'BEGIN {max=0} {if ($1+0>max) max=$1+0} END {print max}'
}

wait_for_thermal_gate() {
    echo "--- THERMAL GATE ---"
    local start_wait=$(date +%s)
    while true; do
        local max_cpu=$(get_max_cpu_temp)
        local battery=$(get_battery_temp)
        echo "[$(date +%H:%M:%S)] Max CPU: ${max_cpu}mC, Battery: ${battery}mC"

        if [ "$max_cpu" -lt 40000 ] && [ "$battery" -lt 45000 ]; then
            local wait_time=$(($(date +%s) - start_wait))
            echo "Thermal gate CLEARED in ${wait_time}s"
            return 0
        fi
        echo "  → Waiting 60s for cool down..."
        sleep 60
    done
}

get_all_temps_inline() {
    adb shell 'for z in /sys/class/thermal/thermal_zone*; do type=$(cat $z/type 2>/dev/null); case "$type" in cpu*|cpuss*|battery|bms) printf "%s=%s " "$type" "$(cat $z/temp 2>/dev/null)";; esac; done'
}

run_experiment() {
    local run_id=$1
    local mask=$2
    local threads=$3

    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║  EXPERIMENT: $run_id  |  Mask: $mask  |  Threads: $threads"
    echo "╚═══════════════════════════════════════════════════════════════╝"

    # Thermal gate
    wait_for_thermal_gate

    local TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    local RAW_LOG="$LOG_DIR_HOST/raw_logs/${run_id}_${TIMESTAMP}.log"
    local THERMAL_LOG="$LOG_DIR_HOST/thermal_logs/${run_id}_thermal_timeline.csv"
    local META_LOG="$LOG_DIR_HOST/raw_logs/${run_id}_${TIMESTAMP}.meta"

    # Pre-run state
    echo "--- PRE-RUN STATE ---"
    local pre_mem=$(adb shell cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
    local pre_temps=$(get_all_temps_inline)
    echo "MemAvailable: ${pre_mem} kB"
    echo "Temps: $pre_temps"

    echo "pre_mem_kb=$pre_mem" > "$META_LOG"
    echo "pre_temps=$pre_temps" >> "$META_LOG"

    # Thermal log header
    echo "timestamp,elapsed_s,max_cpu_temp_mc,battery_temp_mc,status" > "$THERMAL_LOG"

    # Start thermal monitor in background
    local start_time=$(date +%s)
    local ABORT_FLAG="/tmp/phase9_abort_${run_id}"
    rm -f "$ABORT_FLAG"

    (
        while true; do
            local now=$(date +%s)
            local elapsed=$((now - start_time))
            local max_cpu=$(get_max_cpu_temp)
            local battery=$(get_battery_temp)
            local status="OK"

            if [ "$battery" -gt 48000 ]; then
                status="BATTERY_ABORT"
                echo "[SAFETY] BATTERY ABORT at ${battery}mC"
                adb shell pkill -9 llama-cli 2>/dev/null || true
                echo "$now,$elapsed,$max_cpu,$battery,$status" >> "$THERMAL_LOG"
                touch "$ABORT_FLAG"
                exit 1
            fi
            if [ "$max_cpu" -gt 85000 ]; then
                status="HARD_ABORT"
                echo "[SAFETY] HARD ABORT - CPU at ${max_cpu}mC"
                adb shell pkill -9 llama-cli 2>/dev/null || true
                echo "$now,$elapsed,$max_cpu,$battery,$status" >> "$THERMAL_LOG"
                touch "$ABORT_FLAG"
                exit 1
            elif [ "$max_cpu" -gt 83000 ]; then
                status="SOFT_HALT"
                echo "[THERMAL] WARNING approaching limit: ${max_cpu}mC @ ${elapsed}s"
            elif [ "$max_cpu" -gt 80000 ]; then
                status="WARN"
            fi

            echo "$now,$elapsed,$max_cpu,$battery,$status" >> "$THERMAL_LOG"
            echo "  [THERMAL @ ${elapsed}s] CPU=${max_cpu}mC Batt=${battery}mC ${status}"
            sleep 3
        done
    ) &
    local THERMAL_PID=$!
    echo "Thermal monitor PID: $THERMAL_PID"

    # Build inference command
    # Use --single-turn to avoid interactive chat mode
    # Use --no-display-prompt to reduce output noise
    local LLAMA_ARGS="-m $MODEL_PATH -t $threads -p \"$PROMPT\" -n $TARGET_TOKENS -c 1024 --single-turn --no-display-prompt --no-escape 2>&1"

    if [ "$mask" == "none" ]; then
        local FULL_CMD="LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/llama-cli $LLAMA_ARGS"
    else
        local FULL_CMD="LD_LIBRARY_PATH=/data/local/tmp taskset $mask /data/local/tmp/llama-cli $LLAMA_ARGS"
    fi

    echo "CMD: $FULL_CMD"
    echo "cmd=$FULL_CMD" >> "$META_LOG"

    # Run inference
    adb shell "$FULL_CMD" > "$RAW_LOG" 2>&1
    local exit_code=$?
    echo "exit_code=$exit_code" >> "$META_LOG"
    echo "Inference exit code: $exit_code"

    # Stop thermal monitor
    kill $THERMAL_PID 2>/dev/null || true
    wait $THERMAL_PID 2>/dev/null || true
    echo "Thermal monitor stopped."

    # Check for abort
    if [ -f "$ABORT_FLAG" ]; then
        echo "[!] Run was ABORTED by thermal monitor"
        echo "aborted=true" >> "$META_LOG"
        rm -f "$ABORT_FLAG"
    else
        echo "aborted=false" >> "$META_LOG"
    fi

    # Post-run state
    local post_mem=$(adb shell cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
    local post_temps=$(get_all_temps_inline)
    echo "post_mem_kb=$post_mem" >> "$META_LOG"
    echo "post_temps=$post_temps" >> "$META_LOG"
    echo "--- POST-RUN STATE ---"
    echo "MemAvailable: ${post_mem} kB"
    echo "Temps: $post_temps"

    # Show tail of raw log for quick inspection
    echo "--- RAW LOG TAIL (last 15 lines) ---"
    tail -15 "$RAW_LOG"

    # Mandatory cool-down
    echo ""
    echo ">>> Cooling down for 120 seconds... <<<"
    sleep 120
    local cooldown_temp=$(get_max_cpu_temp)
    echo "Post-cooldown CPU temp: ${cooldown_temp}mC"
    echo "cooldown_temp_mc=$cooldown_temp" >> "$META_LOG"
}

# ═══════════════════════════════════════════════════════════════════
# EXECUTE ALL EXPERIMENTS
# ═══════════════════════════════════════════════════════════════════
echo "Phase 1 starting at $(date)"
echo "Device: $(adb shell getprop ro.product.model)"

run_experiment "EXP-A" "f0" 4
run_experiment "EXP-B" "70" 3
run_experiment "EXP-C" "80" 1
run_experiment "EXP-D" "c0" 2
run_experiment "EXP-E" "0f" 4
run_experiment "EXP-F" "none" 6

echo ""
echo "════════════════════════════════════════════════════"
echo "  ALL EXPERIMENTS COMPLETED at $(date)"
echo "════════════════════════════════════════════════════"
