/* device_reference.h — Reference/conformance provider for Sotlas DEVICE ABI v1.
 *
 * This is NOT a hardware driver. It performs no DMA, GPU submission, cache
 * maintenance, MMIO, interrupts, or physical queue work. It is a deterministic,
 * single-threaded software state machine used to validate the compiler/runtime
 * contract for:
 *
 *   submit -> complete -> synchronize -> reacquire
 *
 * The four sotlas_device_* functions are the frozen public C11 ABI consumed by
 * the reference DEVICE lowering. The sotlas_device_reference_* functions are
 * diagnostic/test helpers and are not part of the language-level DEVICE ABI.
 */
#ifndef SOTLAS_DEVICE_REFERENCE_H
#define SOTLAS_DEVICE_REFERENCE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef uintptr_t sotlas_device_queue_t;
typedef uintptr_t sotlas_device_submission_t;
typedef uintptr_t sotlas_device_completion_t;
typedef uintptr_t sotlas_device_fence_t;

typedef enum sotlas_device_reference_status {
    SOTLAS_DEVICE_REFERENCE_OK = 0,
    SOTLAS_DEVICE_REFERENCE_INVALID_ARGUMENT = 1,
    SOTLAS_DEVICE_REFERENCE_CAPACITY_EXHAUSTED = 2,
    SOTLAS_DEVICE_REFERENCE_UNKNOWN_SUBMISSION = 3,
    SOTLAS_DEVICE_REFERENCE_INVALID_STATE = 4,
    SOTLAS_DEVICE_REFERENCE_QUEUE_MISMATCH = 5,
    SOTLAS_DEVICE_REFERENCE_DUPLICATE_COMPLETION = 6,
    SOTLAS_DEVICE_REFERENCE_UNKNOWN_FENCE = 7,
    SOTLAS_DEVICE_REFERENCE_OWNER_NOT_IN_FENCE = 8
} sotlas_device_reference_status_t;

/* Frozen Sotlas DEVICE runtime ABI v1. */
sotlas_device_submission_t sotlas_device_submit(
    sotlas_device_queue_t queue,
    uintptr_t host_address,
    size_t host_extent,
    uintptr_t *out_device_address,
    size_t *out_device_extent
);

sotlas_device_completion_t sotlas_device_complete(
    sotlas_device_queue_t queue,
    sotlas_device_submission_t submission
);

sotlas_device_fence_t sotlas_device_sync(
    sotlas_device_queue_t queue,
    const sotlas_device_completion_t *completions,
    size_t completion_count
);

void sotlas_device_reacquire(
    sotlas_device_queue_t queue,
    uintptr_t device_address,
    size_t device_extent,
    sotlas_device_fence_t fence,
    uintptr_t *out_host_address,
    size_t *out_host_extent
);

/* Reference-provider diagnostics. Not part of the public language ABI. */
void sotlas_device_reference_reset(void);
sotlas_device_reference_status_t sotlas_device_reference_last_status(void);
int sotlas_device_reference_fence_consumed(sotlas_device_fence_t fence);

#ifdef __cplusplus
}
#endif

#endif /* SOTLAS_DEVICE_REFERENCE_H */
