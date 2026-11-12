plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// İmza bilgileri GitHub Actions gizli değişkenlerinden gelir; yoksa hata ayıklama anahtarıyla imzalanır.
val anahtarDosyasi: String? = System.getenv("LIMEOBS_KEYSTORE")

android {
    namespace = "com.kagan.limeobs"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.kagan.limeobs"
        minSdk = 26
        targetSdk = 35
        versionCode = (System.getenv("LIMEOBS_VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("LIMEOBS_VERSION_NAME") ?: "1.0.0"
    }

    signingConfigs {
        create("surum") {
            if (anahtarDosyasi != null) {
                storeFile = file(anahtarDosyasi)
                storePassword = System.getenv("LIMEOBS_KEYSTORE_PASS")
                keyAlias = System.getenv("LIMEOBS_KEY_ALIAS") ?: "limeobs"
                keyPassword = System.getenv("LIMEOBS_KEY_PASS") ?: System.getenv("LIMEOBS_KEYSTORE_PASS")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = if (anahtarDosyasi != null) signingConfigs.getByName("surum") else signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jsoup:jsoup:1.18.3")
}
