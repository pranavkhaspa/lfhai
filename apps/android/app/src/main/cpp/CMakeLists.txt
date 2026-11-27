cmake_minimum_required(VERSION 3.22)
project(lfhai_rpc LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD 11)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(GGML_RPC ON CACHE BOOL "" FORCE)
set(GGML_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GGML_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)

include(FetchContent)
FetchContent_Declare(
    llama_cpp
    GIT_REPOSITORY https://github.com/ggml-org/llama.cpp.git
    GIT_TAG ca123ba76311290ec6ab041dd2058fed8d9f03d2
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(llama_cpp)

add_library(lfhai_rpc SHARED rpc_bridge.cpp)
target_include_directories(lfhai_rpc PRIVATE "${llama_cpp_SOURCE_DIR}/ggml/include")
target_link_libraries(
    lfhai_rpc
    PRIVATE
    ggml
    ggml-base
    ggml-cpu
    ggml-rpc
)
