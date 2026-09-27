# OpenCL vector add

This experimental example sends two contiguous f32 arrays from a C host through
a Sotlas C11 wrapper to the OpenCL runtime, then checks the values read back
from the GPU.

See the [OpenCL GPU preview contract](../../docs/opencl_gpu_preview.md) for
build instructions, supported platforms, status codes, and limits. A machine
without an OpenCL GPU exits with status 77 and prints that the device is
unavailable.
