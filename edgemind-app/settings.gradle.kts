pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        mavenCentral()
        google()
    }
}

rootProject.name = "EdgeMind"
include(":app")

// Composite build: consume llama.android/lib as a local project dependency.
// This avoids publishing the AAR and leaves llama.android/ completely untouched.
includeBuild("../llama.cpp/examples/llama.android") {
    dependencySubstitution {
        substitute(module("com.arm.aichat:lib")).using(project(":lib"))
    }
}
