cmake_minimum_required(VERSION 3.16)
project(mwg_ephemeral_core_apply CXX)
set(CMAKE_CXX_STANDARD 17)

find_package(Python3 COMPONENTS Development REQUIRED)
# Paths are hardcoded to this host's python install: importing torch from
# inside the CANN setenv environment can fail (LD_LIBRARY_PATH conflicts),
# which silently empties the probe variables.
set(TORCH_CMAKE_PATH
    "/usr/local/python3.11.14/lib/python3.11/site-packages/torch/share/cmake")
set(TORCH_NPU_PATH
    "/usr/local/python3.11.14/lib/python3.11/site-packages/torch_npu")
list(APPEND CMAKE_PREFIX_PATH ${TORCH_CMAKE_PATH})
find_package(Torch REQUIRED)
# AscendC kernel language (.asc): the CANN toolkit ships the ASC language
# modules under compiler/tikcpp/ascendc_kernel_cmake.
find_package(ASC REQUIRED
    PATHS /usr/local/Ascend/ascend-toolkit/latest/compiler/tikcpp/ascendc_kernel_cmake
    NO_DEFAULT_PATH)
# Pin the real ccec bisheng (the cann-8.5.0/bin shim lacks the AscendC
# plugin) and give it the 910B aicore architecture BEFORE enable_language
# snapshots the compiler invocation.
set(CMAKE_ASC_COMPILER
    /usr/local/Ascend/cann-8.5.0/aarch64-linux/ccec_compiler/bin/bisheng
    CACHE FILEPATH "" FORCE)
set(CMAKE_ASC_FLAGS "--cce-aicore-arch=dav-c220")
enable_language(ASC)
set(TORCH_NPU_INCLUDE_DIRS ${TORCH_NPU_PATH}/include)
set(TORCH_NPU_LIBRARIES ${TORCH_NPU_PATH}/lib)
add_library(custom_ops SHARED
    ephemeral_core_apply.asc
)
target_include_directories(custom_ops PRIVATE
    ${Python3_INCLUDE_DIRS}
    ${TORCH_INCLUDE_DIRS}
    ${TORCH_NPU_INCLUDE_DIRS}
)
target_link_libraries(custom_ops PRIVATE
    torch_npu
    tiling_api
    register
    platform
    m
    dl
)
target_link_directories(custom_ops PRIVATE
    ${TORCH_NPU_LIBRARIES}
)
target_compile_definitions(custom_ops PRIVATE
    __GLIBCXX_USE_CXX11_ABI=0
)
