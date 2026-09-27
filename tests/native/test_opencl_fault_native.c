#include "opencl_vector.h"

int main(void) {
    const float left[] = {1.0f, 2.0f};
    const float right[] = {3.0f, 4.0f};
    float output[] = {-91.0f, -92.0f};
    if (sotlas_opencl_vector_add_f32(left, right, output, 2) !=
        SOTLAS_OPENCL_BACKEND_ERROR) return 1;
    if (output[0] != -91.0f || output[1] != -92.0f) return 2;
    return 0;
}
