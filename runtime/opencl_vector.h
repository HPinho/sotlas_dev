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

#ifdef __cplusplus
}
#endif

#endif /* SOTLAS_OPENCL_VECTOR_H */
