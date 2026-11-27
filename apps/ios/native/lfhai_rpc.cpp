#include "lfhai_rpc.h"

#include <pthread.h>
#include <cstdio>
#include <cstdlib>
#include <string>

#include "ggml-backend.h"
#include "ggml-rpc.h"

namespace {

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

extern "C" int lfhai_rpc_start(const char * endpoint, int no_comm) {
    static pthread_t thread;
    static bool started = false;
    if (started) {
        return 1;
    }
    if (endpoint == nullptr) {
        return 0;
    }
    setenv("GGML_RPC_NO_COMM", no_comm ? "1" : "0", 1);
    auto * value = new std::string(endpoint);
    if (pthread_create(&thread, nullptr, run_rpc_server, value) != 0) {
        delete value;
        return 0;
    }
    pthread_detach(thread);
    started = true;
    return 1;
}
