#!/bin/bash

# Target MemAvailable values to test
TARGETS=(3.0 2.8 2.6 2.5 2.4 2.3 2.25 2.2 2.15 2.1 2.0)
RESULTS_FILE="phase10_5_threshold_validation/results/threshold_matrix.csv"
echo "Target_GiB,Actual_GiB,MemoryGuard,Model_Load,Inference,Min_Mem_Inference_GiB,Result" > $RESULTS_FILE

for target in "${TARGETS[@]}"; do
    echo "========================================="
    echo "Testing target: $target GiB"
    
    adb shell killall -9 mem_pressure >/dev/null 2>&1
    adb shell am force-stop com.edgemind.app
    sleep 3
    
    avail_kb=$(adb shell cat /proc/meminfo | grep MemAvailable | awk '{print $2}')
    avail_gb=$(echo "scale=3; $avail_kb / 1024 / 1024" | bc)
    
    diff_gb=$(echo "scale=3; $avail_gb - $target" | bc)
    
    if (( $(echo "$diff_gb > 0.05" | bc -l) )); then
        diff_mb=$(echo "scale=0; $diff_gb * 1024 / 1" | bc)
        echo "Creating memory pressure of $diff_mb MB..."
        adb shell "/data/local/tmp/mem_pressure $diff_mb" > /dev/null 2>&1 &
        pressure_pid=$!
        sleep 5
    else
        echo "No pressure needed or unable to reach target."
        pressure_pid=0
    fi
    
    adb logcat -c
    adb shell am start-foreground-service -n com.edgemind.app/.service.InferenceForegroundService
    
    timeout=60
    mg_result="-"
    load_result="-"
    inf_result="-"
    min_mem="-"
    final_res="TIMEOUT"
    actual_gb="-"
    
    while [ $timeout -gt 0 ]; do
        sleep 2
        logs=$(adb logcat -d)
        
        # Extract Actual memory from MemoryGuard log
        act_mem=$(echo "$logs" | grep "Memory refresh: availMem=" | head -1 | grep -oE "availMem=[0-9.]+ GiB" | grep -oE "[0-9.]+")
        if [ ! -z "$act_mem" ] && [ "$actual_gb" = "-" ]; then
            actual_gb=$act_mem
            echo "MemoryGuard recorded starting mem: $actual_gb GiB"
        fi
        
        if echo "$logs" | grep -q "Engine initialization deferred"; then
            mg_result="REJECTED"
            final_res="MemoryGuard expected rejection"
            break
        fi
        
        if echo "$logs" | grep -q "P10.4_MODEL_LOAD_START"; then
            mg_result="ALLOW"
        fi
        
        if echo "$logs" | grep -q "P10.4_MODEL_LOAD_SUCCESS"; then
            load_result="SUCCESS"
        fi
        
        if echo "$logs" | grep -q "P10.4_INFERENCE_COMPLETED"; then
            inf_result="SUCCESS"
            min_mem_bytes=$(echo "$logs" | grep "M4_minimum_observed_availMem_during_inference" | grep -oE "[0-9]+" | head -1)
            if [ ! -z "$min_mem_bytes" ]; then
                min_mem=$(echo "scale=3; $min_mem_bytes / 1024 / 1024 / 1024" | bc)
            fi
            final_res="PASS"
            break
        fi
        
        if echo "$logs" | grep -q "WIN DEATH" | grep -q "com.edgemind.app"; then
            final_res="OOM/CRASH"
            break
        fi
        
        timeout=$((timeout - 2))
    done
    
    echo "$target,$actual_gb,$mg_result,$load_result,$inf_result,$min_mem,$final_res" >> $RESULTS_FILE
    echo "Result: $final_res"
done
