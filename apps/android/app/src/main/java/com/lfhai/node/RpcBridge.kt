package com.lfhai.node

object RpcBridge {
    private var loaded = false

    fun available(): Boolean {
        if (!loaded) {
            try {
                System.loadLibrary("lfhai_rpc")
                loaded = true
            } catch (_: UnsatisfiedLinkError) {
                loaded = false
            }
        }
        return loaded
    }

    fun start(host: String, port: Int, memoryMb: Int): Boolean {
        if (!available()) return false
        return nativeStart(host, port, memoryMb)
    }

    private external fun nativeStart(host: String, port: Int, memoryMb: Int): Boolean
}
