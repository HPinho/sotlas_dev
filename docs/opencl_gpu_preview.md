# OpenCL GPU preview

The preview includes one native accelerator workload: f32 vector addition on
the first available OpenCL GPU. Sotlas source declares the C ABI calls and
exports system entrypoints; a small C host supplies arrays, requests GPU with
CPU fallback, and checks the result. The provider dynamically loads the system OpenCL runtime, copies input
arrays to device buffers, dispatches an OpenCL C 1.2 kernel, waits for the queue,
and copies the result back. A backend policy API can require OpenCL, run on CPU,
or try OpenCL and fall back to CPU when no runtime or GPU is available.

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
- The default call selects the first GPU returned by OpenCL. Callers can query
  the GPU count and select an enumeration index; indices can change when drivers
  or hardware change and are not persistent device identifiers.
- Input is copied to device-owned buffers; host arrays remain owned by the
  caller. Output is copied back only after kernel execution and readback succeed.
- Empty input succeeds without loading the driver. Null pointers and size
  overflow are rejected before device access.
- GPU failures leave the caller's output unchanged. The policy API reports the
  selected backend and falls back only for `RUNTIME_UNAVAILABLE` or `NO_GPU`;
  kernel, allocation, and transfer errors remain visible. Execution is
  synchronous and has no asynchronous event handle.
- The GPU-only profiled call reports OpenCL event durations for both input
  uploads, kernel execution, and result download separately. These are device
  event times; they do not include host-side setup, compilation, allocation, or
  total call latency. A very short command can report zero when it finishes
  within the device timer's resolution.
- This demonstrates Sotlas-to-OpenCL C interop through C11. It does not yet
  lower Flow stages or Sotlas expressions into GPU kernels, and it does not
  provide CUDA, Vulkan, NPU, explicit cross-device scheduling, or a benchmark
  harness that accounts for host setup and end-to-end latency.

The hardware test is optional in CI because hosted runners do not promise an
OpenCL GPU. Native tests also supply a fake OpenCL provider: one compares CPU
and provider results for 259 exact-representable values, and others simulate
zero GPUs and zero platforms to verify required-device failure, unchanged
output, and CPU fallback. These tests verify host-side ABI, buffer transfers,
kernel dispatch, and policy handling. The optional hardware test runs the same
259-element exact-binary-fraction workload through the real provider and checks
each result against the CPU reference; it runs only on machines with an OpenCL
GPU.
