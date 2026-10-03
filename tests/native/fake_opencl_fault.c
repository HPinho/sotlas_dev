/* A tiny OpenCL 1.2 fault provider used to verify runtime cleanup without a GPU. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#if defined(_WIN32)
#include <windows.h>
#endif

typedef int32_t cl_int;
typedef uint32_t cl_uint;
typedef uint64_t cl_device_type;
typedef uint64_t cl_mem_flags;
typedef uint64_t cl_queue_properties;
typedef uint32_t cl_bool;
typedef uint32_t cl_profiling_info;
typedef intptr_t cl_context_properties;
typedef struct _cl_platform_id *cl_platform_id;
typedef struct _cl_device_id *cl_device_id;
typedef struct _cl_context *cl_context;
typedef struct _cl_command_queue *cl_command_queue;
typedef struct _cl_mem *cl_mem;
typedef struct _cl_event *cl_event;
typedef struct _cl_program *cl_program;
typedef struct _cl_kernel *cl_kernel;

#if defined(_WIN32)
#define SOTLAS_FAKE_EXPORT __declspec(dllexport)
#else
#define SOTLAS_FAKE_EXPORT
#endif

#define CL_SUCCESS 0
#define CL_DEVICE_NOT_FOUND (-1)
#define CL_DEVICE_TYPE_GPU ((cl_device_type)1u << 2)
#define CL_TRUE 1u

enum { FAKE_KIND_CONTEXT, FAKE_KIND_QUEUE, FAKE_KIND_PROGRAM, FAKE_KIND_KERNEL,
       FAKE_KIND_BUFFER, FAKE_KIND_EVENT, RESOURCE_COUNT };
static unsigned created[RESOURCE_COUNT];
static unsigned released[RESOURCE_COUNT];
static uintptr_t next_handle = 1;
static unsigned buffers_created;
static unsigned writes_created;
static cl_mem buffer_handles[3];
static float *buffer_data[3];
static size_t buffer_sizes[3];
static cl_mem kernel_args[3];

static int buffer_index(cl_mem handle) {
    unsigned index;
    for (index = 0; index < 3; ++index) {
        if (buffer_handles[index] == handle) return (int)index;
    }
    return -1;
}

static const char *fault(void) {
#if defined(_WIN32)
    static char value[64];
    DWORD length = GetEnvironmentVariableA("SOTLAS_FAKE_OPENCL_FAIL_AT", value,
                                           (DWORD)sizeof(value));
    if (length == 0 || length >= sizeof(value)) return "";
    return value;
#else
    const char *value = getenv("SOTLAS_FAKE_OPENCL_FAIL_AT");
    return value ? value : "";
#endif
}

static int fails(const char *point) { return strcmp(fault(), point) == 0; }

static void *new_handle(unsigned kind) {
    ++created[kind];
    return (void *)next_handle++;
}

static int release_handle(void *handle, unsigned kind) {
    if (!handle) return -1;
    ++released[kind];
    return CL_SUCCESS;
}

SOTLAS_FAKE_EXPORT int sotlas_fake_opencl_cleanup_ok(void) {
    unsigned kind;
    for (kind = 0; kind < RESOURCE_COUNT; ++kind) {
        if (created[kind] != released[kind]) return 0;
    }
    for (kind = 0; kind < 3; ++kind) {
        if (buffer_data[kind] != NULL) return 0;
    }
    return 1;
}

SOTLAS_FAKE_EXPORT cl_int clGetPlatformIDs(cl_uint capacity, cl_platform_id *items, cl_uint *count) {
    if (fails("no_platform")) {
        if (count) *count = 0;
        return CL_SUCCESS;
    }
    if (count) *count = 1;
    if (capacity && items) items[0] = (cl_platform_id)(uintptr_t)1;
    return CL_SUCCESS;
}

SOTLAS_FAKE_EXPORT cl_int clGetDeviceIDs(cl_platform_id platform, cl_device_type type,
                      cl_uint capacity, cl_device_id *items, cl_uint *count) {
    (void)platform;
    if (type != CL_DEVICE_TYPE_GPU) return CL_DEVICE_NOT_FOUND;
    if (fails("no_gpu")) {
        if (count) *count = 0;
        return CL_DEVICE_NOT_FOUND;
    }
    if (count) *count = 1;
    if (capacity && items) items[0] = (cl_device_id)(uintptr_t)2;
    return CL_SUCCESS;
}

SOTLAS_FAKE_EXPORT cl_context clCreateContext(const cl_context_properties *properties, cl_uint count,
                           const cl_device_id *devices, void *notify, void *data,
                           cl_int *error) {
    (void)properties; (void)count; (void)devices; (void)notify; (void)data;
    if (fails("context")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_context)new_handle(FAKE_KIND_CONTEXT);
}
SOTLAS_FAKE_EXPORT cl_int clReleaseContext(cl_context value) { return release_handle(value, FAKE_KIND_CONTEXT); }

SOTLAS_FAKE_EXPORT cl_command_queue clCreateCommandQueue(cl_context context, cl_device_id device,
                                      cl_queue_properties properties, cl_int *error) {
    (void)context; (void)device; (void)properties;
    if (fails("queue")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_command_queue)new_handle(FAKE_KIND_QUEUE);
}
SOTLAS_FAKE_EXPORT cl_int clReleaseCommandQueue(cl_command_queue value) { return release_handle(value, FAKE_KIND_QUEUE); }

SOTLAS_FAKE_EXPORT cl_program clCreateProgramWithSource(cl_context context, cl_uint count,
                                     const char **source, const size_t *length,
                                     cl_int *error) {
    (void)context; (void)count; (void)source; (void)length;
    if (fails("program")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_program)new_handle(FAKE_KIND_PROGRAM);
}
SOTLAS_FAKE_EXPORT cl_int clBuildProgram(cl_program program, cl_uint count, const cl_device_id *devices,
                      const char *options, void *notify, void *data) {
    (void)program; (void)count; (void)devices; (void)options; (void)notify; (void)data;
    return fails("build") ? -1 : CL_SUCCESS;
}
SOTLAS_FAKE_EXPORT cl_int clReleaseProgram(cl_program value) { return release_handle(value, FAKE_KIND_PROGRAM); }

SOTLAS_FAKE_EXPORT cl_kernel clCreateKernel(cl_program program, const char *name, cl_int *error) {
    (void)program; (void)name;
    if (fails("kernel")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_kernel)new_handle(FAKE_KIND_KERNEL);
}
SOTLAS_FAKE_EXPORT cl_int clReleaseKernel(cl_kernel value) { return release_handle(value, FAKE_KIND_KERNEL); }

SOTLAS_FAKE_EXPORT cl_mem clCreateBuffer(cl_context context, cl_mem_flags flags, size_t size,
                      void *host, cl_int *error) {
    unsigned index;
    (void)context; (void)flags; (void)host;
    ++buffers_created;
    if (fails("buffer") && buffers_created == 2) { *error = -1; return NULL; }
    index = buffers_created - 1;
    if (index >= 3) { *error = -1; return NULL; }
    buffer_data[index] = (float *)calloc(size / sizeof(float), sizeof(float));
    if (!buffer_data[index] && size != 0) { *error = -1; return NULL; }
    buffer_sizes[index] = size;
    buffer_handles[index] = (cl_mem)new_handle(FAKE_KIND_BUFFER);
    *error = CL_SUCCESS;
    return buffer_handles[index];
}
SOTLAS_FAKE_EXPORT cl_int clReleaseMemObject(cl_mem value) {
    int index = buffer_index(value);
    if (index < 0) return -1;
    free(buffer_data[index]);
    buffer_data[index] = NULL;
    buffer_handles[index] = NULL;
    buffer_sizes[index] = 0;
    return release_handle(value, FAKE_KIND_BUFFER);
}

SOTLAS_FAKE_EXPORT cl_int clSetKernelArg(cl_kernel kernel, cl_uint index, size_t size, const void *value) {
    (void)kernel;
    if (fails("arg") || index >= 3 || size != sizeof(cl_mem) || !value) return -1;
    memcpy(&kernel_args[index], value, sizeof(cl_mem));
    return CL_SUCCESS;
}
SOTLAS_FAKE_EXPORT cl_int clEnqueueWriteBuffer(cl_command_queue queue, cl_mem buffer, cl_bool blocking,
                            size_t offset, size_t size, const void *data,
                            cl_uint wait_count, const cl_event *wait_list,
                            cl_event *event) {
    int index = buffer_index(buffer);
    (void)queue; (void)blocking; (void)wait_count; (void)wait_list;
    ++writes_created;
    if (fails("write") && writes_created == 2) return -1;
    if (index < 0 || offset > buffer_sizes[index] ||
        size > buffer_sizes[index] - offset || !data) return -1;
    memcpy((unsigned char *)buffer_data[index] + offset, data, size);
    *event = (cl_event)new_handle(FAKE_KIND_EVENT);
    return CL_SUCCESS;
}
SOTLAS_FAKE_EXPORT cl_int clEnqueueNDRangeKernel(cl_command_queue queue, cl_kernel kernel,
                              cl_uint dimensions, const size_t *offset,
                              const size_t *global, const size_t *local,
                              cl_uint wait_count, const cl_event *wait_list,
                              cl_event *event) {
    int left_index = buffer_index(kernel_args[0]);
    int right_index = buffer_index(kernel_args[1]);
    int output_index = buffer_index(kernel_args[2]);
    size_t item;
    (void)queue; (void)kernel; (void)dimensions; (void)offset;
    (void)local; (void)wait_count; (void)wait_list;
    if (fails("kernel_enqueue")) return -1;
    if (!global || left_index < 0 || right_index < 0 || output_index < 0) return -1;
    for (item = 0; item < global[0]; ++item) {
        if ((item + 1) * sizeof(float) > buffer_sizes[left_index] ||
            (item + 1) * sizeof(float) > buffer_sizes[right_index] ||
            (item + 1) * sizeof(float) > buffer_sizes[output_index]) return -1;
        buffer_data[output_index][item] =
            buffer_data[left_index][item] + buffer_data[right_index][item];
    }
    *event = (cl_event)new_handle(FAKE_KIND_EVENT);
    return CL_SUCCESS;
}
SOTLAS_FAKE_EXPORT cl_int clFinish(cl_command_queue queue) {
    (void)queue;
    return fails("finish") ? -1 : CL_SUCCESS;
}
SOTLAS_FAKE_EXPORT cl_int clEnqueueReadBuffer(cl_command_queue queue, cl_mem buffer, cl_bool blocking,
                           size_t offset, size_t size, void *data,
                           cl_uint wait_count, const cl_event *wait_list,
                           cl_event *event) {
    int index = buffer_index(buffer);
    (void)queue; (void)blocking; (void)wait_count; (void)wait_list;
    if (fails("read")) return -1;
    if (index < 0 || offset > buffer_sizes[index] ||
        size > buffer_sizes[index] - offset || !data) return -1;
    memcpy(data, (unsigned char *)buffer_data[index] + offset, size);
    *event = (cl_event)new_handle(FAKE_KIND_EVENT);
    return CL_SUCCESS;
}
SOTLAS_FAKE_EXPORT cl_int clGetEventProfilingInfo(cl_event event, cl_profiling_info key,
                               size_t size, void *value, size_t *size_out) {
    uint64_t timing = key == 0x1282u ? 10u : 20u;
    (void)event; (void)size; (void)size_out;
    if (fails("profile")) return -1;
    *(uint64_t *)value = timing;
    return CL_SUCCESS;
}
SOTLAS_FAKE_EXPORT cl_int clReleaseEvent(cl_event value) { return release_handle(value, FAKE_KIND_EVENT); }
