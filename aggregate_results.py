import json, glob, sys, os
from statistics import mean, median, stdev

files = glob.glob('phase9_results/run_*/metrics/*.json')
data = {}

for f in files:
    with open(f) as fh:
        d = json.load(fh)
        exp = d['experiment']
        if exp not in data: data[exp] = []
        data[exp].append(d)

print(f"{'EXP':<6} | {'Mask':<4} | {'Valid':<5} | {'Gen(t/s)':<8} | {'Prmpt(t/s)':<10} | {'Peak(C)':<7}")
print("-" * 55)

for exp in sorted(data.keys()):
    runs = data[exp]
    valid = [r for r in runs if r.get('valid') and r.get('eval_tps') is not None]
    
    mask = runs[0].get('requested_mask', 'none')
    
    if not valid:
        print(f"{exp:<6} | {mask:<4} | {0}/{len(runs):<3} | {'N/A':<8} | {'N/A':<10} | {'N/A':<7}")
        continue
        
    gen = [float(r['eval_tps']) for r in valid]
    prmpt = [float(r['prompt_eval_tps']) for r in valid]
    
    peaks = []
    for r in valid:
        pt = r.get('peak_cpu_temp_mc')
        if pt is not None and str(pt).replace('.','').isdigit():
            peaks.append(float(pt)/1000.0)
            
    avg_gen = mean(gen)
    avg_prmpt = mean(prmpt)
    max_peak = max(peaks) if peaks else 0.0
    
    print(f"{exp:<6} | {mask:<4} | {len(valid)}/{len(runs):<3} | {avg_gen:<8.2f} | {avg_prmpt:<10.2f} | {max_peak:<7.1f}")

    invalid = [r for r in runs if not r.get('valid')]
    for i in invalid:
        print(f"       -> Invalid reason: {i.get('invalid_reason')}")
