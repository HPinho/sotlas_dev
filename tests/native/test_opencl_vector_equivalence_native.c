#include "opencl_vector.h"

#include <stddef.h>
#include <stdio.h>

#define VECTOR_COUNT 259u

#if defined(_WIN32)
#include <windows.h>
typedef HMODULE sotlas_test_library_t;
static void *test_symbol(sotlas_test_library_t library, const char *name) {
    return (void *)GetProcAddress(library, name);
}
#else
#include <dlfcn.h>
typedef void *sotlas_test_library_t;
static void *test_symbol(sotlas_test_library_t library, const char *name) {
    return dlsym(library, name);
}
#endif

typedef int (*cleanup_check_fn)(void);

static void close_test_library(sotlas_test_library_t library) {
#if defined(_WIN32)
    FreeLibrary(library);
#else
    dlclose(library);
#endif
}

int main(void) {
    float left[VECTOR_COUNT];
    float right[VECTOR_COUNT];
    float cpu_output[VECTOR_COUNT] = {0};
    float opencl_output[VECTOR_COUNT] = {0};
    const size_t count = VECTOR_COUNT;
    sotlas_compute_backend_t cpu_backend = SOTLAS_COMPUTE_BACKEND_NONE;
    sotlas_compute_backend_t opencl_backend = SOTLAS_COMPUTE_BACKEND_NONE;
    size_t index;

    /* Binary fractions make exact CPU/GPU comparison meaningful while these
     * values exercise a non-workgroup-multiple vector length. */
    for (index = 0; index < count; ++index) {
        left[index] = (float)((int)(index % 101u) - 50) * 0.25f;
        right[index] = (float)((int)(index % 37u) - 18) * 0.5f;
    }
#if defined(_WIN32)
    sotlas_test_library_t provider = LoadLibraryA("OpenCL.dll");
#else
    sotlas_test_library_t provider = dlopen("libOpenCL.so.1", RTLD_NOW | RTLD_LOCAL);
#endif
    cleanup_check_fn cleanup_ok;

    if (!provider) return 4;
    cleanup_ok = (cleanup_check_fn)test_symbol(provider, "sotlas_fake_opencl_cleanup_ok");
    if (!cleanup_ok) {
        close_test_library(provider);
        return 5;
    }

    if (sotlas_vector_add_f32_with_policy(
            left, right, cpu_output, count, SOTLAS_COMPUTE_CPU_ONLY,
            &cpu_backend) != SOTLAS_OPENCL_OK ||
        cpu_backend != SOTLAS_COMPUTE_BACKEND_CPU) {
        close_test_library(provider);
        return 1;
    }
    if (sotlas_vector_add_f32_with_policy(
            left, right, opencl_output, count, SOTLAS_COMPUTE_OPENCL_REQUIRED,
            &opencl_backend) != SOTLAS_OPENCL_OK ||
        opencl_backend != SOTLAS_COMPUTE_BACKEND_OPENCL_GPU) {
        close_test_library(provider);
        return 2;
    }

    for (index = 0; index < count; ++index) {
        if (cpu_output[index] != opencl_output[index]) {
            close_test_library(provider);
            return 3;
        }
    }
    if (!cleanup_ok()) {
        close_test_library(provider);
        return 6;
    }
    close_test_library(provider);
    return 0;
}
