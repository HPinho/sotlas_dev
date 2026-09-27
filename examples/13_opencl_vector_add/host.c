#include "opencl_vector.h"

#include <stddef.h>
#include <stdio.h>

extern int run_gpu_add(const float *left, const float *right, float *output, size_t count);

int main(void) {
    const float left[] = {1.0f, 2.0f, -3.0f, 8.0f};
    const float right[] = {4.0f, -2.0f, 3.0f, 0.5f};
    const float expected[] = {5.0f, 0.0f, 0.0f, 8.5f};
    float output[] = {-1.0f, -1.0f, -1.0f, -1.0f};
    const size_t count = sizeof(left) / sizeof(left[0]);
    size_t index;
    int status = run_gpu_add(left, right, output, count);

    if (status == SOTLAS_OPENCL_NO_GPU || status == SOTLAS_OPENCL_RUNTIME_UNAVAILABLE) {
        puts("OpenCL GPU unavailable; no device work was submitted.");
        return 77;
    }
    if (status != SOTLAS_OPENCL_OK) {
        fprintf(stderr, "OpenCL vector add failed with status %d.\n", status);
        return 1;
    }
    for (index = 0; index < count; ++index) {
        const float cpu_reference = left[index] + right[index];
        if (output[index] != cpu_reference || output[index] != expected[index]) {
            fprintf(stderr, "Unexpected result at element %zu.\n", index);
            return 2;
        }
    }
    puts("OpenCL vector add passed.");
    return 0;
}
