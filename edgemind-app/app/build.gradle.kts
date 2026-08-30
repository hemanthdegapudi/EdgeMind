plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.jetbrains.kotlin.android)
}

android {
    namespace = "com.edgemind.app"
    compileSdk = 36

    // NDK version matches what is installed in .toolchain/android-sdk/ndk/
    // The llama.android/lib declares ndkVersion = 29.0.13113456 but that version
    // is not present in this environment. Since edgemind-app does NOT compile any
    // native code itself (it consumes the pre-built lib), the NDK version here
    // only affects lint/metadata, not the actual native build.
    // The native code is built by the composite build in llama.android/lib.
    // Using the installed NDK version to avoid configuration errors.
    ndkVersion = "27.2.12479018"

    defaultConfig {
        applicationId = "com.edgemind.app"

        // minSdk = 33: matches llama.android/lib minSdk to avoid compatibility warnings.
        // The Redmi K20 Pro target device runs a custom ROM (Android 13+, API 33+).
        // ThermalGuard uses PowerManager.addThermalStatusListener (API 29) — satisfied.
        // MemoryGuard uses ActivityManager.getMemoryInfo() — available from API 1.
        minSdk = 30
        targetSdk = 36

        versionCode = 1
        versionName = "10.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        jvmToolchain(17)
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    // llama.android native inference library (consumed via composite build)
    implementation("com.arm.aichat:lib")

    // AndroidX core
    implementation(libs.androidx.core.ktx)

    // Kotlin coroutines (for StateFlow, coroutine scope in guards)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
}
dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
}
