# EdgeMind ProGuard rules

# Preserve JNI-bound classes from llama.android lib
-keep class com.arm.aichat.internal.InferenceEngineImpl { *; }

# Preserve EdgeMind application and service classes
-keep class com.edgemind.app.** { *; }
