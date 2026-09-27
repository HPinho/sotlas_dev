# OpenCL vector add

This experimental example sends two contiguous f32 arrays from a C host through
a Sotlas C11 wrapper. It prefers OpenCL and falls back to CPU when no OpenCL
runtime or GPU is available, then checks every result and reports which backend
ran.

See the [OpenCL GPU preview contract](../../docs/opencl_gpu_preview.md) for
build instructions, supported platforms, status codes, and limits. The separate
hardware-only runtime test uses status 77 when no OpenCL GPU is present.
