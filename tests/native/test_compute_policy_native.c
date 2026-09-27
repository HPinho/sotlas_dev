#include "opencl_vector.h"

#include <stdint.h>

int main(void) {
    const float left[] = {1.5f, -2.0f, 7.0f};
    const float right[] = {2.5f, 3.0f, -4.0f};
    const float expected[] = {4.0f, 1.0f, 3.0f};
    float output[] = {-1.0f, -1.0f, -1.0f};
    const size_t count = sizeof(left) / sizeof(left[0]);
    sotlas_compute_backend_t backend = SOTLAS_COMPUTE_BACKEND_OPENCL_GPU;
    sotlas_opencl_status_t status;
    size_t index;

    status = sotlas_vector_add_f32_with_policy(
        left, right, output, count, SOTLAS_COMPUTE_CPU_ONLY, &backend
    );
    if (status != SOTLAS_OPENCL_OK || backend != SOTLAS_COMPUTE_BACKEND_CPU) return 1;
    for (index = 0; index < count; ++index) {
        if (output[index] != expected[index]) return 2;
    }

    backend = SOTLAS_COMPUTE_BACKEND_NONE;
    status = sotlas_vector_add_f32_with_policy(
        left, right, output, count,
        SOTLAS_COMPUTE_OPENCL_WITH_CPU_FALLBACK, &backend
    );
    if (status != SOTLAS_OPENCL_OK ||
        (backend != SOTLAS_COMPUTE_BACKEND_CPU &&
         backend != SOTLAS_COMPUTE_BACKEND_OPENCL_GPU)) return 3;
    for (index = 0; index < count; ++index) {
        if (output[index] != expected[index]) return 4;
    }

    backend = SOTLAS_COMPUTE_BACKEND_CPU;
    if (sotlas_vector_add_f32_with_policy(
            NULL, right, output, count, SOTLAS_COMPUTE_CPU_ONLY, &backend
        ) != SOTLAS_OPENCL_INVALID_ARGUMENT ||
        backend != SOTLAS_COMPUTE_BACKEND_NONE) return 5;
    if (sotlas_vector_add_f32_with_policy(
            (const float *)(uintptr_t)1u,
            (const float *)(uintptr_t)2u,
            (float *)(uintptr_t)3u,
            SIZE_MAX / sizeof(float) + 1u,
            SOTLAS_COMPUTE_CPU_ONLY,
            &backend
        ) != SOTLAS_OPENCL_SIZE_OVERFLOW ||
        backend != SOTLAS_COMPUTE_BACKEND_NONE) return 6;
    if (sotlas_vector_add_f32_with_policy(
            NULL, NULL, NULL, 0, SOTLAS_COMPUTE_CPU_ONLY, &backend
        ) != SOTLAS_OPENCL_OK ||
        backend != SOTLAS_COMPUTE_BACKEND_NONE) return 7;
    if (sotlas_vector_add_f32_with_policy(
            left, right, output, count, (sotlas_compute_policy_t)99, &backend
        ) != SOTLAS_OPENCL_INVALID_ARGUMENT ||
        backend != SOTLAS_COMPUTE_BACKEND_NONE) return 8;
    if (sotlas_vector_add_f32_with_policy(
            left, right, output, count, SOTLAS_COMPUTE_CPU_ONLY, NULL
        ) != SOTLAS_OPENCL_INVALID_ARGUMENT) return 9;
    return 0;
}
