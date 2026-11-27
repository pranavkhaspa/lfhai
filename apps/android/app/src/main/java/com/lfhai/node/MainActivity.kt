package com.lfhai.node

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = getSharedPreferences("lfhai", Context.MODE_PRIVATE)
        val label = TextView(this).apply { text = "Controller join token" }
        val tokenInput = EditText(this).apply {
            setText(prefs.getString("token", "") ?: "")
            hint = "192.168.1.10:8001:SECRET"
        }
        val startButton = Button(this).apply {
            text = "Join and start worker"
            setOnClickListener {
                prefs.edit().putString("token", tokenInput.text.toString()).apply()
                if (
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                    checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                    PackageManager.PERMISSION_GRANTED
                ) {
                    requestPermissions(
                        arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                        1
                    )
                }
                startForegroundService(Intent(this@MainActivity, WorkerService::class.java))
            }
        }
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
            addView(label)
            addView(tokenInput)
            addView(startButton)
        }
        setContentView(layout)
    }
}
