#include "opencl_vector.h"

#include <stdint.h>
#include <stddef.h>

int main(void) {
    enum { VECTOR_COUNT = 259 };
    float left[VECTOR_COUNT];
    float right[VECTOR_COUNT];
    float output[VECTOR_COUNT];
    const size_t count = VECTOR_COUNT;
    size_t gpu_index;
    size_t index;
    size_t gpu_count = 0;
    sotlas_opencl_status_t status;
    sotlas_opencl_profile_t profile;

    /* Binary fractions make exact CPU/GPU comparison meaningful while this
     * length exercises tail handling beyond common workgroup multiples. */
    for (index = 0; index < count; ++index) {
        left[index] = (float)((int)(index % 101u) - 50) * 0.25f;
        right[index] = (float)((int)(index % 37u) - 18) * 0.5f;
        output[index] = -99.0f;
    }

    status = sotlas_opencl_get_gpu_count(&gpu_count);
    if (status == SOTLAS_OPENCL_NO_GPU ||
        status == SOTLAS_OPENCL_RUNTIME_UNAVAILABLE) return 77;
    if (status != SOTLAS_OPENCL_OK || gpu_count == 0) return 10;
    for (gpu_index = 0; gpu_index < gpu_count; ++gpu_index) {
        status = sotlas_opencl_vector_add_f32_profiled_on_gpu(
            left, right, output, count, gpu_index, &profile
        );
        if (status != SOTLAS_OPENCL_OK) return 1;
        for (index = 0; index < count; ++index) {
            const float cpu_reference = left[index] + right[index];
            if (output[index] != cpu_reference) return 2;
        }
        if (gpu_index == 0 &&
            (profile.upload_nanoseconds == 0 ||
             profile.kernel_nanoseconds == 0 ||
             profile.download_nanoseconds == 0)) return 7;
    }
    if (sotlas_opencl_vector_add_f32_profiled(
            left, right, output, count, NULL
        ) != SOTLAS_OPENCL_INVALID_ARGUMENT) return 8;
    output[0] = -99.0f;
    if (sotlas_opencl_vector_add_f32_on_gpu(
            left, right, output, count, gpu_count
        ) != SOTLAS_OPENCL_DEVICE_NOT_FOUND || output[0] != -99.0f) return 11;

    if (sotlas_opencl_vector_add_f32(NULL, right, output, count) !=
            SOTLAS_OPENCL_INVALID_ARGUMENT) return 3;
    if (sotlas_opencl_vector_add_f32(left, right, NULL, count) !=
            SOTLAS_OPENCL_INVALID_ARGUMENT) return 4;
    if (sotlas_opencl_vector_add_f32(NULL, NULL, NULL, 0) !=
            SOTLAS_OPENCL_OK) return 5;
    if (sotlas_opencl_vector_add_f32(
            (const float *)(uintptr_t)1u,
            (const float *)(uintptr_t)2u,
            (float *)(uintptr_t)3u,
            SIZE_MAX / sizeof(float) + 1u
        ) != SOTLAS_OPENCL_SIZE_OVERFLOW) return 9;
    return 0;
}
