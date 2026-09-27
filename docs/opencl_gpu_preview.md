# OpenCL GPU preview

The preview includes one native accelerator workload: f32 vector addition on
the first available OpenCL GPU. Sotlas source declares the C ABI call and
exports a system entrypoint; a small C host supplies arrays and checks the
result. The provider dynamically loads the system OpenCL runtime, copies input
arrays to device buffers, dispatches an OpenCL C 1.2 kernel, waits for the queue,
and copies the result back.

## Build and run

From the repository root, with Sotlas installed and Clang available:

```sh
mkdir -p build/opencl-vector
sotlas compile examples/13_opencl_vector_add/main.sotlas --backend c11 --emit-c -o build/opencl-vector/main.c
clang -std=c11 -Wall -Wextra -Werror -Iruntime \
  build/opencl-vector/main.c examples/13_opencl_vector_add/host.c \
  runtime/opencl_vector.c -o build/opencl-vector/opencl-vector
build/opencl-vector/opencl-vector
```

The runtime has no build-time OpenCL SDK dependency. At runtime, Windows needs
`OpenCL.dll`; Linux needs `libOpenCL.so.1` or `libOpenCL.so`; macOS uses the
system OpenCL framework. A machine without an OpenCL GPU returns the explicit
`NO_GPU` or `RUNTIME_UNAVAILABLE` status before touching output memory.

## Current contract

- Input and output are contiguous arrays of 32-bit floats with an explicit
  element count.
- The first GPU returned by the OpenCL platform enumeration is selected.
- Input is copied to device-owned buffers; host arrays remain owned by the
  caller. Output is copied back only after kernel execution and readback succeed.
- Empty input succeeds without loading the driver. Null pointers and size
  overflow are rejected before device access.
- Failures leave the caller's output unchanged. The API returns a status code;
  it does not expose a stable device identifier or asynchronous event handle.
- This demonstrates Sotlas-to-OpenCL C interop through C11. It does not yet
  lower Flow stages or Sotlas expressions into GPU kernels, and it does not
  provide CUDA, Vulkan, NPU, CPU fallback, or cross-device scheduling.

The hardware test is optional in CI because hosted runners do not promise an
OpenCL GPU. It was executed against a physical OpenCL GPU during development.
