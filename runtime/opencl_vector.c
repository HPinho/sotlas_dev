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
typedef uint64_t cl_command_queue_properties;
typedef uint32_t cl_profiling_info;
typedef intptr_t cl_context_properties;
typedef intptr_t cl_queue_properties;
typedef struct _cl_platform_id *cl_platform_id;
typedef struct _cl_device_id *cl_device_id;
typedef struct _cl_context *cl_context;
typedef struct _cl_command_queue *cl_command_queue;
typedef struct _cl_mem *cl_mem;
typedef struct _cl_event *cl_event;
typedef struct _cl_program *cl_program;
typedef struct _cl_kernel *cl_kernel;

#define CL_SUCCESS 0
#define CL_DEVICE_NOT_FOUND (-1)
#define CL_DEVICE_TYPE_GPU ((cl_device_type)1u << 2)
#define CL_MEM_WRITE_ONLY ((cl_mem_flags)1u << 1)
#define CL_MEM_READ_ONLY ((cl_mem_flags)1u << 2)
#define CL_MEM_COPY_HOST_PTR ((cl_mem_flags)1u << 5)
#define CL_QUEUE_PROFILING_ENABLE ((cl_command_queue_properties)1u << 1)
#define CL_PROFILING_COMMAND_START ((cl_profiling_info)0x1282u)
#define CL_PROFILING_COMMAND_END ((cl_profiling_info)0x1283u)
#define CL_TRUE 1u

typedef cl_int (SOTLAS_CL_CALL *clGetPlatformIDs_fn)(cl_uint, cl_platform_id *, cl_uint *);
typedef cl_int (SOTLAS_CL_CALL *clGetDeviceIDs_fn)(cl_platform_id, cl_device_type, cl_uint, cl_device_id *, cl_uint *);
typedef cl_context (SOTLAS_CL_CALL *clCreateContext_fn)(const cl_context_properties *, cl_uint, const cl_device_id *, void (*)(const char *, const void *, size_t, void *), void *, cl_int *);
typedef cl_int (SOTLAS_CL_CALL *clReleaseContext_fn)(cl_context);
typedef cl_command_queue (SOTLAS_CL_CALL *clCreateCommandQueue_fn)(cl_context, cl_device_id, cl_command_queue_properties, cl_int *);
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
typedef cl_int (SOTLAS_CL_CALL *clEnqueueWriteBuffer_fn)(cl_command_queue, cl_mem, cl_bool, size_t, size_t, const void *, cl_uint, const cl_event *, cl_event *);
typedef cl_int (SOTLAS_CL_CALL *clGetEventProfilingInfo_fn)(cl_event, cl_profiling_info, size_t, void *, size_t *);
typedef cl_int (SOTLAS_CL_CALL *clReleaseEvent_fn)(cl_event);
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
    clEnqueueWriteBuffer_fn enqueue_write_buffer;
    clGetEventProfilingInfo_fn get_event_profiling_info;
    clReleaseEvent_fn release_event;
    clFinish_fn finish;
} sotlas_opencl_api_t;

static void *sotlas_opencl_symbol(sotlas_library_t library, const char *name) {
#if defined(_WIN32)
    return (void *)GetProcAddress(library, name);
#else
    return dlsym(library, name);
#endif
}

static sotlas_library_t sotlas_opencl_open_library(const char *path) {
#if defined(_WIN32)
    return LoadLibraryA(path);
#else
    return dlopen(path, RTLD_NOW | RTLD_LOCAL);
#endif
}

static int sotlas_opencl_load_override(sotlas_library_t *library) {
#if defined(_WIN32)
    char *library_override = NULL;
    size_t library_override_length = 0;
    if (_dupenv_s(
            &library_override,
            &library_override_length,
            "SOTLAS_OPENCL_LIBRARY"
        ) != 0) {
        return -1;
    }
    if (!library_override || library_override[0] == '\0') {
        free(library_override);
        return 0;
    }
    *library = sotlas_opencl_open_library(library_override);
    free(library_override);
    return *library ? 1 : -1;
#else
    const char *library_override = getenv("SOTLAS_OPENCL_LIBRARY");
    if (!library_override || library_override[0] == '\0') return 0;
    *library = sotlas_opencl_open_library(library_override);
    return *library ? 1 : -1;
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
    int override_status;
    memset(api, 0, sizeof(*api));
    override_status = sotlas_opencl_load_override(&api->library);
    if (override_status < 0) return 0;
    if (override_status == 0) {
#if defined(_WIN32)
        api->library = sotlas_opencl_open_library("OpenCL.dll");
#elif defined(__APPLE__)
        api->library = sotlas_opencl_open_library(
            "/System/Library/Frameworks/OpenCL.framework/OpenCL"
        );
#else
        api->library = sotlas_opencl_open_library("libOpenCL.so.1");
        if (!api->library) {
            api->library = sotlas_opencl_open_library("libOpenCL.so");
        }
#endif
    }
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
    SOTLAS_LOAD_OPENCL(api, enqueue_write_buffer, "clEnqueueWriteBuffer");
    SOTLAS_LOAD_OPENCL(api, get_event_profiling_info, "clGetEventProfilingInfo");
    SOTLAS_LOAD_OPENCL(api, release_event, "clReleaseEvent");
    SOTLAS_LOAD_OPENCL(api, finish, "clFinish");
    return 1;
}

#undef SOTLAS_LOAD_OPENCL

static cl_device_id sotlas_opencl_gpu_at(
    sotlas_opencl_api_t *api,
    size_t target_index,
    size_t *gpu_count_out,
    sotlas_opencl_status_t *status
) {
    cl_uint platform_count = 0;
    cl_platform_id *platforms = NULL;
    cl_device_id selected = NULL;
    size_t gpu_count = 0;
    cl_uint index;

    if (gpu_count_out) *gpu_count_out = 0;
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
            if (gpu_count <= target_index &&
                target_index - gpu_count < (size_t)device_count) {
                selected = devices[target_index - gpu_count];
            }
            if ((size_t)device_count > SIZE_MAX - gpu_count) {
                free(devices);
                *status = SOTLAS_OPENCL_BACKEND_ERROR;
                goto done;
            }
            gpu_count += (size_t)device_count;
            free(devices);
            continue;
        }
        free(devices);
        *status = SOTLAS_OPENCL_BACKEND_ERROR;
        goto done;
    }

done:
    if (gpu_count_out) *gpu_count_out = gpu_count;
    if (*status != SOTLAS_OPENCL_BACKEND_ERROR) {
        if (gpu_count == 0) {
            *status = SOTLAS_OPENCL_NO_GPU;
        } else if (target_index == SIZE_MAX || selected) {
            *status = SOTLAS_OPENCL_OK;
        } else {
            *status = SOTLAS_OPENCL_DEVICE_NOT_FOUND;
        }
    }
    free(platforms);
    return selected;
}

static int sotlas_opencl_event_duration(
    sotlas_opencl_api_t *api,
    cl_event event,
    cl_ulong *duration
) {
    cl_ulong start = 0;
    cl_ulong end = 0;
    if (!event || !duration ||
        api->get_event_profiling_info(
            event, CL_PROFILING_COMMAND_START, sizeof(start), &start, NULL
        ) != CL_SUCCESS ||
        api->get_event_profiling_info(
            event, CL_PROFILING_COMMAND_END, sizeof(end), &end, NULL
        ) != CL_SUCCESS ||
        end < start) {
        return 0;
    }
    *duration = end - start;
    return 1;
}

static sotlas_opencl_status_t sotlas_opencl_vector_add_f32_impl(
    const float *left,
    const float *right,
    float *output,
    size_t count,
    sotlas_opencl_profile_t *profile,
    size_t gpu_index
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
    sotlas_opencl_status_t device_status = SOTLAS_OPENCL_BACKEND_ERROR;
    cl_device_id device = NULL;
    cl_context context = NULL;
    cl_command_queue queue = NULL;
    cl_program program = NULL;
    cl_kernel kernel = NULL;
    cl_mem left_buffer = NULL;
    cl_mem right_buffer = NULL;
    cl_mem output_buffer = NULL;
    cl_event left_write_event = NULL;
    cl_event right_write_event = NULL;
    cl_event kernel_event = NULL;
    cl_event read_event = NULL;
    cl_int result = CL_SUCCESS;
    cl_ulong left_write_duration = 0;
    cl_ulong right_write_duration = 0;
    cl_ulong kernel_duration = 0;
    cl_ulong read_duration = 0;
    size_t index;

    if (profile) {
        profile->upload_nanoseconds = 0;
        profile->kernel_nanoseconds = 0;
        profile->download_nanoseconds = 0;
    }
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

    device = sotlas_opencl_gpu_at(&api, gpu_index, NULL, &device_status);
    if (!device) {
        status = device_status;
        goto cleanup;
    }
    context = api.create_context(NULL, 1, &device, NULL, NULL, &result);
    if (!context || result != CL_SUCCESS) goto cleanup;
    queue = api.create_command_queue(
        context, device, CL_QUEUE_PROFILING_ENABLE, &result
    );
    if (!queue || result != CL_SUCCESS) goto cleanup;
    program = api.create_program_with_source(context, 1, &source_pointer, NULL, &result);
    if (!program || result != CL_SUCCESS) goto cleanup;
    if (api.build_program(program, 1, &device, "-cl-std=CL1.2", NULL, NULL) != CL_SUCCESS) {
        goto cleanup;
    }
    kernel = api.create_kernel(program, "vector_add_f32", &result);
    if (!kernel || result != CL_SUCCESS) goto cleanup;
    left_buffer = api.create_buffer(
        context, CL_MEM_READ_ONLY, byte_count, NULL, &result
    );
    if (!left_buffer || result != CL_SUCCESS) goto cleanup;
    right_buffer = api.create_buffer(
        context, CL_MEM_READ_ONLY, byte_count, NULL, &result
    );
    if (!right_buffer || result != CL_SUCCESS) goto cleanup;
    output_buffer = api.create_buffer(
        context, CL_MEM_WRITE_ONLY, byte_count, NULL, &result
    );
    if (!output_buffer || result != CL_SUCCESS) goto cleanup;
    if (api.enqueue_write_buffer(
            queue, left_buffer, CL_TRUE, 0, byte_count, left,
            0, NULL, &left_write_event
        ) != CL_SUCCESS || !left_write_event) {
        goto cleanup;
    }
    if (api.enqueue_write_buffer(
            queue, right_buffer, CL_TRUE, 0, byte_count, right,
            0, NULL, &right_write_event
        ) != CL_SUCCESS || !right_write_event) {
        goto cleanup;
    }
    if (api.set_kernel_arg(kernel, 0, sizeof(left_buffer), &left_buffer) != CL_SUCCESS ||
        api.set_kernel_arg(kernel, 1, sizeof(right_buffer), &right_buffer) != CL_SUCCESS ||
        api.set_kernel_arg(kernel, 2, sizeof(output_buffer), &output_buffer) != CL_SUCCESS) {
        goto cleanup;
    }
    if (api.enqueue_ndrange_kernel(
            queue, kernel, 1, NULL, &count, NULL, 0, NULL, &kernel_event
        ) != CL_SUCCESS || !kernel_event) {
        goto cleanup;
    }
    if (api.finish(queue) != CL_SUCCESS) goto cleanup;
    if (api.enqueue_read_buffer(
            queue, output_buffer, CL_TRUE, 0, byte_count, staging,
            0, NULL, &read_event
        ) != CL_SUCCESS || !read_event) {
        goto cleanup;
    }
    if (!sotlas_opencl_event_duration(
            &api, left_write_event, &left_write_duration
        ) ||
        !sotlas_opencl_event_duration(
            &api, right_write_event, &right_write_duration
        ) ||
        !sotlas_opencl_event_duration(&api, kernel_event, &kernel_duration) ||
        !sotlas_opencl_event_duration(&api, read_event, &read_duration)) {
        goto cleanup;
    }
    if (profile) {
        profile->upload_nanoseconds =
            (uint64_t)left_write_duration + (uint64_t)right_write_duration;
        profile->kernel_nanoseconds = (uint64_t)kernel_duration;
        profile->download_nanoseconds = (uint64_t)read_duration;
    }
    for (index = 0; index < count; ++index) output[index] = staging[index];
    status = SOTLAS_OPENCL_OK;

cleanup:
    if (read_event) (void)api.release_event(read_event);
    if (kernel_event) (void)api.release_event(kernel_event);
    if (right_write_event) (void)api.release_event(right_write_event);
    if (left_write_event) (void)api.release_event(left_write_event);
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

sotlas_opencl_status_t sotlas_opencl_vector_add_f32(
    const float *left,
    const float *right,
    float *output,
    size_t count
) {
    return sotlas_opencl_vector_add_f32_impl(
        left, right, output, count, NULL, 0
    );
}

sotlas_opencl_status_t sotlas_opencl_vector_add_f32_profiled(
    const float *left,
    const float *right,
    float *output,
    size_t count,
    sotlas_opencl_profile_t *profile
) {
    if (!profile) return SOTLAS_OPENCL_INVALID_ARGUMENT;
    return sotlas_opencl_vector_add_f32_impl(
        left, right, output, count, profile, 0
    );
}

sotlas_opencl_status_t sotlas_opencl_get_gpu_count(size_t *count) {
    sotlas_opencl_api_t api;
    sotlas_opencl_status_t status = SOTLAS_OPENCL_BACKEND_ERROR;
    if (!count) return SOTLAS_OPENCL_INVALID_ARGUMENT;
    *count = 0;
    if (!sotlas_opencl_load(&api)) return SOTLAS_OPENCL_RUNTIME_UNAVAILABLE;
    (void)sotlas_opencl_gpu_at(&api, SIZE_MAX, count, &status);
    sotlas_opencl_close_library(api.library);
    return status;
}

sotlas_opencl_status_t sotlas_opencl_vector_add_f32_on_gpu(
    const float *left,
    const float *right,
    float *output,
    size_t count,
    size_t gpu_index
) {
    return sotlas_opencl_vector_add_f32_impl(
        left, right, output, count, NULL, gpu_index
    );
}

sotlas_opencl_status_t sotlas_opencl_vector_add_f32_profiled_on_gpu(
    const float *left,
    const float *right,
    float *output,
    size_t count,
    size_t gpu_index,
    sotlas_opencl_profile_t *profile
) {
    if (!profile) return SOTLAS_OPENCL_INVALID_ARGUMENT;
    return sotlas_opencl_vector_add_f32_impl(
        left, right, output, count, profile, gpu_index
    );
}

static sotlas_opencl_status_t sotlas_cpu_vector_add_f32(
    const float *left,
    const float *right,
    float *output,
    size_t count
) {
    size_t index;
    if (count == 0) return SOTLAS_OPENCL_OK;
    if (!left || !right || !output) return SOTLAS_OPENCL_INVALID_ARGUMENT;
    if (count > SIZE_MAX / sizeof(float)) return SOTLAS_OPENCL_SIZE_OVERFLOW;
    for (index = 0; index < count; ++index) {
        output[index] = left[index] + right[index];
    }
    return SOTLAS_OPENCL_OK;
}

sotlas_opencl_status_t sotlas_vector_add_f32_with_policy(
    const float *left,
    const float *right,
    float *output,
    size_t count,
    sotlas_compute_policy_t policy,
    sotlas_compute_backend_t *selected_backend
) {
    sotlas_opencl_status_t status;
    if (!selected_backend) return SOTLAS_OPENCL_INVALID_ARGUMENT;
    *selected_backend = SOTLAS_COMPUTE_BACKEND_NONE;
    if (policy != SOTLAS_COMPUTE_CPU_ONLY &&
        policy != SOTLAS_COMPUTE_OPENCL_REQUIRED &&
        policy != SOTLAS_COMPUTE_OPENCL_WITH_CPU_FALLBACK) {
        return SOTLAS_OPENCL_INVALID_ARGUMENT;
    }
    if (count == 0) return SOTLAS_OPENCL_OK;
    if (!left || !right || !output) return SOTLAS_OPENCL_INVALID_ARGUMENT;
    if (count > SIZE_MAX / sizeof(float)) return SOTLAS_OPENCL_SIZE_OVERFLOW;

    if (policy == SOTLAS_COMPUTE_CPU_ONLY) {
        status = sotlas_cpu_vector_add_f32(left, right, output, count);
        if (status == SOTLAS_OPENCL_OK) {
            *selected_backend = SOTLAS_COMPUTE_BACKEND_CPU;
        }
        return status;
    }

    status = sotlas_opencl_vector_add_f32(left, right, output, count);
    if (status == SOTLAS_OPENCL_OK) {
        *selected_backend = SOTLAS_COMPUTE_BACKEND_OPENCL_GPU;
        return status;
    }
    if (policy != SOTLAS_COMPUTE_OPENCL_WITH_CPU_FALLBACK ||
        (status != SOTLAS_OPENCL_RUNTIME_UNAVAILABLE &&
         status != SOTLAS_OPENCL_NO_GPU)) {
        return status;
    }

    status = sotlas_cpu_vector_add_f32(left, right, output, count);
    if (status == SOTLAS_OPENCL_OK) {
        *selected_backend = SOTLAS_COMPUTE_BACKEND_CPU;
    }
    return status;
}
