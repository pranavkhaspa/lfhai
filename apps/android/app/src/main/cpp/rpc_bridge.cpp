#include <jni.h>

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <pthread.h>
#include <string>

#include "ggml-backend.h"
#include "ggml-rpc.h"

namespace {

std::atomic<bool> g_started{false};

void * run_rpc_server(void * data) {
    auto * endpoint = static_cast<std::string *>(data);
    ggml_backend_dev_t cpu = ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
    if (cpu != nullptr) {
        ggml_backend_rpc_start_server(endpoint->c_str(), nullptr, 1, 1, &cpu);
    }
    delete endpoint;
    return nullptr;
}

}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_lfhai_node_RpcBridge_nativeStart(
    JNIEnv * env,
    jclass,
    jstring host,
    jint port,
    jint memory_mb
) {
    (void) memory_mb;
    if (g_started.exchange(true)) {
        return JNI_TRUE;
    }

    const char * raw_host = env->GetStringUTFChars(host, nullptr);
    if (raw_host == nullptr) {
        g_started.store(false);
        return JNI_FALSE;
    }
    char buffer[256];
    std::snprintf(buffer, sizeof(buffer), "%s:%d", raw_host, static_cast<int>(port));
    env->ReleaseStringUTFChars(host, raw_host);

    setenv("GGML_RPC_NO_COMM", "1", 1);
    auto * endpoint = new std::string(buffer);
    pthread_t thread;
    if (pthread_create(&thread, nullptr, run_rpc_server, endpoint) != 0) {
        delete endpoint;
        g_started.store(false);
        return JNI_FALSE;
    }
    pthread_detach(thread);
    return JNI_TRUE;
}
