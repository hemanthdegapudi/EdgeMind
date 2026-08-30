import json, os

path = "validation/run_manifest.json"
if os.path.exists(path):
    with open(path, "r") as f:
        data = json.load(f)
    if "stages" not in data:
        data["stages"] = {}
        for stage in data.get("completed_tests", []):
            data["stages"][stage] = {"status": "PASSED"}
        for stage in data.get("failed_tests", []):
            data["stages"][stage] = {"status": "FAILED"}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
