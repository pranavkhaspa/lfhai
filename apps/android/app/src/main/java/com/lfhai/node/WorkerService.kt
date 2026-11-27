package com.lfhai.node

import android.app.ActivityManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.net.NetworkInterface

class WorkerService : Service() {
    private val client = OkHttpClient()
    private val jsonType = "application/json; charset=utf-8".toMediaType()
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null
    private var running = true

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, buildNotification())
        val power = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "lfhai:worker")
        wakeLock?.acquire()
        val wifi = getSystemService(Context.WIFI_SERVICE) as WifiManager
        wifiLock = wifi.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "lfhai-worker")
        wifiLock?.acquire()
        Thread { runWorker() }.start()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        running = false
        wakeLock?.release()
        wifiLock?.release()
        super.onDestroy()
    }

    private fun runWorker() {
        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        var controller = prefs.getString(KEY_CONTROLLER, "") ?: ""
        var nodeId = prefs.getString(KEY_NODE_ID, "") ?: ""
        var nodeSecret = prefs.getString(KEY_NODE_SECRET, "") ?: ""

        if (nodeId.isEmpty() || nodeSecret.isEmpty()) {
            val token = prefs.getString(KEY_TOKEN, "") ?: ""
            val parsed = parseToken(token)
            if (parsed == null) {
                updateNotification("Invalid join token")
                return
            }
            controller = "http://${parsed.first}:${parsed.second}"
            val joined = join(controller, parsed.third)
            if (joined == null) {
                updateNotification("Join failed; retry by opening the app")
                return
            }
            nodeId = joined.first
            nodeSecret = joined.second
            prefs.edit()
                .putString(KEY_CONTROLLER, controller)
                .putString(KEY_NODE_ID, nodeId)
                .putString(KEY_NODE_SECRET, nodeSecret)
                .apply()
        }

        val endpoint = advertiseRpcEndpoint()
        updateNotification("Worker online${if (endpoint.isEmpty()) "" else " · $endpoint"}")
        while (running) {
            heartbeat(controller, nodeId, nodeSecret)
            Thread.sleep(5000)
        }
    }

    private fun join(controller: String, secret: String): Pair<String, String>? {
        val body = JSONObject()
            .put("token", secret)
            .put("node", nodeInfo())
            .toString()
            .toRequestBody(jsonType)
        val request = Request.Builder()
            .url("$controller/api/v1/nodes/join")
            .post(body)
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return null
                val data = JSONObject(response.body?.string().orEmpty())
                Pair(data.getString("node_id"), data.getString("node_secret"))
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun heartbeat(controller: String, nodeId: String, secret: String) {
        val metrics = JSONObject()
            .put("cpu_usage_pct", 0.0)
            .put("memory_available_bytes", availableMemory())
            .put("memory_total_bytes", totalMemory())
        val body = JSONObject()
            .put("node_id", nodeId)
            .put("metrics", metrics)
            .toString()
            .toRequestBody(jsonType)
        val request = Request.Builder()
            .url("$controller/api/v1/nodes/heartbeat")
            .header("Authorization", "Bearer $secret")
            .post(body)
            .build()
        try {
            client.newCall(request).execute().use { response -> response.close() }
        } catch (_: Exception) {
        }
    }

    private fun nodeInfo(): JSONObject {
        val endpoints = JSONArray()
        val endpoint = advertiseRpcEndpoint()
        if (endpoint.isNotEmpty()) {
            endpoints.put(
                JSONObject()
                    .put("endpoint", endpoint)
                    .put("backend", "cpu")
                    .put("memory_mb", RPC_MEMORY_MB)
            )
        }
        val capabilities = JSONObject()
            .put("models", JSONArray())
            .put("backends", JSONArray().put("llamacpp_rpc"))
            .put("rpc_endpoints", endpoints)
        return JSONObject()
            .put("hostname", Build.MODEL)
            .put(
                "resources",
                JSONObject()
                    .put("ip", localIp())
                    .put("cores", Runtime.getRuntime().availableProcessors())
                    .put("memory_total_bytes", totalMemory())
                    .put("memory_available_bytes", availableMemory())
            )
            .put("capabilities", capabilities)
    }

    private fun advertiseRpcEndpoint(): String {
        if (!RpcBridge.available()) return ""
        val started = RpcBridge.start("0.0.0.0", RPC_PORT, RPC_MEMORY_MB)
        return if (started) "${localIp()}:$RPC_PORT" else ""
    }

    private fun parseToken(token: String): Triple<String, Int, String>? {
        val raw = token.substringAfter("://", token)
        val parts = raw.split(":")
        if (parts.size != 3) return null
        val port = parts[1].toIntOrNull() ?: return null
        return Triple(parts[0], port, parts[2])
    }

    private fun totalMemory(): Long {
        val info = ActivityManager.MemoryInfo()
        (getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(info)
        return info.totalMem
    }

    private fun availableMemory(): Long {
        val info = ActivityManager.MemoryInfo()
        (getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(info)
        return info.availMem
    }

    private fun localIp(): String {
        var fallback = ""
        for (interfaces in NetworkInterface.getNetworkInterfaces()) {
            for (address in interfaces.inetAddresses) {
                val ip = address.hostAddress
                if (address.isLoopbackAddress || !ip.contains(".")) continue
                if (ip.startsWith("100.")) return ip
                if (fallback.isEmpty()) fallback = ip
            }
        }
        return fallback.ifEmpty { "127.0.0.1" }
    }

    private fun buildNotification(): Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "lfhai worker",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
        val intent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            Notification.Builder(this)
        }
        return builder
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle("lfhai node")
            .setContentText("Starting")
            .setContentIntent(intent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification().also { notification ->
            notification.extras.putCharSequence(Notification.EXTRA_TEXT, text)
        })
    }

    companion object {
        private const val PREFS = "lfhai"
        private const val KEY_TOKEN = "token"
        private const val KEY_CONTROLLER = "controller"
        private const val KEY_NODE_ID = "node_id"
        private const val KEY_NODE_SECRET = "node_secret"
        private const val CHANNEL_ID = "lfhai-worker"
        private const val NOTIFICATION_ID = 1
        private const val RPC_PORT = 50053
        private const val RPC_MEMORY_MB = 1536
    }
}
