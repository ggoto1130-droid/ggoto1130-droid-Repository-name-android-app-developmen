package org.syun.pokemonw2

import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.Gravity
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.lifecycleScope
import androidx.preference.PreferenceManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import me.magnum.melonds.ui.emulator.EmulatorActivity
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.security.MessageDigest

class StandaloneLauncherActivity : AppCompatActivity() {
    private lateinit var status: TextView
    private lateinit var progress: ProgressBar
    private var gameActivityStarted = false

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        val recoveredFromInterruptedLaunch = applyLaunchDefaultsAndRecovery()
        showPreparingScreen()
        if (recoveredFromInterruptedLaunch) {
            status.text = "前回の起動が停止したため、互換性を優先して再起動しています…"
        }

        lifecycleScope.launch {
            try {
                withContext(Dispatchers.IO) { ensureGameImage() }
                status.text = "ゲームを起動しています…"
                val uri = android.net.Uri.Builder()
                    .scheme("content")
                    .authority("$packageName.game")
                    .appendPath(GameProvider.FILE_NAME)
                    .build()
                val intent = Intent(this@StandaloneLauncherActivity, EmulatorActivity::class.java)
                    .setDataAndType(uri, GameProvider.MIME_TYPE)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                PreferenceManager.getDefaultSharedPreferences(this@StandaloneLauncherActivity)
                    .edit()
                    .putBoolean(KEY_GAME_LAUNCH_IN_PROGRESS, true)
                    .commit()
                startActivity(intent)
                gameActivityStarted = true
            } catch (error: Exception) {
                PreferenceManager.getDefaultSharedPreferences(this@StandaloneLauncherActivity)
                    .edit()
                    .putBoolean(KEY_GAME_LAUNCH_IN_PROGRESS, false)
                    .apply()
                Log.e(TAG, "Unable to prepare or launch Pokémon White 2", error)
                progress.visibility = ProgressBar.GONE
                status.text = "ゲームを起動できませんでした。空き容量とゲームデータを確認して、もう一度開いてください。\n\n${error.message ?: error.javaClass.simpleName}"
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (gameActivityStarted) {
            PreferenceManager.getDefaultSharedPreferences(this)
                .edit()
                .putBoolean(KEY_GAME_LAUNCH_IN_PROGRESS, false)
                .apply()
            finish()
        }
    }

    private fun showPreparingScreen() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(28), dp(28), dp(28), dp(28))
            setBackgroundColor(0xFF17151F.toInt())
        }
        status = TextView(this).apply {
            text = "ポケモン ホワイト2を準備しています…"
            textSize = 20f
            gravity = Gravity.CENTER
            setTextColor(0xFFFFFFFF.toInt())
        }
        progress = ProgressBar(this)
        root.addView(status, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(progress, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(24)
        })
        setContentView(root)
    }

    private fun applyLaunchDefaultsAndRecovery(): Boolean {
        val preferences = PreferenceManager.getDefaultSharedPreferences(this)
        if (preferences.getBoolean(KEY_DEFAULTS_APPLIED, false)) {
            val interrupted = preferences.getBoolean(KEY_GAME_LAUNCH_IN_PROGRESS, false)
            if (interrupted) {
                preferences.edit()
                    .putBoolean("enable_jit", false)
                    .putString("video_renderer", "software")
                    .putBoolean(KEY_GAME_LAUNCH_IN_PROGRESS, false)
                    .commit()
            }
            return interrupted
        }

        val supportsJit = Build.SUPPORTED_64_BIT_ABIS.any { it == "arm64-v8a" || it == "x86_64" }
        preferences.edit()
            .putBoolean("github_check_for_updates", false)
            .putBoolean("use_custom_bios", false)
            .putBoolean("show_bios", false)
            .putBoolean("enable_jit", supportsJit)
            .putString("video_renderer", "opengl")
            .putBoolean(KEY_DEFAULTS_APPLIED, true)
            .putBoolean(KEY_GAME_LAUNCH_IN_PROGRESS, false)
            .commit()
        return false
    }

    private fun ensureGameImage(): File {
        val preferences = PreferenceManager.getDefaultSharedPreferences(this)
        val image = File(filesDir, GameProvider.FILE_NAME)
        if (image.length() == EXPECTED_SIZE && hasValidHeader(image) && preferences.getBoolean(KEY_IMAGE_VERIFIED, false)) {
            return image
        }

        val temporary = File(filesDir, "${GameProvider.FILE_NAME}.partial")
        temporary.delete()
        try {
            assets.open(ASSET_PATH).use { input ->
                FileOutputStream(temporary).use { output ->
                    val buffer = ByteArray(COPY_BUFFER_SIZE)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        output.write(buffer, 0, count)
                    }
                    output.fd.sync()
                }
            }

            if (temporary.length() != EXPECTED_SIZE || sha256(temporary) != EXPECTED_SHA256) {
                throw IOException("ゲームデータの検証に失敗しました")
            }
            if (image.exists() && !image.delete()) throw IOException("古いゲームデータを置き換えられません")
            if (!temporary.renameTo(image)) throw IOException("ゲームデータを保存できません")

            preferences.edit().putBoolean(KEY_IMAGE_VERIFIED, true).apply()
            return image
        } catch (error: Exception) {
            temporary.delete()
            throw error
        }
    }

    private fun hasValidHeader(file: File): Boolean = try {
        file.inputStream().use { input ->
            val header = ByteArray(16)
            if (input.read(header) != header.size) return false
            String(header, 0, 10, Charsets.US_ASCII) == "POKEMON W2" &&
                String(header, 12, 4, Charsets.US_ASCII) == "IRDO"
        }
    } catch (_: IOException) {
        false
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(COPY_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()

    companion object {
        private const val TAG = "PokemonW2Launcher"
        private const val ASSET_PATH = "bundled/pokemon_white2.nds"
        private const val EXPECTED_SIZE = 536_870_912L
        private const val EXPECTED_SHA256 = "3b3f91fe0e4cc323ea73a1d6242fa04b255d98c4e44971594624bad919713a7b"
        private const val COPY_BUFFER_SIZE = 64 * 1024
        private const val KEY_DEFAULTS_APPLIED = "pokemon_standalone_defaults_v1"
        private const val KEY_GAME_LAUNCH_IN_PROGRESS = "pokemon_game_launch_in_progress_v1"
        private const val KEY_IMAGE_VERIFIED = "pokemon_w2_image_verified_v1"
    }
}
