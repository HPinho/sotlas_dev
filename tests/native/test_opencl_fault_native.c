#include "opencl_vector.h"

#include <stddef.h>

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
    const float left[] = {1.0f, 2.0f};
    const float right[] = {3.0f, 4.0f};
    float output[] = {-91.0f, -92.0f};
#if defined(_WIN32)
    sotlas_test_library_t provider = LoadLibraryA("OpenCL.dll");
#else
    sotlas_test_library_t provider = dlopen("libOpenCL.so.1", RTLD_NOW | RTLD_LOCAL);
#endif
    cleanup_check_fn cleanup_ok;

    if (!provider) return 3;
    cleanup_ok = (cleanup_check_fn)test_symbol(provider, "sotlas_fake_opencl_cleanup_ok");
    if (!cleanup_ok) {
        close_test_library(provider);
        return 4;
    }
    if (sotlas_opencl_vector_add_f32(left, right, output, 2) !=
        SOTLAS_OPENCL_BACKEND_ERROR) {
        close_test_library(provider);
        return 1;
    }
    if (output[0] != -91.0f || output[1] != -92.0f) {
        close_test_library(provider);
        return 2;
    }
    if (!cleanup_ok()) {
        close_test_library(provider);
        return 5;
    }
    close_test_library(provider);
    return 0;
}
