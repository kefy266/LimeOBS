package com.kagan.limeobs

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Giriş bilgilerini Android Keystore'daki donanım destekli AES anahtarıyla şifreleyip saklar.
 * Şifre hiçbir zaman açık metin olarak diske yazılmaz.
 */
class Kasa(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("limeobs_kasa", Context.MODE_PRIVATE)

    private fun anahtar(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(TAKMA_AD, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val uretici = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        uretici.init(
            KeyGenParameterSpec.Builder(TAKMA_AD, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return uretici.generateKey()
    }

    fun yaz(tc: String, sifre: String) {
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, anahtar())
        val sifreli = c.doFinal("$tc\u0000$sifre".toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString("iv", Base64.encodeToString(c.iv, Base64.NO_WRAP))
            .putString("veri", Base64.encodeToString(sifreli, Base64.NO_WRAP))
            .apply()
    }

    fun oku(): Pair<String, String>? = runCatching {
        val iv = Base64.decode(prefs.getString("iv", null) ?: return null, Base64.NO_WRAP)
        val veri = Base64.decode(prefs.getString("veri", null) ?: return null, Base64.NO_WRAP)
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, anahtar(), GCMParameterSpec(128, iv))
        val metin = String(c.doFinal(veri), Charsets.UTF_8)
        metin.substringBefore('\u0000') to metin.substringAfter('\u0000')
    }.getOrNull()

    fun sil() {
        prefs.edit().clear().apply()
    }

    private companion object {
        const val TAKMA_AD = "limeobs_kasa"
    }
}
