/* Experimental OpenCL C ABI for a checked f32 vector-add workload. */
#ifndef SOTLAS_OPENCL_VECTOR_H
#define SOTLAS_OPENCL_VECTOR_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum sotlas_opencl_status {
    SOTLAS_OPENCL_OK = 0,
    SOTLAS_OPENCL_INVALID_ARGUMENT = 1,
    SOTLAS_OPENCL_SIZE_OVERFLOW = 2,
    SOTLAS_OPENCL_RUNTIME_UNAVAILABLE = 3,
    SOTLAS_OPENCL_NO_GPU = 4,
    SOTLAS_OPENCL_BACKEND_ERROR = 5
} sotlas_opencl_status_t;

typedef enum sotlas_compute_policy {
    SOTLAS_COMPUTE_CPU_ONLY = 0,
    SOTLAS_COMPUTE_OPENCL_REQUIRED = 1,
    SOTLAS_COMPUTE_OPENCL_WITH_CPU_FALLBACK = 2
} sotlas_compute_policy_t;

typedef enum sotlas_compute_backend {
    SOTLAS_COMPUTE_BACKEND_NONE = 0,
    SOTLAS_COMPUTE_BACKEND_CPU = 1,
    SOTLAS_COMPUTE_BACKEND_OPENCL_GPU = 2
} sotlas_compute_backend_t;

/* Adds count f32 values on the first available OpenCL GPU.
 * Input buffers are copied to device memory; output is copied back after the
 * queue completes. The output array is written only after a successful read.
 */
sotlas_opencl_status_t sotlas_opencl_vector_add_f32(
    const float *left,
    const float *right,
    float *output,
    size_t count
);

/* Runs the same vector operation with an explicit backend policy. The selected
 * backend is set to NONE on failure and for empty input. Fallback is used only
 * when the OpenCL runtime/GPU is unavailable; execution errors are returned.
 * CPU and OpenCL implementations use the same contiguous f32 input contract.
 */
sotlas_opencl_status_t sotlas_vector_add_f32_with_policy(
    const float *left,
    const float *right,
    float *output,
    size_t count,
    sotlas_compute_policy_t policy,
    sotlas_compute_backend_t *selected_backend
);

#ifdef __cplusplus
}
#endif

#endif /* SOTLAS_OPENCL_VECTOR_H */
