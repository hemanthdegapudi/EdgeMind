import re
def extract_avg10(psi_str):
    if not psi_str: return 0.0
    m = re.search(r'some avg10=([0-9.]+)', psi_str)
    if m: return float(m.group(1))
    return 0.0
