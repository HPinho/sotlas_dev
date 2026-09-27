/* Minimal dynamically-loaded OpenCL 1.2 provider for an f32 vector-add test. */
#include "opencl_vector.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#define SOTLAS_CL_CALL __stdcall
typedef HMODULE sotlas_library_t;
#else
#include <dlfcn.h>
#define SOTLAS_CL_CALL
typedef void *sotlas_library_t;
#endif

typedef int32_t cl_int;
typedef uint32_t cl_uint;
typedef uint32_t cl_bool;
typedef uint64_t cl_device_type;
typedef uint64_t cl_mem_flags;
typedef uint64_t cl_ulong;
typedef intptr_t cl_context_properties;
typedef intptr_t cl_queue_properties;
typedef struct _cl_platform_id *cl_platform_id;
typedef struct _cl_device_id *cl_device_id;
typedef struct _cl_context *cl_context;
typedef struct _cl_command_queue *cl_command_queue;
typedef struct _cl_mem *cl_mem;
typedef struct _cl_program *cl_program;
typedef struct _cl_kernel *cl_kernel;

#define CL_SUCCESS 0
#define CL_DEVICE_NOT_FOUND (-1)
#define CL_DEVICE_TYPE_GPU ((cl_device_type)1u << 2)
#define CL_MEM_WRITE_ONLY ((cl_mem_flags)1u << 1)
#define CL_MEM_READ_ONLY ((cl_mem_flags)1u << 2)
#define CL_MEM_COPY_HOST_PTR ((cl_mem_flags)1u << 5)
#define CL_TRUE 1u

typedef cl_int (SOTLAS_CL_CALL *clGetPlatformIDs_fn)(cl_uint, cl_platform_id *, cl_uint *);
typedef cl_int (SOTLAS_CL_CALL *clGetDeviceIDs_fn)(cl_platform_id, cl_device_type, cl_uint, cl_device_id *, cl_uint *);
typedef cl_context (SOTLAS_CL_CALL *clCreateContext_fn)(const cl_context_properties *, cl_uint, const cl_device_id *, void (*)(const char *, const void *, size_t, void *), void *, cl_int *);
typedef cl_int (SOTLAS_CL_CALL *clReleaseContext_fn)(cl_context);
typedef cl_command_queue (SOTLAS_CL_CALL *clCreateCommandQueue_fn)(cl_context, cl_device_id, cl_ulong, cl_int *);
typedef cl_int (SOTLAS_CL_CALL *clReleaseCommandQueue_fn)(cl_command_queue);
typedef cl_program (SOTLAS_CL_CALL *clCreateProgramWithSource_fn)(cl_context, cl_uint, const char **, const size_t *, cl_int *);
typedef cl_int (SOTLAS_CL_CALL *clBuildProgram_fn)(cl_program, cl_uint, const cl_device_id *, const char *, void (*)(cl_program, void *), void *);
typedef cl_int (SOTLAS_CL_CALL *clReleaseProgram_fn)(cl_program);
typedef cl_kernel (SOTLAS_CL_CALL *clCreateKernel_fn)(cl_program, const char *, cl_int *);
typedef cl_int (SOTLAS_CL_CALL *clReleaseKernel_fn)(cl_kernel);
typedef cl_mem (SOTLAS_CL_CALL *clCreateBuffer_fn)(cl_context, cl_mem_flags, size_t, void *, cl_int *);
typedef cl_int (SOTLAS_CL_CALL *clReleaseMemObject_fn)(cl_mem);
typedef cl_int (SOTLAS_CL_CALL *clSetKernelArg_fn)(cl_kernel, cl_uint, size_t, const void *);
typedef cl_int (SOTLAS_CL_CALL *clEnqueueNDRangeKernel_fn)(cl_command_queue, cl_kernel, cl_uint, const size_t *, const size_t *, const size_t *, cl_uint, const void *, void *);
typedef cl_int (SOTLAS_CL_CALL *clEnqueueReadBuffer_fn)(cl_command_queue, cl_mem, cl_bool, size_t, size_t, void *, cl_uint, const void *, void *);
typedef cl_int (SOTLAS_CL_CALL *clFinish_fn)(cl_command_queue);

typedef struct sotlas_opencl_api {
    sotlas_library_t library;
    clGetPlatformIDs_fn get_platform_ids;
    clGetDeviceIDs_fn get_device_ids;
    clCreateContext_fn create_context;
    clReleaseContext_fn release_context;
    clCreateCommandQueue_fn create_command_queue;
    clReleaseCommandQueue_fn release_command_queue;
    clCreateProgramWithSource_fn create_program_with_source;
    clBuildProgram_fn build_program;
    clReleaseProgram_fn release_program;
    clCreateKernel_fn create_kernel;
    clReleaseKernel_fn release_kernel;
    clCreateBuffer_fn create_buffer;
    clReleaseMemObject_fn release_mem_object;
    clSetKernelArg_fn set_kernel_arg;
    clEnqueueNDRangeKernel_fn enqueue_ndrange_kernel;
    clEnqueueReadBuffer_fn enqueue_read_buffer;
    clFinish_fn finish;
} sotlas_opencl_api_t;

static void *sotlas_opencl_symbol(sotlas_library_t library, const char *name) {
#if defined(_WIN32)
    return (void *)GetProcAddress(library, name);
#else
    return dlsym(library, name);
#endif
}

static void sotlas_opencl_close_library(sotlas_library_t library) {
    if (!library) return;
#if defined(_WIN32)
    FreeLibrary(library);
#else
    dlclose(library);
#endif
}

#define SOTLAS_LOAD_OPENCL(api, field, symbol) do { \
    void *address = sotlas_opencl_symbol((api)->library, symbol); \
    if (!address) { sotlas_opencl_close_library((api)->library); (api)->library = 0; return 0; } \
    (api)->field = (void *)address; \
} while (0)

static int sotlas_opencl_load(sotlas_opencl_api_t *api) {
    memset(api, 0, sizeof(*api));
#if defined(_WIN32)
    api->library = LoadLibraryA("OpenCL.dll");
#elif defined(__APPLE__)
    api->library = dlopen("/System/Library/Frameworks/OpenCL.framework/OpenCL", RTLD_NOW | RTLD_LOCAL);
#else
    api->library = dlopen("libOpenCL.so.1", RTLD_NOW | RTLD_LOCAL);
    if (!api->library) api->library = dlopen("libOpenCL.so", RTLD_NOW | RTLD_LOCAL);
#endif
    if (!api->library) return 0;

    SOTLAS_LOAD_OPENCL(api, get_platform_ids, "clGetPlatformIDs");
    SOTLAS_LOAD_OPENCL(api, get_device_ids, "clGetDeviceIDs");
    SOTLAS_LOAD_OPENCL(api, create_context, "clCreateContext");
    SOTLAS_LOAD_OPENCL(api, release_context, "clReleaseContext");
    SOTLAS_LOAD_OPENCL(api, create_command_queue, "clCreateCommandQueue");
    SOTLAS_LOAD_OPENCL(api, release_command_queue, "clReleaseCommandQueue");
    SOTLAS_LOAD_OPENCL(api, create_program_with_source, "clCreateProgramWithSource");
    SOTLAS_LOAD_OPENCL(api, build_program, "clBuildProgram");
    SOTLAS_LOAD_OPENCL(api, release_program, "clReleaseProgram");
    SOTLAS_LOAD_OPENCL(api, create_kernel, "clCreateKernel");
    SOTLAS_LOAD_OPENCL(api, release_kernel, "clReleaseKernel");
    SOTLAS_LOAD_OPENCL(api, create_buffer, "clCreateBuffer");
    SOTLAS_LOAD_OPENCL(api, release_mem_object, "clReleaseMemObject");
    SOTLAS_LOAD_OPENCL(api, set_kernel_arg, "clSetKernelArg");
    SOTLAS_LOAD_OPENCL(api, enqueue_ndrange_kernel, "clEnqueueNDRangeKernel");
    SOTLAS_LOAD_OPENCL(api, enqueue_read_buffer, "clEnqueueReadBuffer");
    SOTLAS_LOAD_OPENCL(api, finish, "clFinish");
    return 1;
}

#undef SOTLAS_LOAD_OPENCL

static cl_device_id sotlas_opencl_first_gpu(
    sotlas_opencl_api_t *api,
    sotlas_opencl_status_t *status
) {
    cl_uint platform_count = 0;
    cl_platform_id *platforms = NULL;
    cl_device_id selected = NULL;
    cl_uint index;

    if (api->get_platform_ids(0, NULL, &platform_count) != CL_SUCCESS || platform_count == 0) {
        *status = SOTLAS_OPENCL_NO_GPU;
        return NULL;
    }
    if ((size_t)platform_count > SIZE_MAX / sizeof(*platforms)) {
        *status = SOTLAS_OPENCL_BACKEND_ERROR;
        return NULL;
    }
    platforms = (cl_platform_id *)calloc((size_t)platform_count, sizeof(*platforms));
    if (!platforms) {
        *status = SOTLAS_OPENCL_BACKEND_ERROR;
        return NULL;
    }
    if (api->get_platform_ids(platform_count, platforms, NULL) != CL_SUCCESS) {
        *status = SOTLAS_OPENCL_BACKEND_ERROR;
        goto done;
    }

    *status = SOTLAS_OPENCL_NO_GPU;
    for (index = 0; index < platform_count; ++index) {
        cl_uint device_count = 0;
        cl_device_id *devices;
        cl_int result = api->get_device_ids(
            platforms[index], CL_DEVICE_TYPE_GPU, 0, NULL, &device_count
        );
        if (result == CL_DEVICE_NOT_FOUND || device_count == 0) continue;
        if (result != CL_SUCCESS || (size_t)device_count > SIZE_MAX / sizeof(*devices)) {
            *status = SOTLAS_OPENCL_BACKEND_ERROR;
            goto done;
        }
        devices = (cl_device_id *)calloc((size_t)device_count, sizeof(*devices));
        if (!devices) {
            *status = SOTLAS_OPENCL_BACKEND_ERROR;
            goto done;
        }
        result = api->get_device_ids(
            platforms[index], CL_DEVICE_TYPE_GPU, device_count, devices, NULL
        );
        if (result == CL_SUCCESS) {
            selected = devices[0];
            *status = SOTLAS_OPENCL_OK;
            free(devices);
            goto done;
        }
        free(devices);
        *status = SOTLAS_OPENCL_BACKEND_ERROR;
        goto done;
    }

done:
    free(platforms);
    return selected;
}

sotlas_opencl_status_t sotlas_opencl_vector_add_f32(
    const float *left,
    const float *right,
    float *output,
    size_t count
) {
    static const char kernel_source[] =
        "__kernel void vector_add_f32(__global const float *left, "
        "__global const float *right, __global float *output) { "
        "size_t i = get_global_id(0); output[i] = left[i] + right[i]; }";
    const char *source_pointer = kernel_source;
    size_t byte_count;
    float *staging = NULL;
    sotlas_opencl_api_t api;
    sotlas_opencl_status_t status = SOTLAS_OPENCL_BACKEND_ERROR;
    cl_device_id device = NULL;
    cl_context context = NULL;
    cl_command_queue queue = NULL;
    cl_program program = NULL;
    cl_kernel kernel = NULL;
    cl_mem left_buffer = NULL;
    cl_mem right_buffer = NULL;
    cl_mem output_buffer = NULL;
    cl_int result = CL_SUCCESS;
    size_t index;

    if (count == 0) return SOTLAS_OPENCL_OK;
    if (!left || !right || !output) return SOTLAS_OPENCL_INVALID_ARGUMENT;
    if (count > SIZE_MAX / sizeof(float)) return SOTLAS_OPENCL_SIZE_OVERFLOW;
    byte_count = count * sizeof(float);
    staging = (float *)malloc(byte_count);
    if (!staging) return SOTLAS_OPENCL_BACKEND_ERROR;
    if (!sotlas_opencl_load(&api)) {
        free(staging);
        return SOTLAS_OPENCL_RUNTIME_UNAVAILABLE;
    }

    device = sotlas_opencl_first_gpu(&api, &status);
    if (!device) goto cleanup;
    context = api.create_context(NULL, 1, &device, NULL, NULL, &result);
    if (!context || result != CL_SUCCESS) goto cleanup;
    queue = api.create_command_queue(context, device, 0, &result);
    if (!queue || result != CL_SUCCESS) goto cleanup;
    program = api.create_program_with_source(context, 1, &source_pointer, NULL, &result);
    if (!program || result != CL_SUCCESS) goto cleanup;
    if (api.build_program(program, 1, &device, "-cl-std=CL1.2", NULL, NULL) != CL_SUCCESS) {
        goto cleanup;
    }
    kernel = api.create_kernel(program, "vector_add_f32", &result);
    if (!kernel || result != CL_SUCCESS) goto cleanup;
    left_buffer = api.create_buffer(
        context, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
        byte_count, (void *)left, &result
    );
    if (!left_buffer || result != CL_SUCCESS) goto cleanup;
    right_buffer = api.create_buffer(
        context, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR,
        byte_count, (void *)right, &result
    );
    if (!right_buffer || result != CL_SUCCESS) goto cleanup;
    output_buffer = api.create_buffer(
        context, CL_MEM_WRITE_ONLY, byte_count, NULL, &result
    );
    if (!output_buffer || result != CL_SUCCESS) goto cleanup;
    if (api.set_kernel_arg(kernel, 0, sizeof(left_buffer), &left_buffer) != CL_SUCCESS ||
        api.set_kernel_arg(kernel, 1, sizeof(right_buffer), &right_buffer) != CL_SUCCESS ||
        api.set_kernel_arg(kernel, 2, sizeof(output_buffer), &output_buffer) != CL_SUCCESS) {
        goto cleanup;
    }
    if (api.enqueue_ndrange_kernel(
            queue, kernel, 1, NULL, &count, NULL, 0, NULL, NULL
        ) != CL_SUCCESS) {
        goto cleanup;
    }
    if (api.finish(queue) != CL_SUCCESS) goto cleanup;
    if (api.enqueue_read_buffer(
            queue, output_buffer, CL_TRUE, 0, byte_count, staging,
            0, NULL, NULL
        ) != CL_SUCCESS) {
        goto cleanup;
    }
    for (index = 0; index < count; ++index) output[index] = staging[index];
    status = SOTLAS_OPENCL_OK;

cleanup:
    if (output_buffer) (void)api.release_mem_object(output_buffer);
    if (right_buffer) (void)api.release_mem_object(right_buffer);
    if (left_buffer) (void)api.release_mem_object(left_buffer);
    if (kernel) (void)api.release_kernel(kernel);
    if (program) (void)api.release_program(program);
    if (queue) (void)api.release_command_queue(queue);
    if (context) (void)api.release_context(context);
    sotlas_opencl_close_library(api.library);
    free(staging);
    return status;
}
