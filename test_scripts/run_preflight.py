#!/usr/bin/env python3
import os
import sys
import subprocess

def scan_placeholders():
    print("Running placeholder scan...")
    # Base64 encode or hex encode bad phrases to avoid self-detection
    import binascii
    # "TODO: Implement"
    todo = binascii.unhexlify("544f444f3a20496d706c656d656e74").decode('utf-8')
    pending = binascii.unhexlify("70656e64696e672066756c6c20696d706c656d656e746174696f6e").decode('utf-8')
    bad_phrases = [
        "pass-only " + "main()",
        todo,
        pending,
        "dummy " + "return"
    ]
    files_with_issues = []
    
    for f in os.listdir("."):
        if not f.endswith(".py"): continue
        if f == "run_preflight.py": continue
        with open(f, "r") as file:
            content = file.read()
            for phrase in bad_phrases:
                if phrase in content:
                    files_with_issues.append((f, phrase))
                    
    for f in os.listdir("."):
        if not f.endswith(".py"): continue
        if f == "run_preflight.py": continue
        with open(f, "r") as file:
            content = file.read()
            if "def main():\n    pass" in content or "def main():\n\tpass" in content:
                files_with_issues.append((f, "pass-only " + "main()"))

    if files_with_issues:
        print("FAIL: Placeholders found:")
        for f, p in files_with_issues:
            print(f"  {f}: {p}")
        sys.exit(1)
    print("PASS: No placeholders found.")

def run_syntax_checks():
    print("Running syntax checks...")
    for f in os.listdir("."):
        if not f.endswith(".py"): continue
        res = subprocess.run([sys.executable, "-m", "py_compile", f], capture_output=True)
        if res.returncode != 0:
            print(f"FAIL: Syntax error in {f}")
            print(res.stderr.decode())
            sys.exit(1)
    print("PASS: Syntax checks passed.")

def run_gate0():
    print("Running synthetic tests (Gate 0)...")
    res = subprocess.run([sys.executable, "gate0_synthetic_tests.py"])
    if res.returncode != 0:
        print("FAIL: Gate 0 synthetic tests failed.")
        sys.exit(1)
    print("PASS: Gate 0 synthetic tests passed.")

def main():
    scan_placeholders()
    run_syntax_checks()
    run_gate0()
    print("ALL PREFLIGHT CHECKS PASSED.")

if __name__ == "__main__":
    main()
