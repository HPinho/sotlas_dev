/* A tiny OpenCL 1.2 fault provider used to verify runtime cleanup without a GPU. */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

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

#define CL_SUCCESS 0
#define CL_DEVICE_NOT_FOUND (-1)
#define CL_DEVICE_TYPE_GPU ((cl_device_type)1u << 2)
#define CL_TRUE 1u

enum { CONTEXT, QUEUE, PROGRAM, KERNEL, BUFFER, EVENT, RESOURCE_COUNT };
static unsigned created[RESOURCE_COUNT];
static unsigned released[RESOURCE_COUNT];
static uintptr_t next_handle = 1;
static unsigned buffers_created;
static unsigned writes_created;

static const char *fault(void) {
    const char *value = getenv("SOTLAS_FAKE_OPENCL_FAIL_AT");
    return value ? value : "";
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

__attribute__((destructor)) static void verify_cleanup(void) {
    unsigned kind;
    for (kind = 0; kind < RESOURCE_COUNT; ++kind) {
        if (created[kind] != released[kind]) abort();
    }
}

cl_int clGetPlatformIDs(cl_uint capacity, cl_platform_id *items, cl_uint *count) {
    if (count) *count = 1;
    if (capacity && items) items[0] = (cl_platform_id)(uintptr_t)1;
    return CL_SUCCESS;
}

cl_int clGetDeviceIDs(cl_platform_id platform, cl_device_type type,
                      cl_uint capacity, cl_device_id *items, cl_uint *count) {
    (void)platform;
    if (type != CL_DEVICE_TYPE_GPU) return CL_DEVICE_NOT_FOUND;
    if (count) *count = 1;
    if (capacity && items) items[0] = (cl_device_id)(uintptr_t)2;
    return CL_SUCCESS;
}

cl_context clCreateContext(const cl_context_properties *properties, cl_uint count,
                           const cl_device_id *devices, void *notify, void *data,
                           cl_int *error) {
    (void)properties; (void)count; (void)devices; (void)notify; (void)data;
    if (fails("context")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_context)new_handle(CONTEXT);
}
cl_int clReleaseContext(cl_context value) { return release_handle(value, CONTEXT); }

cl_command_queue clCreateCommandQueue(cl_context context, cl_device_id device,
                                      cl_queue_properties properties, cl_int *error) {
    (void)context; (void)device; (void)properties;
    if (fails("queue")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_command_queue)new_handle(QUEUE);
}
cl_int clReleaseCommandQueue(cl_command_queue value) { return release_handle(value, QUEUE); }

cl_program clCreateProgramWithSource(cl_context context, cl_uint count,
                                     const char **source, const size_t *length,
                                     cl_int *error) {
    (void)context; (void)count; (void)source; (void)length;
    if (fails("program")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_program)new_handle(PROGRAM);
}
cl_int clBuildProgram(cl_program program, cl_uint count, const cl_device_id *devices,
                      const char *options, void *notify, void *data) {
    (void)program; (void)count; (void)devices; (void)options; (void)notify; (void)data;
    return fails("build") ? -1 : CL_SUCCESS;
}
cl_int clReleaseProgram(cl_program value) { return release_handle(value, PROGRAM); }

cl_kernel clCreateKernel(cl_program program, const char *name, cl_int *error) {
    (void)program; (void)name;
    if (fails("kernel")) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_kernel)new_handle(KERNEL);
}
cl_int clReleaseKernel(cl_kernel value) { return release_handle(value, KERNEL); }

cl_mem clCreateBuffer(cl_context context, cl_mem_flags flags, size_t size,
                      void *host, cl_int *error) {
    (void)context; (void)flags; (void)size; (void)host;
    ++buffers_created;
    if (fails("buffer") && buffers_created == 2) { *error = -1; return NULL; }
    *error = CL_SUCCESS;
    return (cl_mem)new_handle(BUFFER);
}
cl_int clReleaseMemObject(cl_mem value) { return release_handle(value, BUFFER); }

cl_int clSetKernelArg(cl_kernel kernel, cl_uint index, size_t size, const void *value) {
    (void)kernel; (void)index; (void)size; (void)value;
    return fails("arg") ? -1 : CL_SUCCESS;
}
cl_int clEnqueueWriteBuffer(cl_command_queue queue, cl_mem buffer, cl_bool blocking,
                            size_t offset, size_t size, const void *data,
                            cl_uint wait_count, const cl_event *wait_list,
                            cl_event *event) {
    (void)queue; (void)buffer; (void)blocking; (void)offset; (void)size;
    (void)data; (void)wait_count; (void)wait_list;
    ++writes_created;
    if (fails("write") && writes_created == 2) return -1;
    *event = (cl_event)new_handle(EVENT);
    return CL_SUCCESS;
}
cl_int clEnqueueNDRangeKernel(cl_command_queue queue, cl_kernel kernel,
                              cl_uint dimensions, const size_t *offset,
                              const size_t *global, const size_t *local,
                              cl_uint wait_count, const cl_event *wait_list,
                              cl_event *event) {
    (void)queue; (void)kernel; (void)dimensions; (void)offset; (void)global;
    (void)local; (void)wait_count; (void)wait_list;
    if (fails("kernel_enqueue")) return -1;
    *event = (cl_event)new_handle(EVENT);
    return CL_SUCCESS;
}
cl_int clFinish(cl_command_queue queue) {
    (void)queue;
    return fails("finish") ? -1 : CL_SUCCESS;
}
cl_int clEnqueueReadBuffer(cl_command_queue queue, cl_mem buffer, cl_bool blocking,
                           size_t offset, size_t size, void *data,
                           cl_uint wait_count, const cl_event *wait_list,
                           cl_event *event) {
    (void)queue; (void)buffer; (void)blocking; (void)offset; (void)size;
    (void)data; (void)wait_count; (void)wait_list;
    if (fails("read")) return -1;
    *event = (cl_event)new_handle(EVENT);
    return CL_SUCCESS;
}
cl_int clGetEventProfilingInfo(cl_event event, cl_profiling_info key,
                               size_t size, void *value, size_t *size_out) {
    uint64_t timing = key == 0x1282u ? 10u : 20u;
    (void)event; (void)size; (void)size_out;
    if (fails("profile")) return -1;
    *(uint64_t *)value = timing;
    return CL_SUCCESS;
}
cl_int clReleaseEvent(cl_event value) { return release_handle(value, EVENT); }
