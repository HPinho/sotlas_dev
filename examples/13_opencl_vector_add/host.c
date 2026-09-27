#include "opencl_vector.h"

#include <stddef.h>
#include <stdio.h>

extern int run_vector_add(
    const float *left,
    const float *right,
    float *output,
    size_t count,
    int policy,
    int *selected_backend
);

int main(void) {
    const float left[] = {1.0f, 2.0f, -3.0f, 8.0f};
    const float right[] = {4.0f, -2.0f, 3.0f, 0.5f};
    const float expected[] = {5.0f, 0.0f, 0.0f, 8.5f};
    float output[] = {-1.0f, -1.0f, -1.0f, -1.0f};
    const size_t count = sizeof(left) / sizeof(left[0]);
    int selected_backend = SOTLAS_COMPUTE_BACKEND_NONE;
    size_t index;
    int status = run_vector_add(
        left, right, output, count,
        SOTLAS_COMPUTE_OPENCL_WITH_CPU_FALLBACK,
        &selected_backend
    );

    if (status != SOTLAS_OPENCL_OK) {
        fprintf(stderr, "Vector add failed with status %d.\n", status);
        return 1;
    }
    if (selected_backend != SOTLAS_COMPUTE_BACKEND_CPU &&
        selected_backend != SOTLAS_COMPUTE_BACKEND_OPENCL_GPU) return 3;
    for (index = 0; index < count; ++index) {
        const float cpu_reference = left[index] + right[index];
        if (output[index] != cpu_reference || output[index] != expected[index]) {
            fprintf(stderr, "Unexpected result at element %zu.\n", index);
            return 2;
        }
    }
    puts(selected_backend == SOTLAS_COMPUTE_BACKEND_OPENCL_GPU
        ? "OpenCL vector add passed."
        : "CPU fallback vector add passed.");
    return 0;
}
