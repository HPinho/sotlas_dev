#include "opencl_vector.h"

int main(void) {
    const float left[] = {1.5f, -2.0f, 7.0f, 0.125f};
    const float right[] = {2.5f, 3.0f, -4.0f, -0.5f};
    const float expected[] = {4.0f, 1.0f, 3.0f, -0.375f};
    float output[] = {-91.0f, -92.0f, -93.0f, -94.0f};
    const size_t count = sizeof(left) / sizeof(left[0]);
    sotlas_compute_backend_t backend = SOTLAS_COMPUTE_BACKEND_CPU;
    size_t index;

    if (sotlas_vector_add_f32_with_policy(
            left, right, output, count, SOTLAS_COMPUTE_OPENCL_REQUIRED,
            &backend) != SOTLAS_OPENCL_NO_GPU ||
        backend != SOTLAS_COMPUTE_BACKEND_NONE ||
        output[0] != -91.0f || output[1] != -92.0f ||
        output[2] != -93.0f || output[3] != -94.0f) {
        return 1;
    }

    if (sotlas_vector_add_f32_with_policy(
            left, right, output, count,
            SOTLAS_COMPUTE_OPENCL_WITH_CPU_FALLBACK, &backend) !=
            SOTLAS_OPENCL_OK ||
        backend != SOTLAS_COMPUTE_BACKEND_CPU) {
        return 2;
    }
    for (index = 0; index < count; ++index) {
        if (output[index] != expected[index]) return 3;
    }
    return 0;
}
