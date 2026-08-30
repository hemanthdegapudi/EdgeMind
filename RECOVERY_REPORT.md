# Recovery Status
Successfully recovered to the single-app architecture. The repository is now clean and ready for single-APK validation.

# Root Cause of Two-App Architecture
The two-app architecture was an uncommitted deviation left in the working directory by a previous test or agent. The changes included modifying `edgemind-app/app/build.gradle.kts` to add `productFlavors` (qwen and deepseek) and adding flavor-specific source directories (`edgemind-app/app/src/qwen` and `edgemind-app/app/src/deepseek`). Furthermore, these uncommitted changes destructively deleted historical Gate 0.5 and Gate 0.6 validation evidence from the `validation/` and `evidence/` directories. Since these changes were never committed, they appeared as unstaged/untracked modifications on top of the clean `main` branch.

# Recovery Commit / Strategy
Recovery Base Commit: `e229519` (chore: update .gitignore to include vscode AI rules and add local toolchain directory).
Strategy:
1. Created a backup branch and commit (`69444d4`) named `backup/pre-single-app-recovery` containing the exact dirty two-app state and tracking all deleted files.
2. Created a clean recovery branch `recovery/single-app` from `e229519` which perfectly restores the clean, single-app state and recovers all validation evidence.
3. Added `Theme.AppCompat` to `AndroidManifest.xml` to prevent a crash on app launch.

# T01–T06 Preservation Evidence
All historical validation files from Gate 0, Gate 0.5, and Gate 0.6 (e.g., `validation_readiness_report.md`, `gate0_5_validation_report.md`, and raw trace files in `evidence/` and `phase10_evidence/`) were restored automatically because their deletions were part of the uncommitted dirty state. They are fully intact and preserved on the `recovery/single-app` branch.

# Files Changed
To recover the state, the uncommitted dirty changes were committed to the backup branch and then cleared by checking out `recovery/single-app` from the base commit `e229519`.
Files restored to original single-app architecture:
- `edgemind-app/app/build.gradle.kts` (Product flavors removed)
- `edgemind-app/app/src/qwen/` and `edgemind-app/app/src/deepseek/` (Removed flavor source sets)
- `edgemind-app/app/src/main/java/com/edgemind/app/model/ModelDefinition.kt` (Restored unified registry)
- `edgemind-app/app/src/main/AndroidManifest.xml` (Fixed missing theme causing launch crash)
Files recovered from deletion:
- `validation/validation_readiness_report.md`
- `validation/gate0_5_validation_report.md`
- `validation/gate0_6_certification_report.md`
- Raw memory baselines in `evidence/` and `phase10_evidence/`

# Build / APK Verification
`./gradlew assembleDebug` successfully executes and produces exactly one unified application: `edgemind-app/app/build/outputs/apk/debug/app-debug.apk`. The build completes without generating flavor-specific APKs (e.g., no `app-qwen.apk` or `app-deepseek.apk`), satisfying the single-app requirement.

# Device / Package Verification
Installation was successfully completed after a manual bypass of the MIUI "Install via USB" block. 
`adb shell pm list packages | grep -i edgemind` correctly verified that exactly 1 EdgeMind package (`com.edgemind.app`) exists on the device, confirming the absence of a split dual-app deployment. 

# Model Switching Verification
Model switching and inference have been strictly verified dynamically on the physical device via `verify_recovery.sh`.
- **Test B**: App launched successfully.
- **Test C**: `Qwen3-1.7B` generated output correctly (decode TPS: ~9.5 tokens/s).
- **Test D**: Switch to `DeepSeek-1.5B` succeeded.
- **Test E**: `DeepSeek-1.5B` generated output correctly.
- **Test F**: Switch back to `Qwen3-1.7B` succeeded.
All tests PASSED flawlessly inside the single application context.

# Remaining Risks
- Model memory release and cache contamination claims during the Qwen ↔ DeepSeek switch are still unverified on the hardware and must be formally proven in Gate 3+.

# Gate Status
T01 — Completed
T02 — Completed
T03 — Partial / measurement issue discovered
T04 — Completed
T05 — Partial; historical memory evidence invalid
T06 — Completed
T07 — Completed (Recovery & Sanity Verification passed on-device)
T08 — Pending
T09 — Pending
T10 — Pending
T11 — Pending
T12 — Pending
T13 — Pending
T14 — Pending
T15 — Pending
T16–T19 — Reconcile individually

# Recommended Next Step
With the single-app architecture validated and fully functional on the target Redmi K20 Pro, you can proceed to Gate 3+ to measure the true memory footprint delta between `Qwen` and `DeepSeek` across continuous runtime switching.
